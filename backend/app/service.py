import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from backend.agents.base import Model
from backend.app.knowledge import KnowledgeBase
from backend.app.policy import BLOCKED, UNCERTAIN, PolicyError, check_text, validate_sources
from backend.app.schemas import ChatImage, ModelOutput, Notice, Task, Today
from backend.app.settings import Settings
from backend.app.store import StoreError
from backend.app.repository import Repository
from backend.app.weather import WeatherClient, WeatherService
from backend.tools.context import ToolContext


class InvalidModelJSON(Exception):
    pass


class AssistantService:
    def __init__(self, settings: Settings, store: Repository, model: Model,
                 weather: WeatherClient | None = None):
        self.settings = settings
        self.store = store
        self.model = model
        self.knowledge = KnowledgeBase(settings.knowledge_dir)
        self.slots = asyncio.Semaphore(settings.max_model_concurrency)
        self.weather = WeatherService(weather, settings.weather_timeout)

    async def _generate(self, session_id: str, mode: str, question: str,
                        queue: asyncio.Queue | None = None,
                        farm_id: str = "demo", image: ChatImage | None = None) -> tuple[ModelOutput, ToolContext]:
        async with self.slots:
            for attempt in range(2):
                snapshot = {"farm": {key: value for key, value in self.store.farm(session_id, farm_id).items()
                                     if key != "sessionId"},
                            "logs": [item.model_dump(mode="json", exclude={"sessionId"}) for item in
                                     self.store.logs(session_id, farm_id)[:30]],
                            "calendar": [item.model_dump(mode="json", exclude={"sessionId"}) for item in
                                         self.store.calendar(session_id, farm_id)]}
                context = ToolContext(self.knowledge, session_id, farm_id, mode, queue,
                                      snapshot, self.weather)
                await context.get_weather(snapshot["farm"]["region"], 3)
                month = context.today.month
                season = "봄" if month in (3, 4, 5) else "여름" if month in (6, 7, 8) else (
                    "가을" if month in (9, 10, 11) else "겨울")
                prompt = json.dumps({
                    "mode": mode, "date": context.today.isoformat(), "timezone": "Asia/Seoul",
                    "season": season, "untrusted_farm_context": snapshot,
                    "weather": context.weather_result, "measurements": None,
                    "untrusted_user_input": question,
                    "untrusted_recent_conversation": self.store.history(session_id, farm_id) if mode == "chat" else [],
                    "format_retry": bool(attempt),
                }, ensure_ascii=False)
                if image is None:
                    raw = await self.model.generate(prompt, context)
                else:
                    raw = await self.model.generate(prompt, context, image=image)
                try:
                    if not isinstance(raw, str) or len(raw) > 20000:
                        raise InvalidModelJSON()
                    result = ModelOutput.model_validate_json(raw)
                except (ValidationError, InvalidModelJSON):
                    if attempt == 0:
                        # Discard the entire attempt, including found source IDs and proposals.
                        await asyncio.sleep(0.1)
                        continue
                    raise InvalidModelJSON() from None
                return result, context
        raise InvalidModelJSON()

    def _validate(self, output: ModelOutput, context: ToolContext) -> tuple[list, list[Task]]:
        check_text(output.answer)

        def weather_guard(text: str) -> None:
            # Forecasts are shown in a separate validated field. Free-form weather-based
            # advice is conservatively disallowed when forecasts could not be obtained.
            if not context.weather_result["available"]:
                stripped = text.replace("날씨 정보 없음", "")
                if re.search(r"날씨|예보|강수|기온|습도|풍속|맑|흐림|서리|우천|폭우|가뭄|"
                             r"(?<![가-힣])비(?:가|는|로|\s+소식)", stripped):
                    raise PolicyError("weather_without_data")
        weather_guard(output.answer)
        sources = validate_sources(output.source_ids, context.found) if output.source_ids else []
        tasks = []
        for draft in output.tasks:
            check_text(draft.reason)
            weather_guard(draft.title + draft.reason)
            task_sources = context.check_task(draft.title, draft.source_ids)
            tasks.append(Task(title=draft.title, reason=draft.reason, sources=task_sources))
        for pending in context.pending:
            context.check_task(pending.event.title, [source.id for source in pending.event.sources])
            check_text(pending.event.reason)
            weather_guard(pending.event.title + pending.event.reason)
        if context.pending and not sources:
            raise PolicyError("proposal_without_grounded_answer")
        return sources, tasks

    async def today(self, session_id: str, farm_id: str = "demo") -> Today:
        day = datetime.now(ZoneInfo("Asia/Seoul")).date()
        key = f"{farm_id}:{day.isoformat()}"
        session = self.store.touch(session_id)
        # Single flight within a session; cache never shares personalized output across sessions.
        async with asyncio.timeout(self.settings.model_timeout):
            async with session.today_lock:
                cached = self.store.cached(session_id, key)
                if cached is not None:
                    return cached
                revision = self.store.revision(session_id, farm_id)
                weather_summary = "날씨 정보 없음"
                try:
                    output, context = await self._generate(session_id, "today", "오늘 수확 곶감 준비 확인",
                                                           farm_id=farm_id)
                    _, tasks = self._validate(output, context)
                    completed = {item.note for item in self.store.logs(session_id, farm_id)
                                 if item.type == "work" and item.date == day}
                    scheduled = {item.title for item in self.store.calendar(session_id, farm_id)
                                 if item.date == day}
                    tasks = [task for task in tasks if task.title not in completed | scheduled]
                    weather_summary = context.weather_result["summary"]
                    notices = [] if tasks else [Notice(text=UNCERTAIN)]
                except InvalidModelJSON:
                    tasks, notices = [], [Notice(text="응답 형식을 확인하지 못했습니다. " + UNCERTAIN)]
                result = Today(farmId=farm_id, date=day, tasks=tasks, notices=notices, weather=weather_summary,
                               model_mode=self.model.mode)
                self.store.cache(session_id, key, result, revision)
                return result

    async def _chat_work(self, session_id: str, question: str, queue: asyncio.Queue,
                         farm_id: str = "demo", image: ChatImage | None = None) -> None:
        succeeded = False
        try:
            async with asyncio.timeout(self.settings.model_timeout):
                output, context = await self._generate(session_id, "chat", question, queue, farm_id, image)
                sources, _ = self._validate(output, context)
                # Unsupported model prose is replaced by a fixed uncertainty notice.
                answer = output.answer if sources else UNCERTAIN
                if image:
                    answer += " 사진만으로 확정할 수 없음, 농업기술센터 확인 필요."
                proposals = self.store.publish(session_id, context.pending)
                self.store.remember(session_id, question, answer, farm_id)
                queue.put_nowait(("message", {
                    "text": answer, "sources": [source.model_dump() for source in sources],
                    "evidence": "근거 있음" if sources else "확인 필요", "ai_generated": True,
                    "model_mode": self.model.mode, "weather": context.weather_result["summary"],
                    "proposals": [item.model_dump(mode="json") for item in proposals],
                }))
                succeeded = True
        except PolicyError:
            queue.put_nowait(("error", {"code": "policy_blocked", "text": BLOCKED, "retryable": False}))
        except InvalidModelJSON:
            queue.put_nowait(("message", {"text": "응답 형식을 확인하지 못했습니다. " + UNCERTAIN,
                                           "sources": [], "proposals": [], "evidence": "확인 필요",
                                           "ai_generated": True, "model_mode": self.model.mode}))
            succeeded = True
        except StoreError as error:
            queue.put_nowait(("error", {"code": "session_error", "text": error.message, "retryable": False}))
        except Exception:
            # Do not log exception text: SDK errors may contain credentials or user data.
            queue.put_nowait(("error", {"code": "model_unavailable", "retryable": True,
                                       "text": "모델 응답이 지연되거나 연결되지 않았습니다. 잠시 후 다시 시도해 주세요."}))
        finally:
            queue.put_nowait(("done", {"ok": succeeded}))

    async def chat(self, session_id: str, question: str, farm_id: str = "demo",
                   image: ChatImage | None = None):
        yield self._sse("status", {"text": "자료를 확인하고 있습니다.", "model_mode": self.model.mode})
        queue: asyncio.Queue = asyncio.Queue()
        worker = asyncio.create_task(self._chat_work(session_id, question, queue, farm_id, image))
        try:
            while True:
                try:
                    name, data = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield self._sse(name, data)
                if name == "done":
                    break
        finally:
            if not worker.done():
                worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    @staticmethod
    def _sse(name: str, data: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
