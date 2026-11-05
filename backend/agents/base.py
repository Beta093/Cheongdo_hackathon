from typing import Protocol

from backend.app.schemas import ChatImage
from backend.tools.context import ToolContext


class Model(Protocol):
    mode: str

    async def generate(self, prompt: str, context: ToolContext,
                       image: ChatImage | None = None) -> str: ...
