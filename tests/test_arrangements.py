"""基础安排校验与会话隔离，不访问外部服务。"""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from test_app import configured as configured  # noqa: PLC0414 — 导出 pytest fixture。

from app import agent as agent_module
from app.models.arrangements import TravelArrangements
from app.models.products import Product

ITINERARY = {
    "transports": [
        {
            "type": "train",
            "number": "G123",
            "departure_station": "上海虹桥",
            "arrival_station": "杭州东",
            "departure_time": "2026-12-04T09:00:00",
            "arrival_time": "2026-12-04T10:00:00",
            "purchase_url": "https://example.com/train",
            "purchased": False,
        },
        {
            "type": "flight",
            "number": "MU1234",
            "departure_station": "杭州萧山机场",
            "arrival_station": "上海虹桥机场",
            "departure_time": "2026-12-06T18:00:00",
            "arrival_time": "2026-12-06T19:00:00",
            "purchased": True,
        },
    ],
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


MULTI_ITINERARY = deepcopy(ITINERARY)
MULTI_ITINERARY["transports"].insert(
    1,
    {
        **ITINERARY["transports"][0],
        "number": "G456",
        "departure_station": "杭州东",
        "arrival_station": "南京南",
        "departure_time": "2026-12-05T10:00:00",
        "arrival_time": "2026-12-05T12:00:00",
        "purchased": True,
    },
)
MULTI_ITINERARY["transports"][-1].update(departure_station="南京禄口机场")
MULTI_ITINERARY["stays"][0]["check_out"] = "2026-12-05"
MULTI_ITINERARY["stays"].append(
    {
        **ITINERARY["stays"][0],
        "hotel": "南京测试酒店",
        "city": "南京",
        "check_in": "2026-12-05",
    }
)


def test_multi_city_arrangements():
    assert TravelArrangements.model_validate(MULTI_ITINERARY).issues() == []


@pytest.mark.parametrize(
    "change,expected",
    [
        (lambda t: t["stays"].pop(), "2026-12-05 晚住宿缺失"),
    ],
)
def test_multi_city_invalid_arrangements(change, expected):
    itinerary = deepcopy(MULTI_ITINERARY)
    change(itinerary)
    assert expected in " ".join(TravelArrangements.model_validate(itinerary).issues())


def test_overnight_transport_and_early_arrival_hotel(itinerary):
    itinerary["transports"][0].update(
        departure_time="2026-12-03T22:00:00", arrival_time="2026-12-04T06:00:00"
    )
    itinerary["transports"][-1].update(
        departure_time="2026-12-06T22:00:00", arrival_time="2026-12-07T06:00:00"
    )
    assert TravelArrangements.model_validate(itinerary).issues() == []
    itinerary["stays"][0]["check_in"] = "2026-12-03"
    assert TravelArrangements.model_validate(itinerary).issues() == []
    itinerary["stays"][0]["check_out"] = "2026-12-05"
    assert "2026-12-05 晚住宿缺失" in " ".join(
        TravelArrangements.model_validate(itinerary).issues()
    )


def test_route_requires_at_least_one_transport(itinerary):
    itinerary["transports"] = []
    with pytest.raises(ValidationError):
        TravelArrangements.model_validate(itinerary)


@pytest.fixture
def itinerary():
    return deepcopy(ITINERARY)


def test_valid_arrangements_and_same_day_return(itinerary):
    assert TravelArrangements.model_validate(itinerary).issues() == []
    itinerary["transports"][1]["departure_time"] = "2026-12-04T18:00:00"
    itinerary["transports"][1]["arrival_time"] = "2026-12-04T19:00:00"
    itinerary["stays"] = []
    assert TravelArrangements.model_validate(itinerary).issues() == []


@pytest.mark.parametrize(
    "change,expected",
    [
        (
            lambda t: t["transports"][1].update(departure_time="2026-12-04T08:00:00"),
            "依次递增",
        ),
        (lambda t: t["stays"][0].update(check_out="2026-12-05"), "2026-12-05"),
        (lambda t: t["stays"].append(deepcopy(t["stays"][0])), "重复"),
        (lambda t: t["stays"][0].update(check_out="2026-12-03"), "退房"),
        (lambda t: t["stays"][0].update(booked=False), "购买链接"),
    ],
)
def test_invalid_arrangements(itinerary, change, expected):
    change(itinerary)
    assert expected in " ".join(TravelArrangements.model_validate(itinerary).issues())


def test_transport_schema(itinerary):
    itinerary["transports"][0]["type"] = "car"
    with pytest.raises(ValidationError):
        TravelArrangements.model_validate(itinerary)


@pytest.mark.anyio
async def test_proposal_ends_run_and_confirmation_uses_pending(
    configured, itinerary, tmp_path, store_factory
):
    store = await store_factory(database=tmp_path / "travel.db")
    agent = agent_module.create_agent()
    calls = 0

    def propose(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "present_arrangements", itinerary, tool_call_id="proposal-1"
                ),
                ToolCallPart("confirm_arrangements", {}),
            ]
        )

    with agent.override(model=FunctionModel(propose)):
        result = await agent.run("选好了", deps=store, conversation_id="chat-a")
    assert calls == 1
    assert result.output == TravelArrangements.model_validate(itinerary)
    assert (await store.arrangements.get("chat-a")) is None
    assert (await store.arrangements.get_state("chat-a"))["pending_id"] == "proposal-1"
    assert (await store.arrangements.get_state("chat-b"))[
        "pending_arrangements"
    ] is None

    def confirm(messages, info):
        if messages[-1].parts[0].part_kind == "tool-return":
            return ModelResponse(parts=[TextPart("开始每日规划")])
        return ModelResponse(parts=[ToolCallPart("confirm_arrangements", {})])

    with agent.override(model=FunctionModel(confirm)):
        await agent.run("确认", deps=store, conversation_id="chat-a")
        missing = await agent.run("确认", deps=store, conversation_id="chat-b")
    assert (await store.arrangements.get("chat-a")) == result.output
    assert (await store.arrangements.get_state("chat-a"))[
        "pending_arrangements"
    ] is None
    assert "没有待确认方案" in str(missing.all_messages())


@pytest.mark.anyio
async def test_invalid_proposal_retries_without_saving(
    configured, itinerary, tmp_path, store_factory
):
    store = await store_factory(database=tmp_path / "travel.db")
    itinerary["stays"] = []
    calls = 0

    def model(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(
                parts=[ToolCallPart("present_arrangements", itinerary)]
            )
        assert "住宿缺失" in str(messages[-1])
        return ModelResponse(parts=[TextPart("需要补齐住宿")])

    agent = agent_module.create_agent()
    with agent.override(model=FunctionModel(model)):
        await agent.run("展示方案", deps=store, conversation_id="chat-a")
    assert (await store.arrangements.get_state("chat-a"))[
        "pending_arrangements"
    ] is None


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
    itinerary["transports"][0].update(
        type="bus",
        number=None,
        departure_station="成都茶店子客运站",
        arrival_station="四姑娘山镇停车场",
    )
    itinerary["transports"][1].update(
        type="bus",
        number=None,
        departure_station="四姑娘山镇停车场",
        arrival_station="成都东站",
    )
    itinerary["stays"][0].update(city="小金县", address="四姑娘山镇")
    arrangements = TravelArrangements.model_validate(itinerary)
    assert arrangements.issues() == []
    assert arrangements.transports[0].number is None
    del itinerary["transports"][0]["departure_time"]
    with pytest.raises(ValidationError):
        TravelArrangements.model_validate(itinerary)


@pytest.mark.anyio
async def test_arrangements_store_save_update_isolation_and_delete(
    tmp_path, itinerary, store_factory
):
    database = tmp_path / "旅行?#.db"
    store = await store_factory(database=database)
    arrangements = TravelArrangements.model_validate(itinerary)
    assert (await store.arrangements.get("missing")) is None
    await store.arrangements.delete("missing")
    await store.arrangements.present("chat-a", arrangements, "a1")
    await store.arrangements.confirm("chat-a")
    await store.arrangements.present("chat-b", arrangements, "b1")
    await store.arrangements.confirm("chat-b")
    updated = arrangements.model_copy(deep=True)
    updated.transports[0].purchased = True
    updated.transports[0].purchase_url = None
    await store.arrangements.present("chat-a", updated, "a2")
    assert (await store.arrangements.get("chat-a")) == arrangements
    store = await store_factory(database=database)
    assert (await store.arrangements.get_state("chat-a"))[
        "pending_arrangements"
    ] == updated
    with pytest.raises(ValueError, match="已更新"):
        await store.arrangements.confirm("chat-a", "a1")
    await store.arrangements.confirm("chat-a", "a2")
    assert (await store.arrangements.get_state("chat-a"))["confirmed_id"] == "a2"
    assert await store.arrangements.confirm("chat-a") == await store.arrangements.get(
        "chat-a"
    )
    store = await store_factory(database=database)
    assert (await store.arrangements.get("chat-a")) == updated
    assert (await store.arrangements.get("chat-b")) == arrangements
    await store.arrangements.delete("chat-a")
    await store.arrangements.delete("chat-a")
    store = await store_factory(database=database)
    assert (await store.arrangements.get("chat-a")) is None
    assert (await store.arrangements.get("chat-b")) == arrangements


@pytest.mark.anyio
async def test_delete_conversation_clears_all_stores(
    tmp_path, itinerary, store_factory
):

    from pydantic_ai import Conversation
    from pydantic_ai.conversation_store import ConversationConflict
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    store = await store_factory(tmp_path / "travel.db")
    arrangements = TravelArrangements.model_validate(itinerary)
    product = Product(
        name="酒店", description="近车站", purchase_url="https://example.com/hotel"
    )

    for conversation_id in ("first", "other"):
        await store.conversations.save(
            Conversation(
                conversation_id=conversation_id,
                messages=[ModelRequest(parts=[UserPromptPart("去杭州")])],
            )
        )
        await store.arrangements.present(conversation_id, arrangements, "proposal")
        await store.products.save(conversation_id, [product])

    # 单独删除交通住宿安排不影响商品或会话历史。
    await store.arrangements.delete("first")
    assert len(await store.products.list("first")) == 1
    assert (await store.conversations.load("first")).messages
    await store.arrangements.present("first", arrangements, "replacement")
    saved = await store.conversations.load("first")
    await store.conversations.save_messages(
        conversation=await store.conversations.load("first"),
        outcome="completed",
        messages=[ModelRequest(parts=[UserPromptPart("换一个酒店")])],
    )
    with pytest.raises(ConversationConflict):
        await store.conversations.delete_record(
            "first", expected_revision=saved.revision
        )
    assert (await store.arrangements.get_state("first"))[
        "pending_arrangements"
    ] == arrangements
    assert len(await store.products.list("first")) == 1
    latest = await store.conversations.load("first")
    await store.delete_conversation(latest.conversation_id)

    reopened = await store_factory(tmp_path / "travel.db")
    assert await reopened.conversations.load("first") is None
    assert (await reopened.arrangements.get_state("first"))[
        "pending_arrangements"
    ] is None
    assert (await reopened.products.list("first")) == []
    assert (await reopened.conversations.load("other")).messages
    assert (await reopened.arrangements.get_state("other"))[
        "pending_arrangements"
    ] == arrangements
    assert len(await reopened.products.list("other")) == 1


@pytest.mark.parametrize("kind", ["train", "flight", "bus", "drive", "taxi", "ferry"])
@pytest.mark.anyio
async def test_transport_can_be_confirmed_without_purchase_or_link(
    itinerary, kind, tmp_path, store_factory
):
    leg = itinerary["transports"][0]
    leg.update(type=kind, purchased=False, purchase_url=None)
    arrangements = TravelArrangements.model_validate(itinerary)
    assert arrangements.issues() == []
    store = await store_factory(database=tmp_path / "travel.db")
    await store.arrangements.present("chat-a", arrangements, "proposal")
    confirmed = await store.arrangements.confirm("chat-a", "proposal")
    assert confirmed.transports[0].purchased is False
    assert confirmed.transports[0].purchase_url is None
    assert await store.arrangements.get("chat-a") == arrangements


@pytest.mark.parametrize("with_stay", [False, True])
def test_one_way_trip_can_end_with_long_stay(itinerary, with_stay):
    itinerary["transports"] = itinerary["transports"][:1]
    if with_stay:
        itinerary["stays"][0]["check_out"] = "2027-01-04"
    else:
        itinerary["stays"] = []
    assert TravelArrangements.model_validate(itinerary).issues() == []


def test_multi_city_trip_can_end_elsewhere():
    itinerary = deepcopy(MULTI_ITINERARY)
    itinerary["transports"].pop()
    assert TravelArrangements.model_validate(itinerary).issues() == []


@pytest.mark.parametrize(
    "departure,arrival",
    [
        ("2026-12-04T01:00:00Z", "2026-12-04T10:00:00+08:00"),
        ("2026-12-04T09:00:00", "2026-12-04T02:00:00Z"),
    ],
)
def test_transport_accepts_standard_datetime_and_normalizes_to_beijing(
    itinerary, departure, arrival
):
    itinerary["transports"][0].update(departure_time=departure, arrival_time=arrival)
    arrangements = TravelArrangements.model_validate(itinerary)
    assert arrangements.issues() == []
    leg = arrangements.transports[0]
    assert leg.departure_time.isoformat() == "2026-12-04T09:00:00+08:00"
    assert leg.arrival_time.isoformat() == "2026-12-04T10:00:00+08:00"
