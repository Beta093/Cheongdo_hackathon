import asyncio
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from backend.agents.fake import FakeModel
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.conftest import proposal


FARM = {"name": "우리 과원", "cultivar": "청도반시", "region": "청도읍",
        "plantedYear": 2020, "areaM2": 500}
LOG = {"type": "work", "date": "2026-11-05", "note": "수확 준비 점검"}


@pytest.mark.parametrize("patch", [
    {"name": " "}, {"plantedYear": 1899}, {"plantedYear": 9999},
    {"areaM2": -1}, {"cultivar": "사과"}, {"region": "서울"}, {"plantedYear": True},
])
def test_farm_validation(client, headers, patch):
    assert client.post("/api/farms", headers=headers, json=FARM | patch).status_code == 422


def test_farm_required_fields_and_isolation(client, headers):
    for key in FARM:
        if key == "cultivar":
            continue
        assert client.post("/api/farms", headers=headers,
                           json={k: v for k, v in FARM.items() if k != key}).status_code == 422
    result = client.post("/api/farms", headers=headers, json=FARM)
    assert result.status_code == 201
    farm = result.json()
    assert not farm["isDemo"] and farm["farmId"] == farm["id"]
    other = {"X-Session-Id": str(uuid4())}
    assert client.get(f'/api/farms/{farm["id"]}', headers=headers).json()["name"] == FARM["name"]
    assert client.get(f'/api/farms/{farm["id"]}', headers=other).status_code == 404
    for suffix in ("today", "calendar", "logs", "weather"):
        path = f'/api/farms/{farm["id"]}/{suffix}'
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path, headers=other).status_code == 404
    assert client.post(f'/api/farms/{farm["id"]}/logs', headers=other, json=LOG).status_code == 404


@pytest.mark.parametrize("patch", [
    {"type": "other"}, {"date": "2026-02-30"}, {"date": "tomorrow"},
    {"note": " "}, {"note": "a" * 2001}, {"amount": -1}, {"amount": True},
    {"type": "harvest"}, {"type": "harvest", "amount": 0},
    {"type": "symptom", "amount": 2}, {"date": "9999-01-01"},
])
def test_log_validation(client, headers, patch):
    assert client.post("/api/farms/demo/logs", headers=headers, json=LOG | patch).status_code == 422


def test_logs_and_cache_invalidation(client, app, headers):
    day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    today = "/api/farms/demo/today"
    assert client.get(today, headers=headers).json()["tasks"]
    for kind in ("work", "symptom", "harvest"):
        body = LOG | {"type": kind, "date": day}
        if kind == "harvest":
            body["amount"] = 12.5
        assert client.post("/api/farms/demo/logs", headers=headers, json=body).status_code == 201
    assert len(client.get("/api/farms/demo/logs", headers=headers).json()) == 3
    assert client.get("/api/farms/demo/logs", headers={"X-Session-Id": str(uuid4())}).json() == []
    result = client.get(today, headers=headers).json()
    assert app.state.service.model.calls == 2
    assert result["tasks"] == []  # Today's completed task is not proposed again.
    item = proposal(client, headers)
    client.post(f'/api/proposals/{item["id"]}/approve', headers=headers)
    client.get(today, headers=headers)
    assert app.state.service.model.calls == 4


class FakeWeather:
    def __init__(self, fail=False, delay=0):
        self.fail, self.delay = fail, delay

    async def forecast(self, location, days):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("private-provider-error")
        return {"days": [{"date": "2026-11-05", "minC": 4, "maxC": 15,
                          "rainMm": 0}], "source": "테스트 예보"}


@pytest.mark.parametrize("client_kind", ["ok", "fail", "slow", "unset"])
def test_weather(knowledge_dir, headers, client_kind, monkeypatch):
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    weather = None if client_kind == "unset" else FakeWeather(
        fail=client_kind == "fail", delay=0.1 if client_kind == "slow" else 0)
    app = create_app(Settings(knowledge_dir=knowledge_dir, weather_timeout=0.01),
                     FakeModel(), weather=weather)
    with TestClient(app) as client:
        response = client.get("/api/farms/demo/weather", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is (client_kind == "ok")
        if client_kind != "ok":
            assert data["summary"] == "날씨 정보 없음"
        assert "private-provider-error" not in response.text
        assert client.get("/api/farms/demo/weather?days=0", headers=headers).status_code == 422
