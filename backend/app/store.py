import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable
from uuid import uuid4
from copy import deepcopy

from backend.app.schemas import CalendarEvent, FarmInput, LogInput, LogEntry, Proposal, Today
from backend.app.repository import DEMO_FARM


class StoreError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


@dataclass
class Session:
    expires: float
    proposals: dict[str, Proposal] = field(default_factory=dict)
    deadlines: dict[str, float] = field(default_factory=dict)
    events: dict[str, CalendarEvent] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    cache: dict[str, Today] = field(default_factory=dict)
    today_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    farms: dict[str, dict] = field(default_factory=dict)
    logs: dict[str, LogEntry] = field(default_factory=dict)
    revisions: dict[str, int] = field(default_factory=dict)
    histories: dict[str, list[dict[str, str]]] = field(default_factory=dict)


class MemoryStore:
    def __init__(self, session_ttl: int = 7200, proposal_ttl: int = 1800,
                 max_sessions: int = 1000, clock: Callable[[], float] = time.monotonic):
        self.session_ttl = session_ttl
        self.proposal_ttl = proposal_ttl
        self.max_sessions = max_sessions
        self.clock = clock
        self.sessions: dict[str, Session] = {}
        self.lock = RLock()

    def touch(self, session_id: str) -> Session:
        with self.lock:
            now = self.clock()
            for key in [key for key, value in self.sessions.items() if value.expires <= now]:
                del self.sessions[key]
            if session_id not in self.sessions:
                if len(self.sessions) >= self.max_sessions:
                    raise StoreError(503, "데모 이용자가 많습니다. 잠시 후 다시 시도해 주세요.")
                self.sessions[session_id] = Session(now + self.session_ttl)
            session = self.sessions[session_id]
            session.expires = now + self.session_ttl
            return session

    def _session(self, session_id: str) -> Session:
        session = self.sessions.get(session_id)
        if session is None or session.expires <= self.clock():
            raise StoreError(409, "세션이 만료되었습니다. 데모를 다시 시작해 주세요.")
        return session

    def publish(self, session_id: str, proposals: list[Proposal]) -> list[Proposal]:
        with self.lock:
            session = self._session(session_id)
            for item in proposals:
                self.farm(session_id, item.farmId)
                if item.event.farmId != item.farmId or item.event.sessionId != session_id:
                    raise StoreError(409, "올바르지 않은 제안입니다.")
            farm_ids = {p.farmId for p in proposals}
            if len(farm_ids) > 1:
                raise StoreError(409, "한 과원의 제안만 함께 등록할 수 있습니다.")
            if sum(p.farmId in farm_ids for p in session.proposals.values()) + len(proposals) > 100:
                raise StoreError(409, "과원의 제안 한도에 도달했습니다.")
            # Validate the entire batch before any write.
            if any(p.sessionId != session_id or p.status != "pending" or p.id in session.proposals
                   for p in proposals):
                raise StoreError(409, "올바르지 않은 제안입니다.")
            now = datetime.now(timezone.utc)
            saved = [p.model_copy(update={"createdAt": now, "expiresAt": now + timedelta(
                seconds=self.proposal_ttl), "ttl": self.proposal_ttl}, deep=True) for p in proposals]
            for item in saved:
                session.proposals[item.id] = item
                session.deadlines[item.id] = self.clock() + self.proposal_ttl
            return [item.model_copy(deep=True) for item in saved]

    def decide(self, session_id: str, proposal_id: str, action: str) -> CalendarEvent | Proposal:
        with self.lock:
            session = self._session(session_id)
            item = session.proposals.get(proposal_id)
            if item is None:
                raise StoreError(404, "제안을 찾을 수 없습니다.")
            if item.status == "approved" and action == "approve":
                return session.events[item.event.id].model_copy(deep=True)
            if item.status == "rejected" and action == "reject":
                return item.model_copy(deep=True)
            if item.status != "pending":
                raise StoreError(409, "이미 처리된 제안입니다.")
            if session.deadlines[item.id] <= self.clock():
                raise StoreError(409, "제안이 만료되었습니다. 새로 요청해 주세요.")
            if action == "approve":
                session.events[item.event.id] = item.event.model_copy(deep=True)
                item.status = "approved"
                self._invalidate(session, item.farmId)
                return session.events[item.event.id].model_copy(deep=True)
            if action != "reject":
                raise StoreError(400, "올바르지 않은 처리입니다.")
            item.status = "rejected"
            return item.model_copy(deep=True)

    def calendar(self, session_id: str, farm_id: str) -> list[CalendarEvent]:
        with self.lock:
            self.farm(session_id, farm_id)
            session = self._session(session_id)
            return sorted([event.model_copy(deep=True) for event in session.events.values()
                           if event.farmId == farm_id], key=lambda event: (event.date, event.id))

    def history(self, session_id: str, farm_id: str = "demo") -> list[dict[str, str]]:
        with self.lock:
            self.farm(session_id, farm_id)
            return deepcopy(self._session(session_id).histories.get(farm_id, []))

    def remember(self, session_id: str, question: str, answer: str, farm_id: str = "demo") -> None:
        with self.lock:
            self.farm(session_id, farm_id)
            session = self._session(session_id)
            session.histories[farm_id] = (session.histories.get(farm_id, []) + [
                {"user": question, "assistant": answer}])[-4:]

    def cached(self, session_id: str, key: str) -> Today | None:
        with self.lock:
            value = self._session(session_id).cache.get(key)
            return value.model_copy(deep=True) if value else None

    def cache(self, session_id: str, key: str, value: Today, revision: int | None = None) -> None:
        with self.lock:
            session = self._session(session_id)
            if revision is None or revision == session.revisions.get(value.farmId, 0):
                session.cache = {k: v for k, v in session.cache.items()
                                 if v.farmId != value.farmId}
                session.cache[key] = value.model_copy(deep=True)

    def farm(self, session_id: str, farm_id: str) -> dict:
        with self.lock:
            session = self._session(session_id)
            if farm_id == "demo":
                return {**DEMO_FARM, "sessionId": session_id}
            farm = session.farms.get(farm_id)
            if farm is None:
                raise StoreError(404, "과원을 찾을 수 없습니다.")
            return deepcopy(farm)

    def create_farm(self, session_id: str, value: FarmInput) -> dict:
        with self.lock:
            session = self._session(session_id)
            if len(session.farms) >= 20:
                raise StoreError(409, "과원 등록 한도에 도달했습니다.")
            farm_id = str(uuid4())
            farm = {**value.model_dump(), "id": farm_id, "farmId": farm_id,
                    "sessionId": session_id, "isDemo": False,
                    "weather": "날씨 정보 없음", "measurements": "현장 측정 정보 없음"}
            session.farms[farm_id] = farm
            return deepcopy(farm)

    def logs(self, session_id: str, farm_id: str) -> list[LogEntry]:
        with self.lock:
            self.farm(session_id, farm_id)
            return sorted([item.model_copy(deep=True) for item in self._session(session_id).logs.values()
                           if item.farmId == farm_id], key=lambda item: (item.date, item.id), reverse=True)

    def add_log(self, session_id: str, farm_id: str, value: LogInput) -> LogEntry:
        with self.lock:
            self.farm(session_id, farm_id)
            session = self._session(session_id)
            if len(self.logs(session_id, farm_id)) >= 200:
                raise StoreError(409, "과원의 기록 한도에 도달했습니다.")
            item = LogEntry(**value.model_dump(), id=str(uuid4()), farmId=farm_id, sessionId=session_id)
            session.logs[item.id] = item
            self._invalidate(session, farm_id)
            return item.model_copy(deep=True)

    def revision(self, session_id: str, farm_id: str) -> int:
        with self.lock:
            self.farm(session_id, farm_id)
            return self._session(session_id).revisions.get(farm_id, 0)

    def update_log(self, session_id: str, farm_id: str, log_id: str, value: LogInput) -> LogEntry:
        with self.lock:
            self._log(session_id, farm_id, log_id)
            session = self._session(session_id)
            item = LogEntry(**value.model_dump(), id=log_id, farmId=farm_id, sessionId=session_id)
            session.logs[log_id] = item
            self._invalidate(session, farm_id)
            return item.model_copy(deep=True)

    def delete_log(self, session_id: str, farm_id: str, log_id: str) -> None:
        with self.lock:
            self._log(session_id, farm_id, log_id)
            session = self._session(session_id)
            del session.logs[log_id]
            self._invalidate(session, farm_id)

    def _log(self, session_id: str, farm_id: str, log_id: str) -> LogEntry:
        self.farm(session_id, farm_id)
        item = self._session(session_id).logs.get(log_id)
        if item is None or item.farmId != farm_id:
            raise StoreError(404, "기록을 찾을 수 없습니다.")
        return item

    @staticmethod
    def _invalidate(session: Session, farm_id: str) -> None:
        session.revisions[farm_id] = session.revisions.get(farm_id, 0) + 1
        session.cache = {key: value for key, value in session.cache.items() if value.farmId != farm_id}
