from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatInput(StrictModel):
    message: str = Field(min_length=1, max_length=2000)


class Source(StrictModel):
    id: str
    source_title: str
    source_url: str
    retrieved_at: str
    reviewed: bool = False


class TaskDraft(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=600)
    source_ids: list[str] = Field(min_length=1, max_length=8)


class ModelOutput(StrictModel):
    answer: str = Field(min_length=1, max_length=4000)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    tasks: list[TaskDraft] = Field(default_factory=list, max_length=5)


class EventDraft(TaskDraft):
    date: date


class Task(StrictModel):
    title: str
    reason: str
    sources: list[Source]
    evidence: Literal["근거 있음"] = "근거 있음"
    ai_generated: bool = True


class CalendarEvent(Task):
    id: str
    farmId: str
    sessionId: str
    date: date


class Proposal(StrictModel):
    id: str
    farmId: str
    sessionId: str
    event: CalendarEvent
    status: Literal["pending", "approved", "rejected"] = "pending"
    createdAt: datetime
    expiresAt: datetime
    ttl: int
    ai_generated: bool = True


class Notice(StrictModel):
    text: str
    evidence: Literal["확인 필요"] = "확인 필요"
    ai_generated: bool = True


class Today(StrictModel):
    farmId: str
    date: date
    tasks: list[Task]
    notices: list[Notice]
    weather: str = "날씨 정보 없음"
    ai_generated: bool = True
    model_mode: str
