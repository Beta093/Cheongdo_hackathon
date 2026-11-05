"""Farm aggregates updated with ETag CAS; no SDK is required for fake-container tests.

Each farm/session generation is one document in the actual farmId partition. Proposal
status, calendar insertion and cache revision therefore commit in one atomic write.
The bounded session directory uses a reserved partition and contains no farm notes.
"""
import json
import os
import time
from copy import deepcopy
from dataclasses import fields
from threading import RLock
from typing import Callable, Protocol
from uuid import uuid4

from backend.app.schemas import CalendarEvent, FarmInput, LogEntry, LogInput, Proposal, Today
from backend.app.store import MemoryStore, Session, StoreError


class DocumentContainer(Protocol):
    def read_item(self, item: str, partition_key: str) -> dict: ...
    def create_item(self, body: dict) -> dict: ...
    def replace_item(self, item: str, body: dict, **kwargs) -> dict: ...


class CosmosStore:
    DIRECTORY = "__sessions__"

    def __init__(self, container: DocumentContainer, session_ttl: int = 7200,
                 proposal_ttl: int = 1800, max_sessions: int = 1000,
                 clock: Callable[[], float] = time.time, match_condition="IfNotModified"):
        self.container = container
        self.session_ttl, self.proposal_ttl = session_ttl, proposal_ttl
        self.max_sessions, self.clock = max_sessions, clock
        self.match_condition = match_condition
        if match_condition is None:
            raise ValueError("Conditional writes are required")
        self.sessions: dict[str, Session] = {}
        self.lock = RLock()

    @classmethod
    def from_environment(cls, settings):
        endpoint = os.environ.get("COSMOS_ENDPOINT", "").strip()
        if not endpoint.startswith("https://"):
            raise ValueError("COSMOS_ENDPOINT must be configured for cosmos storage")
        from azure.core import MatchConditions
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        credential = os.environ.get("COSMOS_KEY") or DefaultAzureCredential(
            managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID"))
        client = CosmosClient(endpoint, credential=credential, consistency_level="Session",
                              connection_timeout=3, request_timeout=5, retry_total=2)
        container = client.get_database_client(os.environ.get("COSMOS_DATABASE", "gamjaba")).get_container_client(
            os.environ.get("COSMOS_CONTAINER", "state"))
        return cls(container, settings.session_ttl, settings.proposal_ttl,
                   settings.max_sessions, match_condition=MatchConditions.IfNotModified)

    def _read(self, item: str, partition: str) -> dict | None:
        try:
            return self.container.read_item(item=item, partition_key=partition)
        except Exception as error:
            if getattr(error, "status_code", None) == 404:
                return None
            raise StoreError(503, "저장소 연결을 확인해 주세요.") from None

    def _write(self, previous: dict | None, body: dict) -> bool:
        if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > 1900000:
            raise StoreError(409, "과원 저장 용량에 도달했습니다.")
        try:
            if previous is None:
                self.container.create_item(body=body)
            else:
                # Never replace without an observed ETag, including under fake transports.
                self.container.replace_item(item=body["id"], body=body,
                                            etag=previous["_etag"],
                                            match_condition=self.match_condition)
            return True
        except Exception as error:
            if getattr(error, "status_code", None) in (409, 412):
                return False
            raise StoreError(503, "저장소에 저장하지 못했습니다. 다시 시도해 주세요.") from None

    def _directory(self) -> dict:
        return self._read("sessions", self.DIRECTORY) or {
            "id": "sessions", "farmId": self.DIRECTORY, "ttl": -1, "sessions": {}}

    def _session_info(self, session_id: str) -> dict:
        info = self._directory()["sessions"].get(session_id)
        if info is None or info["expires"] <= self.clock():
            raise StoreError(409, "세션이 만료되었습니다. 데모를 다시 시작해 주세요.")
        return info

    def touch(self, session_id: str) -> Session:
        for _ in range(12):
            document = self._directory()
            previous = document if "_etag" in document else None
            body = deepcopy(document)
            now = self.clock()
            body["sessions"] = {key: value for key, value in body["sessions"].items()
                                if value["expires"] > now}
            info = body["sessions"].get(session_id)
            if info is None:
                if len(body["sessions"]) >= self.max_sessions:
                    raise StoreError(503, "데모 이용자가 많습니다. 잠시 후 다시 시도해 주세요.")
                info = {"generation": str(uuid4()), "farms": ["demo"], "expires": now + self.session_ttl}
                body["sessions"][session_id] = info
            info["expires"] = now + self.session_ttl
            if self._write(previous, body):
                break
        else:
            raise StoreError(409, "동시 요청이 많습니다. 다시 시도해 주세요.")
        # Physical TTL has a grace period; authorization always uses the exact idle expiry
        # and generation above. Refresh every owned farm on activity in any farm.
        for farm_id in info["farms"]:
            self._run(session_id, farm_id, lambda memory: None, write=True)
        with self.lock:
            for key in [k for k, v in self.sessions.items() if v.expires <= now]:
                del self.sessions[key]
            local = self.sessions.setdefault(session_id, Session(info["expires"]))
            local.expires = info["expires"]
            return local

    @staticmethod
    def _decode(payload: dict, expires: float) -> Session:
        result = Session(expires)
        for name in ("deadlines", "farms", "revisions", "histories"):
            setattr(result, name, deepcopy(payload.get(name, {})))
        for name, schema in (("proposals", Proposal), ("events", CalendarEvent),
                             ("logs", LogEntry), ("cache", Today)):
            setattr(result, name, {k: schema.model_validate(v) for k, v in payload.get(name, {}).items()})
        return result

    @staticmethod
    def _encode(session: Session) -> dict:
        result = {}
        for field in fields(Session):
            name = field.name
            if name in ("today_lock", "expires", "history"):
                continue
            value = getattr(session, name)
            result[name] = {k: v.model_dump(mode="json") if hasattr(v, "model_dump") else deepcopy(v)
                            for k, v in value.items()}
        return result

    def _run(self, session_id: str, farm_id: str, operation, write=False):
        for _ in range(12):
            info = self._session_info(session_id)
            if farm_id not in info["farms"]:
                raise StoreError(404, "과원을 찾을 수 없습니다.")
            item_id = f'{session_id}:{info["generation"]}'
            previous = self._read(item_id, farm_id)
            if previous is None and farm_id != "demo":
                raise StoreError(404, "과원을 찾을 수 없습니다.")
            memory = MemoryStore(self.session_ttl, self.proposal_ttl, clock=self.clock)
            memory.sessions[session_id] = self._decode(previous["state"] if previous else {}, info["expires"])
            result = operation(memory)
            if not write:
                return result
            current = self._session_info(session_id)
            if current["generation"] != info["generation"]:
                raise StoreError(409, "세션이 만료되었습니다.")
            body = {"id": item_id, "farmId": farm_id, "sessionId": session_id,
                    "generation": info["generation"], "ttl": self.session_ttl * 2,
                    "state": self._encode(memory.sessions[session_id])}
            if self._write(previous, body):
                return result
        raise StoreError(409, "동시 변경이 많습니다. 다시 시도해 주세요.")

    def farm(self, session_id: str, farm_id: str) -> dict:
        return self._run(session_id, farm_id, lambda m: m.farm(session_id, farm_id))

    def create_farm(self, session_id: str, value: FarmInput) -> dict:
        info = self._session_info(session_id)
        memory = MemoryStore(clock=self.clock)
        memory.touch(session_id)
        farm = memory.create_farm(session_id, value)
        body = {"id": f'{session_id}:{info["generation"]}', "farmId": farm["id"],
                "sessionId": session_id, "generation": info["generation"], "ttl": self.session_ttl * 2,
                "state": self._encode(memory.sessions[session_id])}
        if not self._write(None, body):
            raise StoreError(409, "과원을 다시 등록해 주세요.")
        for _ in range(12):
            document = self._directory()
            updated = deepcopy(document)
            current = updated["sessions"].get(session_id)
            if not current or current["expires"] <= self.clock() or current["generation"] != info["generation"]:
                raise StoreError(409, "세션이 만료되었습니다.")
            if len(current["farms"]) >= 21:
                raise StoreError(409, "과원 등록 한도에 도달했습니다.")
            current["farms"].append(farm["id"])
            if self._write(document, updated):
                return farm
        # Unindexed aggregates are inaccessible and expire by TTL.
        raise StoreError(409, "동시 변경이 많습니다. 다시 시도해 주세요.")

    def logs(self, session_id: str, farm_id: str) -> list[LogEntry]:
        return self._run(session_id, farm_id, lambda m: m.logs(session_id, farm_id))

    def add_log(self, session_id: str, farm_id: str, value: LogInput) -> LogEntry:
        return self._run(session_id, farm_id, lambda m: m.add_log(session_id, farm_id, value), True)

    def update_log(self, session_id: str, farm_id: str, log_id: str, value: LogInput) -> LogEntry:
        return self._run(session_id, farm_id, lambda m: m.update_log(session_id, farm_id, log_id, value), True)

    def delete_log(self, session_id: str, farm_id: str, log_id: str) -> None:
        self._run(session_id, farm_id, lambda m: m.delete_log(session_id, farm_id, log_id), True)

    def publish(self, session_id: str, proposals: list[Proposal]) -> list[Proposal]:
        if not proposals:
            self._session_info(session_id)
            return []
        if len({p.farmId for p in proposals}) != 1:
            raise StoreError(409, "한 과원의 제안만 함께 등록할 수 있습니다.")
        return self._run(session_id, proposals[0].farmId, lambda m: m.publish(session_id, proposals), True)

    def decide(self, session_id: str, proposal_id: str, action: str) -> CalendarEvent | Proposal:
        info = self._session_info(session_id)
        for farm_id in info["farms"]:
            found = self._run(session_id, farm_id, lambda m: proposal_id in m.sessions[session_id].proposals)
            if found:
                return self._run(session_id, farm_id, lambda m: m.decide(session_id, proposal_id, action), True)
        raise StoreError(404, "제안을 찾을 수 없습니다.")

    def calendar(self, session_id: str, farm_id: str) -> list[CalendarEvent]:
        return self._run(session_id, farm_id, lambda m: m.calendar(session_id, farm_id))

    def history(self, session_id: str, farm_id: str = "demo") -> list[dict[str, str]]:
        return self._run(session_id, farm_id, lambda m: m.history(session_id, farm_id))

    def remember(self, session_id: str, question: str, answer: str, farm_id: str = "demo") -> None:
        self._run(session_id, farm_id, lambda m: m.remember(session_id, question, answer, farm_id), True)

    def revision(self, session_id: str, farm_id: str) -> int:
        return self._run(session_id, farm_id, lambda m: m.revision(session_id, farm_id))

    def cached(self, session_id: str, key: str) -> Today | None:
        return self._run(session_id, key.split(":", 1)[0], lambda m: m.cached(session_id, key))

    def cache(self, session_id: str, key: str, value: Today, revision: int | None = None) -> None:
        self._run(session_id, value.farmId, lambda m: m.cache(session_id, key, value, revision), True)
