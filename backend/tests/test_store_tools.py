from datetime import date
from types import SimpleNamespace

import pytest

from backend.agents.permissions import permission_allowed
from backend.app.knowledge import KnowledgeBase
from backend.app.policy import PolicyError
from backend.app.store import MemoryStore, StoreError
from backend.tools.context import ToolContext


@pytest.mark.parametrize("kind,name,allowed", [
    ("custom-tool", "search_knowledge", True),
    ("custom-tool", "propose_calendar_event", True),
    ("custom-tool", "shell", False), ("shell", "search_knowledge", False),
    ("read", "search_knowledge", False), ("url", "fetch", False),
])
def test_permissions(kind, name, allowed):
    assert permission_allowed(SimpleNamespace(kind=kind, tool_name=name)) is allowed


def test_proposal_tool_has_no_store_access_and_requires_search(knowledge_dir):
    context = ToolContext(KnowledgeBase(knowledge_dir), "session", "demo")
    assert not hasattr(context, "store")
    with pytest.raises(PolicyError):
        context.propose_calendar_event("수확 준비 점검", date.today().isoformat(),
                                       "도구 확인", ["checked"])
    context.search_knowledge("수확")
    result = context.propose_calendar_event("수확 준비 점검", date.today().isoformat(),
                                            "도구 확인", ["checked"])
    assert result["status"] == "pending"
    assert len(context.pending) == 1
    other = ToolContext(KnowledgeBase(knowledge_dir), "session", "demo")
    assert other.found == {}


def test_expiry_and_approve_reject_race(knowledge_dir):
    clock = [100.0]
    store = MemoryStore(session_ttl=100, proposal_ttl=5, clock=lambda: clock[0])
    store.touch("session")
    context = ToolContext(KnowledgeBase(knowledge_dir), "session", "demo")
    context.search_knowledge("수확")
    context.propose_calendar_event("수확 준비 점검", "2026-11-05", "확인", ["checked"])
    pending = context.pending[0]
    store.publish("session", [pending])
    clock[0] += 6
    with pytest.raises(StoreError) as error:
        store.decide("session", pending.id, "approve")
    assert error.value.status_code == 409
    clock[0] += 101
    store.touch("session")
    assert store.calendar("session", "demo") == []
    with pytest.raises(StoreError):
        store.decide("session", pending.id, "approve")


def test_approve_reject_is_atomic(knowledge_dir):
    from concurrent.futures import ThreadPoolExecutor

    store = MemoryStore()
    store.touch("session")
    context = ToolContext(KnowledgeBase(knowledge_dir), "session", "demo")
    context.search_knowledge("수확")
    context.propose_calendar_event("수확 준비 점검", "2026-11-05", "확인", ["checked"])
    item = context.pending[0]
    store.publish("session", [item])

    def decide(action):
        try:
            return store.decide("session", item.id, action)
        except StoreError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ["approve", "reject"]))
    assert sum(result == 409 for result in results) == 1
    assert len(store.calendar("session", "demo")) in (0, 1)
