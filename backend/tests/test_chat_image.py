import base64
import asyncio
import sys
from types import SimpleNamespace

import pytest

from backend.tests.conftest import events
from backend.agents.copilot import CopilotModel
from backend.agents.permissions import on_permission_request
from backend.app.schemas import ChatImage


def picture(raw=b"\x89PNG\r\n\x1a\nfixture", mime="image/png"):
    return {"mimeType": mime, "data": base64.b64encode(raw).decode()}


@pytest.mark.parametrize("image", [None, picture(), picture(b"\xff\xd8\xfffixture", "image/jpeg"),
                                   picture(b"RIFF\x10\x00\x00\x00WEBPfixture", "image/webp")])
def test_chat_image_and_legacy(client, app, headers, image):
    payload = {"message": "수확 준비 일정 추가"}
    if image:
        payload["image"] = image
    response = client.post("/api/farms/demo/chat", headers=headers, json=payload)
    assert response.status_code == 200
    assert events(response)[-1] == ("done", {"ok": True})
    received = app.state.service.model.last_image
    assert (received.model_dump() if received else None) == image
    assert client.get("/api/farms/demo/calendar", headers=headers).json() == []
    if image:
        assert image["data"] not in response.text


@pytest.mark.parametrize("image", [
    picture(mime="image/gif"), picture(b"not a picture"),
    {"mimeType": "image/png", "data": "%%%"},
    {"mimeType": "image/png", "data": ""},
    picture(b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)),
    picture(b"\xff\xd8\xfffixture", "image/png"),
])
def test_invalid_image(client, headers, image):
    response = client.post("/api/farms/demo/chat", headers=headers,
                           json={"message": "사진 확인", "image": image})
    assert response.status_code == 422
    if image["data"]:
        assert image["data"] not in response.text


def test_maximum_image_size(client, headers):
    image = picture(b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024 - 8))
    response = client.post("/api/farms/demo/chat", headers=headers,
                           json={"message": "사진 확인", "image": image})
    assert response.status_code == 200
    assert events(response)[-1] == ("done", {"ok": True})


def test_other_body_limit_unchanged(client, headers):
    assert client.post("/api/farms", headers=headers, content=b"x" * 17000).status_code == 413


def test_blob_reaches_session(monkeypatch):
    sent = {}

    class Session:
        def on(self, callback):
            self.callback = callback
            return lambda: None

        async def send(self, prompt, *, attachments):
            sent.update(prompt=prompt, attachments=attachments)
            self.callback(SimpleNamespace(type="assistant.message", data=SimpleNamespace(content="answer")))
            self.callback(SimpleNamespace(type="session.idle"))

        async def destroy(self):
            sent["destroyed"] = True

    class Client:
        async def start(self):
            pass

        async def create_session(self, config):
            assert config["on_permission_request"] is on_permission_request
            assert {tool["name"] for tool in config["tools"]} == {
                "search_knowledge", "propose_calendar_event", "get_farm_context", "get_weather"}
            return Session()

        async def stop(self):
            sent["stopped"] = True

    monkeypatch.setitem(sys.modules, "copilot", SimpleNamespace(CopilotClient=Client))
    monkeypatch.setitem(sys.modules, "copilot.types", SimpleNamespace(Tool=dict, ToolResult=dict))
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "test-only")
    image = ChatImage(**picture())
    assert asyncio.run(CopilotModel().generate("question", None, image)) == "answer"
    assert sent["attachments"] == [{"type": "blob", "data": image.data,
                                    "mimeType": "image/png", "displayName": "사진"}]
    assert sent["destroyed"] and sent["stopped"]


def test_image_requires_session(client):
    assert client.post("/api/farms/demo/chat", json={"message": "사진", "image": picture()}).status_code == 422
