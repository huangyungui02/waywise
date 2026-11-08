"""基础安排校验与会话隔离，不访问外部服务。"""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from test_app import configured  # noqa: F401

import agent as agent_module
from trip import Trip, TripStore


@pytest.fixture
def itinerary():
    return {
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


def test_confirmation_tool_and_conversation_isolation(configured, itinerary):
    store = TripStore()
    agent = agent_module.create_agent()

    def model(messages, info):
        if messages[-1].parts[0].part_kind == "tool-return":
            return ModelResponse(parts=[TextPart("完成")])
        return ModelResponse(parts=[ToolCallPart("confirm_trip", {"trip": itinerary})])

    with agent.override(model=FunctionModel(model)):
        agent.run_sync("确认这套安排", deps=store, conversation_id="chat-a")
        saved = store.confirmed["chat-a"].model_dump()
        assert not store.confirmed["chat-a"].outbound.purchased
        assert "chat-b" not in store.confirmed
        itinerary["stays"] = []
        result = agent.run_sync("确认另一套安排", deps=store, conversation_id="chat-b")
        assert "chat-b" not in store.confirmed
        assert "住宿缺失" in str(result.all_messages())
        agent.run_sync("修改安排", deps=store, conversation_id="chat-a")
        assert store.confirmed["chat-a"].model_dump() == saved


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


@pytest.mark.parametrize("persistent", [False, True])
def test_trip_store_save_update_isolation_and_delete(tmp_path, itinerary, persistent):
    database = tmp_path / "旅行?#.db" if persistent else None
    store = TripStore(database=database)
    trip = Trip.model_validate(itinerary)
    assert store.get("missing") is None
    store.delete("missing")
    store.save("chat-a", trip)
    store.save("chat-b", trip)
    updated = trip.model_copy(deep=True)
    updated.outbound.purchased = True
    updated.outbound.purchase_url = None
    store.save("chat-a", updated)
    if persistent:
        store = TripStore(database=database)
    assert store.get("chat-a") == updated
    assert store.get("chat-b") == trip
    store.delete("chat-a")
    store.delete("chat-a")
    if persistent:
        store = TripStore(database=database)
    assert store.get("chat-a") is None
    assert store.get("chat-b") == trip
