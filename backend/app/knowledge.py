import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from backend.app.schemas import Source


@dataclass(frozen=True)
class Entry:
    source: Source
    task_title: str
    content: str


class KnowledgeBase:
    def __init__(self, directory: Path):
        self.entries: dict[str, Entry] = {}
        for path in sorted(directory.glob("*.md")):
            raw = path.read_text(encoding="utf-8-sig")
            if not raw.startswith("---\n"):
                raise ValueError(f"Missing frontmatter: {path.name}")
            _, header, body = raw.split("---", 2)
            metadata = {}
            # Deliberately small frontmatter subset: flat key: JSON-string / bool.
            for line in header.strip().splitlines():
                key, value = line.split(":", 1)
                value = value.strip()
                metadata[key.strip()] = json.loads(value) if value[:1] == '"' or value in (
                    "true", "false") else value
            source = Source(id=path.stem, **{key: metadata[key] for key in
                            ("source_title", "source_url", "retrieved_at")},
                            reviewed=metadata.get("reviewed") is True)
            if source.reviewed:
                url = urlsplit(source.source_url)
                if url.scheme != "https" or not url.netloc or "확인 필요" in source.source_url:
                    raise ValueError(f"Invalid reviewed URL: {path.name}")
                date.fromisoformat(source.retrieved_at)
            self.entries[source.id] = Entry(source, str(metadata["task_title"]), body.strip())

    def search(self, query: str) -> list[Entry]:
        words = set(re.findall(r"[가-힣a-zA-Z0-9]+", query.lower()))
        ranked = []
        for entry in self.entries.values():
            haystack = f"{entry.task_title} {entry.content}".lower()
            score = sum(word in haystack for word in words)
            if score:
                ranked.append((score, entry))
        return [entry for _, entry in sorted(ranked, key=lambda item: (-item[0], item[1].source.id))[:5]]
