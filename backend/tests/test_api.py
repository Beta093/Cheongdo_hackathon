from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.agents.fake import FakeModel
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.conftest import events, proposal


def test_session_required_and_demo(client, headers):
    assert client.get("/api/health").status_code == 422
    assert client.get("/api/health", headers={"X-Session-Id": "bad"}).status_code == 422
    assert client.get("/api/health", headers=headers).json()["status"] == "ok"
    assert client.get("/api/farms/demo", headers=headers).json()["cultivar"] == "청도반시"
    assert client.get("/api/farms/other/today", headers=headers).status_code == 404


def test_today_cache_and_isolation(client, app, headers):
    first = client.get("/api/farms/demo/today", headers=headers).json()
    second = client.get("/api/farms/demo/today", headers=headers).json()
    assert first == second
    assert app.state.service.model.calls == 1
    assert first["tasks"][0]["ai_generated"] is True
    assert first["tasks"][0]["sources"][0]["id"] == "checked"
    client.get("/api/farms/demo/today", headers={"X-Session-Id": str(uuid4())})
    assert app.state.service.model.calls == 2


def test_concurrent_today_is_single_flight(knowledge_dir, headers):
    model = FakeModel(delay=0.03)
    with TestClient(create_app(Settings(knowledge_dir=knowledge_dir), model)) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: client.get("/api/farms/demo/today", headers=headers), range(4)))
        assert all(result.status_code == 200 for result in results)
        assert model.calls == 1


def test_sse_and_approval(client, headers):
    response = client.post("/api/farms/demo/chat", headers=headers,
                           json={"message": "수확 준비 일정 추가"})
    stream = events(response)
    names = [name for name, _ in stream]
    assert names[0] == "status"
    assert names.count("message") == 1
    assert names[-1] == "done"
    assert names.index("tool_call") < names.index("message")
    item = next(data for name, data in stream if name == "message")
    pending = item["proposals"][0]
    assert pending["status"] == "pending"
    assert client.get("/api/farms/demo/calendar", headers=headers).json() == []
    path = f'/api/proposals/{pending["id"]}/approve'
    first = client.post(path, headers=headers)
    assert first.status_code == 200
    assert client.post(path, headers=headers).json() == first.json()
    assert len(client.get("/api/farms/demo/calendar", headers=headers).json()) == 1


def test_concurrent_approval(client, headers):
    item = proposal(client, headers)
    path = f'/api/proposals/{item["id"]}/approve'
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: client.post(path, headers=headers), range(8)))
    assert all(result.status_code == 200 for result in results)
    assert len({result.json()["id"] for result in results}) == 1
    assert len(client.get("/api/farms/demo/calendar", headers=headers).json()) == 1


def test_sessions_cannot_access_or_decide_others_proposals(client, headers):
    item = proposal(client, headers)
    other = {"X-Session-Id": str(uuid4())}
    for action in ("approve", "reject"):
        assert client.post(f'/api/proposals/{item["id"]}/{action}', headers=other).status_code == 404
    client.post(f'/api/proposals/{item["id"]}/approve', headers=headers)
    assert client.get("/api/farms/demo/calendar", headers=other).json() == []


def test_reject_and_missing(client, headers):
    item = proposal(client, headers)
    path = f'/api/proposals/{item["id"]}'
    assert client.post(path + "/reject", headers=headers).json()["status"] == "rejected"
    assert client.post(path + "/reject", headers=headers).status_code == 200
    assert client.post(path + "/approve", headers=headers).status_code == 409
    assert client.post("/api/proposals/missing/approve", headers=headers).status_code == 404
    assert client.get("/api/farms/demo/calendar", headers=headers).json() == []


def test_input_limits(client, headers):
    for value in ("", "   ", "가" * 2001):
        assert client.post("/api/farms/demo/chat", headers=headers,
                           json={"message": value}).status_code == 422
    assert client.post("/api/farms/demo/chat", headers=headers,
                       content=b"x" * 17000).status_code == 413


def test_session_and_ip_rate_limits(knowledge_dir, headers):
    for session_limit, ip_limit in [(2, 100), (100, 2)]:
        app = create_app(Settings(knowledge_dir=knowledge_dir, session_rate=session_limit,
                                  ip_rate=ip_limit), FakeModel())
        with TestClient(app) as client:
            for _ in range(2):
                assert client.get("/api/farms/demo", headers=headers).status_code == 200
            last_headers = headers if session_limit == 2 else {"X-Session-Id": str(uuid4())}
            result = client.get("/api/farms/demo", headers=last_headers)
            assert result.status_code == 429
            assert result.headers["Retry-After"]


def test_policy_and_unknown_source_never_stream_raw_output(knowledge_dir, headers):
    for output in [
        '{"answer":"농약 비밀제품을 1000배 희석", "source_ids":["checked"]}',
        '{"answer":"검증된 조언", "source_ids":["invented"]}',
    ]:
        model = FakeModel(raw_output=output)
        with TestClient(create_app(Settings(knowledge_dir=knowledge_dir), model)) as client:
            response = client.post("/api/farms/demo/chat", headers=headers,
                                   json={"message": "수확 준비"})
            stream = events(response)
            assert "농약 비밀제품" not in response.text
            assert "검증된 조언" not in response.text
            assert any(name == "error" for name, _ in stream)
            assert not any(name == "message" for name, _ in stream)
            assert stream[-1][0] == "done"


def test_model_failure_and_timeout(knowledge_dir, headers):
    for model in (FakeModel(fail=True), FakeModel(delay=0.1)):
        settings = Settings(knowledge_dir=knowledge_dir, model_timeout=0.01)
        with TestClient(create_app(settings, model)) as client:
            response = client.post("/api/farms/demo/chat", headers=headers,
                                   json={"message": "수확 준비"})
            stream = events(response)
            assert stream[0][0] == "status"
            assert next(data for name, data in stream if name == "error")["retryable"]
            assert stream[-1][0] == "done"
            assert "sensitive-error" not in response.text
            assert client.get("/api/farms/demo/today", headers=headers).status_code == 503


def test_json_retry_is_bounded(knowledge_dir, headers):
    model = FakeModel(raw_output="invalid json")
    with TestClient(create_app(Settings(knowledge_dir=knowledge_dir), model)) as client:
        result = client.get("/api/farms/demo/today", headers=headers)
        assert result.status_code == 200
        assert result.json()["tasks"] == []
        assert result.json()["notices"][0]["evidence"] == "확인 필요"
        assert model.calls == 2


def test_unreviewed_knowledge_is_not_advice(tmp_path, headers):
    (tmp_path / "draft.md").write_text(
        '---\nsource_title: "초안"\nsource_url: "확인 필요"\n'
        'retrieved_at: "확인 필요"\nreviewed: false\ntask_title: "수확 준비"\n'
        '---\n수확 곶감 준비 확인 항목\n', encoding="utf-8")
    with TestClient(create_app(Settings(knowledge_dir=tmp_path), FakeModel())) as client:
        result = client.get("/api/farms/demo/today", headers=headers).json()
        assert result["tasks"] == []
        assert result["notices"]
        response = client.post("/api/farms/demo/chat", headers=headers,
                               json={"message": "수확 준비 일정 추가"})
        message = next(data for name, data in events(response) if name == "message")
        assert message["evidence"] == "확인 필요"
        assert message["proposals"] == []
