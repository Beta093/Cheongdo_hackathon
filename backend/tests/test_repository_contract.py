from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock, Barrier

import pytest

from backend.app.cosmos import CosmosStore
from backend.app.knowledge import KnowledgeBase
from backend.app.schemas import FarmInput, LogInput, Today
from backend.app.store import MemoryStore, StoreError
from backend.tests.test_p1 import FARM, LOG
from backend.tools.context import ToolContext


class FakeConflict(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


class FakeContainer:
    """Shared transport for independent adapter instances, enforcing partition and ETag."""
    def __init__(self):
        self.items = {}
        self.lock = RLock()
        self.sequence = 0
        self.conflicts = 0
        self.barrier = None

    def read_item(self, item, partition_key):
        with self.lock:
            value = self.items.get((partition_key, item))
            if value is None:
                raise FakeConflict(404)
            return deepcopy(value)

    def create_item(self, body):
        with self.lock:
            key = (body["farmId"], body["id"])
            if key in self.items:
                raise FakeConflict(409)
            return self._save(key, body)

    def replace_item(self, item, body, etag, match_condition):
        assert etag and match_condition == "IfNotModified"
        barrier = self.barrier
        if barrier and body["farmId"] != CosmosStore.DIRECTORY:
            barrier.wait(timeout=5)
            self.barrier = None
        with self.lock:
            key = (body["farmId"], item)
            if self.conflicts:
                self.conflicts -= 1
                raise FakeConflict(412)
            if key not in self.items or self.items[key]["_etag"] != etag:
                raise FakeConflict(412)
            return self._save(key, body)

    def _save(self, key, body):
        self.sequence += 1
        value = deepcopy(body)
        value["_etag"] = str(self.sequence)
        self.items[key] = value
        return deepcopy(value)


@pytest.fixture(params=["memory", "cosmos"])
def repository(request):
    clock = [100.0]
    if request.param == "memory":
        store = MemoryStore(session_ttl=100, proposal_ttl=5, clock=lambda: clock[0])
    else:
        store = CosmosStore(FakeContainer(), session_ttl=100, proposal_ttl=5,
                            clock=lambda: clock[0], match_condition="IfNotModified")
    store.touch("one")
    store.touch("two")
    return store, clock


def pending(knowledge_dir, farm_id="demo"):
    context = ToolContext(KnowledgeBase(knowledge_dir), "one", farm_id)
    context.search_knowledge("수확")
    context.propose_calendar_event("수확 준비 점검", "2026-11-05", "확인", ["checked"])
    return context.pending[0]


def test_contract_farms_logs_context_and_copies(repository):
    store, _ = repository
    farm = store.create_farm("one", FarmInput(**FARM))
    with pytest.raises(StoreError) as error:
        store.farm("two", farm["id"])
    assert error.value.status_code == 404
    for kind in ("work", "symptom", "harvest"):
        body = LOG | {"type": kind}
        if kind == "harvest":
            body["amount"] = 5
        store.add_log("one", farm["id"], LogInput(**body))
    assert len(store.logs("one", farm["id"])) == 3
    result = store.logs("one", farm["id"])
    result[0].note = "changed"
    assert all(item.note != "changed" for item in store.logs("one", farm["id"]))
    assert store.logs("two", "demo") == []
    store.remember("one", "private", "answer", farm["id"])
    assert store.history("one", "demo") == []
    assert store.history("two", "demo") == []


def test_contract_cache_revision_and_approval(repository, knowledge_dir):
    store, _ = repository
    value = Today(farmId="demo", date="2026-11-05", tasks=[], notices=[], model_mode="fake")
    key = "demo:2026-11-05"
    version = store.revision("one", "demo")
    store.cache("one", key, value, version)
    assert store.cached("one", key) == value
    assert store.cached("two", key) is None
    store.add_log("one", "demo", LogInput(**LOG))
    assert store.cached("one", key) is None
    store.cache("one", key, value, version)
    assert store.cached("one", key) is None  # In-flight old generation cannot restore cache.
    store.cache("one", key, value, store.revision("one", "demo"))
    item = pending(knowledge_dir)
    store.publish("one", [item])
    with pytest.raises(StoreError):
        store.decide("two", item.id, "approve")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.decide("one", item.id, "approve"), range(8)))
    assert len({result.id for result in results}) == 1
    assert len(store.calendar("one", "demo")) == 1
    assert store.cached("one", key) is None
    with pytest.raises(StoreError) as error:
        store.decide("one", item.id, "reject")
    assert error.value.status_code == 409


def test_contract_log_update_delete_and_farm_isolation(repository):
    store, _ = repository
    farm = store.create_farm("one", FarmInput(**FARM))
    item = store.add_log("one", farm["id"], LogInput(**LOG))
    for session, farm_id in (("two", farm["id"]), ("one", "demo")):
        with pytest.raises(StoreError):
            store.update_log(session, farm_id, item.id, LogInput(**LOG))
        with pytest.raises(StoreError):
            store.delete_log(session, farm_id, item.id)
    updated = store.update_log("one", farm["id"], item.id, LogInput(**(LOG | {"note": "수정한 기록"})))
    assert updated.id == item.id and updated.note == "수정한 기록"
    assert store.revision("one", farm["id"]) == 2
    store.delete_log("one", farm["id"], item.id)
    assert store.logs("one", farm["id"]) == []
    assert store.revision("one", farm["id"]) == 3
    with pytest.raises(StoreError):
        store.delete_log("one", farm["id"], item.id)


def test_contract_mutation_keeps_other_farm_cache(repository):
    store, _ = repository
    farm = store.create_farm("one", FarmInput(**FARM))
    first = Today(farmId="demo", date="2026-11-05", tasks=[], notices=[], model_mode="fake")
    second = first.model_copy(update={"farmId": farm["id"]})
    store.cache("one", "demo:2026-11-05", first)
    store.cache("one", f'{farm["id"]}:2026-11-05', second)
    store.add_log("one", farm["id"], LogInput(**LOG))
    assert store.cached("one", "demo:2026-11-05") == first
    assert store.cached("one", f'{farm["id"]}:2026-11-05') is None


def test_contract_expiry_and_idle_refresh(repository, knowledge_dir):
    store, clock = repository
    farm = store.create_farm("one", FarmInput(**FARM))
    store.add_log("one", farm["id"], LogInput(**LOG))
    item = pending(knowledge_dir, farm["id"])
    store.publish("one", [item])
    clock[0] += 6
    with pytest.raises(StoreError) as error:
        store.decide("one", item.id, "approve")
    assert error.value.status_code == 409
    clock[0] += 90
    store.touch("one")
    clock[0] += 10
    assert store.logs("one", farm["id"])
    clock[0] += 101
    with pytest.raises(StoreError):
        store.farm("one", farm["id"])
    store.touch("one")
    assert store.calendar("one", "demo") == []
    with pytest.raises(StoreError):
        store.farm("one", farm["id"])
    with pytest.raises(StoreError):
        store.decide("one", item.id, "approve")


def test_contract_reject_is_idempotent_and_races(repository, knowledge_dir):
    store, _ = repository
    item = pending(knowledge_dir)
    store.publish("one", [item])
    def decide(action):
        try:
            return store.decide("one", item.id, action)
        except StoreError as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ["approve", "reject"]))
    assert sum(result == 409 for result in results) == 1
    rejected = pending(knowledge_dir)
    store.publish("one", [rejected])
    assert store.decide("one", rejected.id, "reject") == store.decide("one", rejected.id, "reject")


def test_cosmos_restart_conditional_conflicts_and_atomicity(knowledge_dir):
    container = FakeContainer()
    first = CosmosStore(container, match_condition="IfNotModified")
    first.touch("one")
    item = pending(knowledge_dir)
    first.publish("one", [item])
    second = CosmosStore(container, match_condition="IfNotModified")
    container.barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda store: store.decide("one", item.id, "approve"), [first, second]))
    assert results[0] == results[1]
    assert len(second.calendar("one", "demo")) == 1
    container.conflicts = 2
    second.add_log("one", "demo", LogInput(**LOG))
    assert len(first.logs("one", "demo")) == 1
    state = next(value for (partition, _), value in container.items.items() if partition == "demo")
    assert state["state"]["proposals"][item.id]["status"] == "approved"
    assert len(state["state"]["events"]) == 1
    assert state["ttl"] == first.session_ttl * 2


def test_cosmos_registered_farm_survives_adapter_restart():
    container = FakeContainer()
    first = CosmosStore(container, match_condition="IfNotModified")
    first.touch("one")
    farm = first.create_farm("one", FarmInput(**FARM))
    first.add_log("one", farm["id"], LogInput(**LOG))
    second = CosmosStore(container, match_condition="IfNotModified")
    second.touch("one")
    assert second.farm("one", farm["id"]) == farm
    assert len(second.logs("one", farm["id"])) == 1
    assert any(partition == farm["id"] for partition, _ in container.items)


def test_cosmos_conflict_exhaustion_does_not_save_partial_state(knowledge_dir):
    container = FakeContainer()
    store = CosmosStore(container, match_condition="IfNotModified")
    store.touch("one")
    item = pending(knowledge_dir)
    store.publish("one", [item])
    container.conflicts = 12
    with pytest.raises(StoreError) as error:
        store.decide("one", item.id, "approve")
    assert error.value.status_code == 409
    assert store.calendar("one", "demo") == []
    assert store.decide("one", item.id, "approve").id == item.event.id
