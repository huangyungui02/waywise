"""使用真实 DBOS/SQLite 和离线模型验证执行、排队、停止与重放。"""

import threading
import time

import anyio
import httpx2
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel
from starlette.testclient import TestClient
from test_server import request

from app.settings import Settings


def wait_detail(client, cid, outcome):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        detail = client.get(f"/api/conversations/{cid}").json()
        if detail["summary"]["outcome"] == outcome:
            return detail
        time.sleep(0.05)
    raise AssertionError(detail)


def disconnect(client, backend, cid, started):
    async def send_and_disconnect():
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=backend),
            base_url="http://test",
            headers={"Authorization": "Bearer offline-access-token"},
        ) as browser:

            async def send():
                await browser.post(
                    f"/api/conversations/{cid}/chat", json=request("后台测试")
                )

            with anyio.fail_after(10):
                async with anyio.create_task_group() as group:
                    group.start_soon(send)
                    while not started.is_set():
                        await anyio.sleep(0.01)
                    group.cancel_scope.cancel()

    client.portal.call(send_and_disconnect)


@pytest.mark.parametrize("stop", [False, True])
def test_disconnect_replay_and_stop(app_factory, tmp_path, stop):
    started = threading.Event()
    release = threading.Event()
    calls = 0

    async def model(messages, info):
        nonlocal calls
        calls += 1
        yield "已经生成的建议。"
        started.set()
        while not release.is_set():
            await anyio.sleep(0.01)
        yield "完整建议。"

    agent = Agent(FunctionModel(stream_function=model))
    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test",
        AMAP_MAPS_API_KEY="test",
        database_path=tmp_path / "travel.db",
        max_concurrent_runs=1,
    )
    backend = app_factory(settings, agent)
    with TestClient(backend) as client:
        cid = client.post("/api/conversations").json()["id"]
        disconnect(client, backend, cid, started)
        assert (
            client.post(
                f"/api/conversations/{cid}/chat", json=request("重复")
            ).status_code
            == 409
        )
        assert client.delete(f"/api/conversations/{cid}").status_code == 409
        assert (
            client.post(f"/api/conversations/{cid}/proposals/old/confirm").status_code
            == 409
        )
        if stop:
            assert client.post(f"/api/conversations/{cid}/chat/stop").status_code == 204
        else:
            release.set()
        detail = wait_detail(client, cid, "cancelled" if stop else "completed")
        response = client.get(
            f"/api/conversations/{cid}/chat/stream",
            params={"run_id": detail["recovery"]["run_id"]},
        )
        assert "已经生成的建议" in response.text
        assert ("完整建议" in response.text) is not stop
        assert "[DONE]" in response.text
        assert calls == 1
        assert "后台测试" in str(detail["messages"])
        if stop:
            # 执行器取消后仍会收尾部分历史。
            deadline = time.monotonic() + 5
            while (
                "已经生成的建议" not in str(detail["messages"])
                and time.monotonic() < deadline
            ):
                time.sleep(0.05)
                detail = client.get(f"/api/conversations/{cid}").json()
            assert "已经生成的建议" in str(detail["messages"])
        assert (
            client.get(
                f"/api/conversations/{cid}/chat/stream", params={"run_id": "old"}
            ).status_code
            == 409
        )
        release.set()


def test_capacity_queues_instead_of_rejecting(app_factory, tmp_path):
    started = threading.Event()
    release = threading.Event()

    async def model(messages, info):
        started.set()
        yield "开始。"
        while not release.is_set():
            await anyio.sleep(0.01)
        yield "结束。"

    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test",
        AMAP_MAPS_API_KEY="test",
        database_path=tmp_path / "travel.db",
        max_concurrent_runs=1,
    )
    backend = app_factory(settings, Agent(FunctionModel(stream_function=model)))
    with TestClient(backend) as client:
        first = client.post("/api/conversations").json()["id"]
        second = client.post("/api/conversations").json()["id"]
        disconnect(client, backend, first, started)
        from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

        run_id = client.portal.call(
            backend.state.replies.start,
            second,
            SubmitMessage.model_validate(request("排队")),
        )
        assert run_id
        detail = client.get(f"/api/conversations/{second}").json()
        assert detail["summary"]["outcome"] == "queued"
        assert "排队" in str(detail["recovery"]["messages"])
        assert client.post(f"/api/conversations/{second}/chat/stop").status_code == 204
        assert wait_detail(client, second, "cancelled")
        release.set()
        assert wait_detail(client, first, "completed")


@pytest.mark.parametrize("graceful", [False, True])
def test_process_restart_recovers_steps_and_replaces_partial_output(tmp_path, graceful):
    import json
    import subprocess
    import sys
    from pathlib import Path

    worker = Path(__file__).with_name("durable_worker.py")

    def wait_file(name, process):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if (tmp_path / name).exists():
                return
            assert process.poll() is None, (tmp_path / "worker.log").read_text()
            time.sleep(0.05)
        raise AssertionError((tmp_path / "worker.log").read_text())

    with (tmp_path / "worker.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, str(worker), str(tmp_path)], stdout=log, stderr=log
        )
        try:
            wait_file("started", process)
            if graceful:
                (tmp_path / "shutdown").touch()
                assert process.wait(timeout=10) == 0
                (tmp_path / "shutdown").unlink()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        (tmp_path / "release").touch()
        process = subprocess.Popen(
            [sys.executable, str(worker), str(tmp_path)], stdout=log, stderr=log
        )
        try:
            wait_file("done", process)
            assert process.wait(timeout=10) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    assert (tmp_path / "tool-calls").read_text().splitlines() == ["query"]
    assert (tmp_path / "model-calls").read_text().splitlines() == [
        "tool",
        "response",
        "response",
    ]
    detail = json.loads((tmp_path / "done").read_text())
    assert detail["summary"]["outcome"] == "completed"
    assert [m["role"] for m in detail["messages"]].count("user") == 1
    replay = (tmp_path / "replay").read_text()
    assert "恢复后的完整答复" in replay
    assert "中断前的部分输出" not in replay


def test_startup_failure_ends_stream_and_releases_queue(
    app_factory, tmp_path, monkeypatch
):
    settings = Settings(
        _env_file=None,
        DASHSCOPE_API_KEY="test",
        AMAP_MAPS_API_KEY="test",
        database_path=tmp_path / "travel.db",
    )

    async def model(messages, info):
        yield "可以继续咨询。"

    backend = app_factory(settings, Agent(FunctionModel(stream_function=model)))
    with TestClient(backend) as client:
        cid = client.post("/api/conversations").json()["id"]
        original = backend.state.store.conversations.load

        async def unavailable(conversation_id, **kwargs):
            raise RuntimeError("临时存储故障")

        with monkeypatch.context() as patch:
            patch.setattr(backend.state.store.conversations, "load", unavailable)
            response = client.post(
                f"/api/conversations/{cid}/chat", json=request("去杭州")
            )
            assert "回复执行失败" in response.text
            assert "[DONE]" in response.text
        assert backend.state.store.conversations.load == original
        response = client.post(f"/api/conversations/{cid}/chat", json=request("继续"))
        assert "可以继续咨询" in response.text
