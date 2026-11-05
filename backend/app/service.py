import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from backend.agents.base import Model
from backend.app.knowledge import KnowledgeBase
from backend.app.policy import BLOCKED, UNCERTAIN, PolicyError, check_text, validate_sources
from backend.app.schemas import ModelOutput, Notice, Task, Today
from backend.app.settings import Settings
from backend.app.store import MemoryStore, StoreError
from backend.tools.context import ToolContext


class InvalidModelJSON(Exception):
    pass


class AssistantService:
    def __init__(self, settings: Settings, store: MemoryStore, model: Model):
        self.settings = settings
        self.store = store
        self.model = model
        self.knowledge = KnowledgeBase(settings.knowledge_dir)
        self.slots = asyncio.Semaphore(settings.max_model_concurrency)

    async def _generate(self, session_id: str, mode: str, question: str,
                        queue: asyncio.Queue | None = None) -> tuple[ModelOutput, ToolContext]:
        async with self.slots:
            for attempt in range(2):
                context = ToolContext(self.knowledge, session_id, "demo", mode, queue)
                month = context.today.month
                season = "봄" if month in (3, 4, 5) else "여름" if month in (6, 7, 8) else (
                    "가을" if month in (9, 10, 11) else "겨울")
                prompt = json.dumps({
                    "mode": mode, "date": context.today.isoformat(), "timezone": "Asia/Seoul",
                    "season": season, "farm": {"id": "demo", "cultivar": "청도반시", "region": "청도군"},
                    "weather": "날씨 정보 없음", "measurements": None,
                    "untrusted_user_input": question,
                    "untrusted_recent_conversation": self.store.history(session_id) if mode == "chat" else [],
                    "format_retry": bool(attempt),
                }, ensure_ascii=False)
                raw = await self.model.generate(prompt, context)
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
        sources = validate_sources(output.source_ids, context.found) if output.source_ids else []
        tasks = []
        for draft in output.tasks:
            check_text(draft.reason)
            task_sources = context.check_task(draft.title, draft.source_ids)
            tasks.append(Task(title=draft.title, reason=draft.reason, sources=task_sources))
        for pending in context.pending:
            context.check_task(pending.event.title, [source.id for source in pending.event.sources])
            check_text(pending.event.reason)
        if context.pending and not sources:
            raise PolicyError("proposal_without_grounded_answer")
        return sources, tasks

    async def today(self, session_id: str) -> Today:
        day = datetime.now(ZoneInfo("Asia/Seoul")).date()
        key = f"demo:{day.isoformat()}"
        session = self.store.touch(session_id)
        # Single flight within a session; cache never shares personalized output across sessions.
        async with asyncio.timeout(self.settings.model_timeout):
            async with session.today_lock:
                cached = self.store.cached(session_id, key)
                if cached is not None:
                    return cached
                try:
                    output, context = await self._generate(session_id, "today", "오늘 수확 곶감 준비 확인")
                    _, tasks = self._validate(output, context)
                    notices = [] if tasks else [Notice(text=UNCERTAIN)]
                except InvalidModelJSON:
                    tasks, notices = [], [Notice(text="응답 형식을 확인하지 못했습니다. " + UNCERTAIN)]
                result = Today(farmId="demo", date=day, tasks=tasks, notices=notices,
                               model_mode=self.model.mode)
                self.store.cache(session_id, key, result)
                return result

    async def _chat_work(self, session_id: str, question: str, queue: asyncio.Queue) -> None:
        succeeded = False
        try:
            async with asyncio.timeout(self.settings.model_timeout):
                output, context = await self._generate(session_id, "chat", question, queue)
                sources, _ = self._validate(output, context)
                # Unsupported model prose is replaced by a fixed uncertainty notice.
                answer = output.answer if sources else UNCERTAIN
                proposals = self.store.publish(session_id, context.pending)
                self.store.remember(session_id, question, answer)
                queue.put_nowait(("message", {
                    "text": answer, "sources": [source.model_dump() for source in sources],
                    "evidence": "근거 있음" if sources else "확인 필요", "ai_generated": True,
                    "model_mode": self.model.mode, "weather": "날씨 정보 없음",
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

    async def chat(self, session_id: str, question: str):
        yield self._sse("status", {"text": "자료를 확인하고 있습니다.", "model_mode": self.model.mode})
        queue: asyncio.Queue = asyncio.Queue()
        worker = asyncio.create_task(self._chat_work(session_id, question, queue))
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
