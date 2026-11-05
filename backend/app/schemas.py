import base64
import binascii
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FarmInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    cultivar: Literal["청도반시"] = "청도반시"
    region: Literal["청도읍", "화양읍", "각남면", "각북면", "금천면", "매전면", "운문면", "이서면", "풍각면"]
    plantedYear: int = Field(strict=True, ge=1900)
    areaM2: float = Field(gt=0, le=10000000, allow_inf_nan=False, strict=True)

    @field_validator("plantedYear")
    @classmethod
    def planting_year(cls, value: int) -> int:
        if value > datetime.now(ZoneInfo("Asia/Seoul")).year:
            raise ValueError("식재 연도는 올해까지 입력할 수 있습니다.")
        return value


class LogInput(StrictModel):
    type: Literal["work", "symptom", "harvest"]
    date: date
    note: str = Field(min_length=1, max_length=2000)
    amount: float | None = Field(default=None, gt=0, le=10000000,
                                 allow_inf_nan=False, strict=True)

    @field_validator("date", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if not isinstance(value, (str, date)) or isinstance(value, datetime):
            raise ValueError("날짜를 입력하세요.")
        if isinstance(value, str):
            if len(value) != 10 or value[4] != "-" or value[7] != "-":
                raise ValueError("날짜는 YYYY-MM-DD 형식입니다.")
            value = date.fromisoformat(value)
        if not date(1900, 1, 1) <= value <= datetime.now(ZoneInfo("Asia/Seoul")).date():
            raise ValueError("기록 날짜는 1900년부터 오늘까지입니다.")
        return value

    @model_validator(mode="after")
    def harvest_amount(self):
        if (self.type == "harvest") != (self.amount is not None):
            raise ValueError("수확 기록에만 양수 수확량(kg)을 입력하세요.")
        return self


class LogEntry(LogInput):
    id: str
    farmId: str
    sessionId: str


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BASE64 = 4 * ((MAX_IMAGE_BYTES + 2) // 3)


class ChatImage(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    mimeType: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(min_length=1, max_length=MAX_IMAGE_BASE64, repr=False)

    @model_validator(mode="after")
    def validate_image(self):
        try:
            raw = base64.b64decode(self.data, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("사진 인코딩을 확인해 주세요.") from None
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("사진은 5MB 이하만 첨부할 수 있습니다.")
        valid = {
            "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
            "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
        }
        if not valid[self.mimeType]:
            raise ValueError("사진 형식과 내용을 확인해 주세요.")
        return self


class ChatInput(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    image: ChatImage | None = None


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
