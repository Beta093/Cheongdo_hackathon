import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable

from backend.app.schemas import CalendarEvent, Proposal, Today


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
            if len(session.proposals) + len(proposals) > 100:
                raise StoreError(409, "세션의 제안 한도에 도달했습니다.")
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
                return session.events[item.event.id].model_copy(deep=True)
            if action != "reject":
                raise StoreError(400, "올바르지 않은 처리입니다.")
            item.status = "rejected"
            return item.model_copy(deep=True)

    def calendar(self, session_id: str, farm_id: str) -> list[CalendarEvent]:
        with self.lock:
            session = self._session(session_id)
            return sorted([event.model_copy(deep=True) for event in session.events.values()
                           if event.farmId == farm_id], key=lambda event: (event.date, event.id))

    def history(self, session_id: str) -> list[dict[str, str]]:
        with self.lock:
            return [dict(turn) for turn in self._session(session_id).history]

    def remember(self, session_id: str, question: str, answer: str) -> None:
        with self.lock:
            session = self._session(session_id)
            session.history = (session.history + [{"user": question, "assistant": answer}])[-4:]

    def cached(self, session_id: str, key: str) -> Today | None:
        with self.lock:
            value = self._session(session_id).cache.get(key)
            return value.model_copy(deep=True) if value else None

    def cache(self, session_id: str, key: str, value: Today) -> None:
        with self.lock:
            self._session(session_id).cache = {key: value.model_copy(deep=True)}
