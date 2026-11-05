from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.agents.fake import FakeModel
from backend.app.main import create_app
from backend.app.settings import Settings


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    # Synthetic trusted corpus for tests only; never presented as real farm advice.
    (tmp_path / "checked.md").write_text(
        '---\nsource_title: "테스트 검토 자료"\n'
        'source_url: "https://example.org/test-only"\n'
        'retrieved_at: "2026-11-05"\nreviewed: true\n'
        'task_title: "수확 준비 점검"\n---\n'
        '수확 곶감 준비 도구를 점검할 항목을 확인합니다.\n', encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def headers():
    return {"X-Session-Id": str(uuid4())}


@pytest.fixture
def app(knowledge_dir):
    return create_app(Settings(knowledge_dir=knowledge_dir), FakeModel())


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def events(response):
    import json

    parsed = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        parsed.append((name, data))
    return parsed


def proposal(client, headers):
    result = events(client.post("/api/farms/demo/chat", headers=headers,
                                json={"message": "수확 준비 일정 추가"}))
    return next(data["proposals"][0] for name, data in result if name == "message")
