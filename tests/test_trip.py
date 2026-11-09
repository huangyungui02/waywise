"""基础安排校验与会话隔离，不访问外部服务。"""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from test_app import configured  # noqa: F401

import agent as agent_module
from trip import Trip, TripStore


ITINERARY = {
    "origin": "上海",
    "destination": "杭州",
    "outbound": {
        "type": "train",
        "name": "G123",
        "number": "G123",
        "departure_point": "上海虹桥",
        "arrival_point": "杭州东",
        "departure_time": "2026-12-04T09:00:00",
        "arrival_time": "2026-12-04T10:00:00",
        "purchase_url": "https://example.com/train",
        "purchased": False,
    },
    "inbound": {
        "type": "flight",
        "name": "MU1234",
        "number": "MU1234",
        "departure_point": "杭州萧山机场",
        "arrival_point": "上海虹桥机场",
        "departure_time": "2026-12-06T18:00:00",
        "arrival_time": "2026-12-06T19:00:00",
        "purchased": True,
    },
    "stays": [
        {
            "hotel": "测试酒店",
            "city": "杭州",
            "address": "测试地址",
            "check_in": "2026-12-04",
            "check_out": "2026-12-06",
            "booked": True,
        }
    ],
}


@pytest.fixture
def itinerary():
    return deepcopy(ITINERARY)


def test_valid_trip_and_day_trip(itinerary):
    assert Trip.model_validate(itinerary).issues() == []
    itinerary["inbound"]["departure_time"] = "2026-12-04T18:00:00"
    itinerary["inbound"]["arrival_time"] = "2026-12-04T19:00:00"
    itinerary["stays"] = []
    assert Trip.model_validate(itinerary).issues() == []


@pytest.mark.parametrize(
    "change,expected",
    [
        (
            lambda t: t["inbound"].update(departure_time="2026-12-04T08:00:00"),
            "依次递增",
        ),
        (lambda t: t.update(destination="上海"), "不能相同"),
        (lambda t: t["outbound"].update(purchase_url=None), "购买链接"),
        (lambda t: t["stays"][0].update(check_out="2026-12-05"), "2026-12-05"),
        (lambda t: t["stays"].append(deepcopy(t["stays"][0])), "重复"),
        (lambda t: t["stays"][0].update(check_out="2026-12-03"), "退房"),
        (lambda t: t["stays"][0].update(booked=False), "购买链接"),
    ],
)
def test_invalid_trip(itinerary, change, expected):
    change(itinerary)
    assert expected in " ".join(Trip.model_validate(itinerary).issues())


def test_transport_schema(itinerary):
    itinerary["outbound"]["type"] = "car"
    with pytest.raises(ValidationError):
        Trip.model_validate(itinerary)


def test_proposal_ends_run_and_confirmation_uses_pending(
    configured, itinerary, tmp_path
):
    store = TripStore(database=tmp_path / "travel.db")
    agent = agent_module.create_agent()
    calls = 0

    def propose(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(
            parts=[
                ToolCallPart("present_trip", itinerary, tool_call_id="proposal-1"),
                ToolCallPart("confirm_trip", {}),
            ]
        )

    with agent.override(model=FunctionModel(propose)):
        result = agent.run_sync("选好了", deps=store, conversation_id="chat-a")
    assert calls == 1
    assert result.output == Trip.model_validate(itinerary)
    assert store.get("chat-a") is None
    assert store.get_state("chat-a")["pending_id"] == "proposal-1"
    assert store.get_state("chat-b")["pending_trip"] is None

    def confirm(messages, info):
        if messages[-1].parts[0].part_kind == "tool-return":
            return ModelResponse(parts=[TextPart("开始每日规划")])
        return ModelResponse(parts=[ToolCallPart("confirm_trip", {})])

    with agent.override(model=FunctionModel(confirm)):
        agent.run_sync("确认", deps=store, conversation_id="chat-a")
        missing = agent.run_sync("确认", deps=store, conversation_id="chat-b")
    assert store.get("chat-a") == result.output
    assert store.get_state("chat-a")["pending_trip"] is None
    assert "没有待确认方案" in str(missing.all_messages())


def test_invalid_proposal_retries_without_saving(configured, itinerary, tmp_path):
    store = TripStore(database=tmp_path / "travel.db")
    itinerary["stays"] = []
    calls = 0

    def model(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[ToolCallPart("present_trip", itinerary)])
        assert "住宿缺失" in str(messages[-1])
        return ModelResponse(parts=[TextPart("需要补齐住宿")])

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(model)):
        agent.run_sync("展示方案", deps=store, conversation_id="chat-a")
    assert store.get_state("chat-a")["pending_trip"] is None


def test_time_is_a_tool(configured):
    calls = iter(["current_time"])

    def model(messages, info):
        name = next(calls, None)
        if name:
            return ModelResponse(parts=[ToolCallPart(name, {})])
        return ModelResponse(parts=[TextPart("完成")])

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(model)):
        result = agent.run_sync("现在是北京时间几点？")
    from pydantic_ai.messages import ModelRequest, ToolReturnPart

    returns = [
        p
        for m in result.all_messages()
        for p in m.parts
        if isinstance(p, ToolReturnPart)
    ]
    assert isinstance(returns[0].content, str)
    assert "当前北京时间" in returns[0].content
    for message in result.all_messages():
        if isinstance(message, ModelRequest):
            assert "当前北京时间：" not in (message.instructions or "")
            assert "G123" not in (message.instructions or "")


def test_bus_to_scenic_destination(itinerary):
    itinerary.update(origin="成都", destination="四姑娘山")
    itinerary["outbound"].update(
        type="bus",
        name="成都至四姑娘山景区直通车",
        number=None,
        departure_point="成都茶店子客运站",
        arrival_point="四姑娘山镇停车场",
    )
    itinerary["inbound"].update(
        type="bus",
        name="四姑娘山至成都直通车",
        number=None,
        departure_point="四姑娘山镇停车场",
        arrival_point="成都东站",
    )
    itinerary["stays"][0].update(city="小金县", address="四姑娘山镇")
    trip = Trip.model_validate(itinerary)
    assert trip.issues() == []
    assert trip.outbound.number is None
    del itinerary["outbound"]["departure_time"]
    with pytest.raises(ValidationError):
        Trip.model_validate(itinerary)


def test_trip_store_save_update_isolation_and_delete(tmp_path, itinerary):
    database = tmp_path / "旅行?#.db"
    store = TripStore(database=database)
    trip = Trip.model_validate(itinerary)
    assert store.get("missing") is None
    store.delete("missing")
    store.present("chat-a", trip, "a1")
    store.confirm("chat-a")
    store.present("chat-b", trip, "b1")
    store.confirm("chat-b")
    updated = trip.model_copy(deep=True)
    updated.outbound.purchased = True
    updated.outbound.purchase_url = None
    store.present("chat-a", updated, "a2")
    assert store.get("chat-a") == trip
    store = TripStore(database=database)
    assert store.get_state("chat-a")["pending_trip"] == updated
    with pytest.raises(ValueError, match="已更新"):
        store.confirm("chat-a", "a1")
    store.confirm("chat-a", "a2")
    assert store.get_state("chat-a")["confirmed_id"] == "a2"
    with pytest.raises(ValueError, match="没有待确认"):
        store.confirm("chat-a")
    store = TripStore(database=database)
    assert store.get("chat-a") == updated
    assert store.get("chat-b") == trip
    store.delete("chat-a")
    store.delete("chat-a")
    store = TripStore(database=database)
    assert store.get("chat-a") is None
    assert store.get("chat-b") == trip
