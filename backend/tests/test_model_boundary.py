import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.agents.copilot import CopilotModel
from backend.agents.fake import FakeModel
from backend.agents.permissions import on_permission_request
from backend.app.knowledge import KnowledgeBase
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.conftest import events
from backend.tools.context import ToolContext


def test_permission_handler_returns_deny_by_default(monkeypatch):
    sdk = ModuleType("copilot.session")
    sdk.PermissionDecisionApproveOnce = type("Approve", (), {})
    sdk.PermissionDecisionUserNotAvailable = type("Deny", (), {})
    monkeypatch.setitem(sys.modules, "copilot.session", sdk)
    assert isinstance(on_permission_request(SimpleNamespace(kind="custom-tool", tool_name="search_knowledge")),
                      sdk.PermissionDecisionApproveOnce)
    for request in (SimpleNamespace(kind="shell", tool_name="search_knowledge"),
                    SimpleNamespace(kind="custom-tool", tool_name="approve"), {}, None):
        assert isinstance(on_permission_request(request), sdk.PermissionDecisionUserNotAvailable)


def test_missing_token_fails_before_sdk_import(monkeypatch, knowledge_dir):
    monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
    context = ToolContext(KnowledgeBase(knowledge_dir), "session", "demo")
    with pytest.raises(RuntimeError, match="copilot_token_missing"):
        asyncio.run(CopilotModel().generate("test", context))


def test_failed_final_validation_does_not_publish_proposal(knowledge_dir, headers):
    class UnsafeAfterProposal(FakeModel):
        async def generate(self, prompt, context):
            await super().generate(prompt, context)
            assert context.pending
            return json.dumps({"answer": "살충제 추천", "source_ids": ["checked"]})

    app = create_app(Settings(knowledge_dir=knowledge_dir), UnsafeAfterProposal())
    with TestClient(app) as client:
        response = client.post("/api/farms/demo/chat", headers=headers, json={"message": "일정 추가"})
        assert "살충제" not in response.text
        assert events(response)[-1] == ("done", {"ok": False})
        assert app.state.store.sessions[headers["X-Session-Id"]].proposals == {}


def test_retry_cannot_reuse_source_ids_or_pending_proposals(knowledge_dir, headers):
    class RetryModel(FakeModel):
        async def generate(self, prompt, context):
            if self.calls == 0:
                await super().generate(prompt, context)
                return "invalid JSON"
            self.calls += 1
            assert not context.found and not context.pending
            return json.dumps({"answer": "자료 확인", "source_ids": ["checked"]})

    app = create_app(Settings(knowledge_dir=knowledge_dir), RetryModel())
    with TestClient(app) as client:
        response = client.post("/api/farms/demo/chat", headers=headers, json={"message": "일정 추가"})
        assert any(name == "error" for name, _ in events(response))
        assert not any(name == "message" for name, _ in events(response))
        assert app.state.store.sessions[headers["X-Session-Id"]].proposals == {}


def test_unattributed_model_claim_is_replaced(knowledge_dir, headers):
    output = json.dumps({"answer": "근거 없는 임의의 농사 조언", "source_ids": []})
    app = create_app(Settings(knowledge_dir=knowledge_dir), FakeModel(raw_output=output))
    with TestClient(app) as client:
        response = client.post("/api/farms/demo/chat", headers=headers, json={"message": "수확 준비"})
        assert "근거 없는 임의의 농사 조언" not in response.text
        message = next(data for name, data in events(response) if name == "message")
        assert message["evidence"] == "확인 필요"


def test_parallel_contexts_do_not_share_sources(knowledge_dir):
    async def run():
        knowledge = KnowledgeBase(knowledge_dir)
        first = ToolContext(knowledge, "one", "demo")
        second = ToolContext(knowledge, "two", "demo")

        async def search(context, query):
            context.search_knowledge(query)
            await asyncio.sleep(0)
            return set(context.found)

        results = await asyncio.gather(search(first, "수확"), search(second, "nomatch"))
        assert results == [{"checked"}, set()]

    asyncio.run(run())
