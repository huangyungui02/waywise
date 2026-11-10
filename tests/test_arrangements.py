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


def test_valid_arrangements_and_same_day_return(itinerary):
    assert TravelArrangements.model_validate(itinerary).issues() == []
    itinerary["inbound"]["departure_time"] = "2026-12-04T18:00:00"
    itinerary["inbound"]["arrival_time"] = "2026-12-04T19:00:00"
    itinerary["stays"] = []
    assert TravelArrangements.model_validate(itinerary).issues() == []


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
def test_invalid_arrangements(itinerary, change, expected):
    change(itinerary)
    assert expected in " ".join(TravelArrangements.model_validate(itinerary).issues())


def test_transport_schema(itinerary):
    itinerary["outbound"]["type"] = "car"
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
    arrangements = TravelArrangements.model_validate(itinerary)
    assert arrangements.issues() == []
    assert arrangements.outbound.number is None
    del itinerary["outbound"]["departure_time"]
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
    updated.outbound.purchased = True
    updated.outbound.purchase_url = None
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
    with pytest.raises(ValueError, match="没有待确认"):
        await store.arrangements.confirm("chat-a")
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
