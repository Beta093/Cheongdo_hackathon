import asyncio
import json

from backend.app.policy import UNCERTAIN
from backend.tools.context import ToolContext


class FakeModel:
    """Deterministic offline fixture, clearly distinguished from a real model."""

    mode = "fake"

    def __init__(self, raw_output: str | None = None, fail: bool = False, delay: float = 0):
        self.raw_output = raw_output
        self.fail = fail
        self.delay = delay
        self.calls = 0

    async def generate(self, prompt: str, context: ToolContext) -> str:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("sensitive-error")
        results = context.search_knowledge("수확 곶감 준비")["results"]
        if self.raw_output is not None:
            return self.raw_output
        checked = [entry for entry in results if entry["reviewed"]]
        if not checked:
            return json.dumps({"answer": UNCERTAIN, "source_ids": [], "tasks": []}, ensure_ascii=False)
        entry = checked[0]
        title = entry["task_title"]
        reason = entry["content"][:500]
        task = {"title": title, "reason": reason, "source_ids": [entry["id"]]}
        data = json.loads(prompt)
        if context.mode == "chat" and "일정" in data["untrusted_user_input"]:
            context.propose_calendar_event(title, context.today.isoformat(), reason, [entry["id"]])
        return json.dumps({"answer": reason, "source_ids": [entry["id"]],
                           "tasks": [task] if context.mode == "today" else []}, ensure_ascii=False)
