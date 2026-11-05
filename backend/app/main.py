import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.agents.base import Model
from backend.agents.copilot import CopilotModel
from backend.agents.fake import FakeModel
from backend.app.policy import PolicyError
from backend.app.schemas import ChatInput, FarmInput, LogInput
from backend.app.security import RateLimiter, SecurityMiddleware
from backend.app.service import AssistantService
from backend.app.settings import PROJECT_ROOT, Settings
from backend.app.store import MemoryStore, StoreError
from backend.app.repository import Repository
from backend.app.weather import WeatherClient
from backend.app.telemetry import configure_telemetry


def create_app(settings: Settings | None = None, model: Model | None = None,
               store: Repository | None = None, weather: WeatherClient | None = None) -> FastAPI:
    settings = settings or Settings()
    if model is None:
        mode = os.environ.get("GAMJABA_MODEL", "copilot")
        if mode not in ("copilot", "fake"):
            raise ValueError("GAMJABA_MODEL must be copilot or fake")
        model = FakeModel() if mode == "fake" else CopilotModel()
    if store is None:
        storage_mode = os.environ.get("GAMJABA_STORE", "memory")
        if storage_mode == "cosmos":
            from backend.app.cosmos import CosmosStore
            store = CosmosStore.from_environment(settings)
        elif storage_mode == "memory":
            store = MemoryStore(settings.session_ttl, settings.proposal_ttl, settings.max_sessions)
        else:
            raise ValueError("GAMJABA_STORE must be memory or cosmos")
    limiter = RateLimiter(settings.session_rate, settings.ip_rate, settings.rate_window)
    service = AssistantService(settings, store, model, weather)
    app = FastAPI(title="감잡아", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.state.store = store
    app.add_middleware(SecurityMiddleware, max_body_bytes=settings.max_body_bytes)
    configure_telemetry(app)

    @app.exception_handler(StoreError)
    async def store_error_handler(request: Request, error: StoreError):
        return JSONResponse({"detail": error.message}, status_code=error.status_code)

    async def session(request: Request, x_session_id: Annotated[UUID, Header()]) -> str:
        session_id = str(x_session_id)
        # Do not trust arbitrary X-Forwarded-For supplied by a public client.
        ip = request.client.host if request.client else "unknown"
        if not limiter.allow(session_id, ip):
            raise HTTPException(429, "요청이 많습니다. 잠시 후 다시 시도해 주세요.",
                                headers={"Retry-After": str(settings.rate_window)})
        store.touch(session_id)
        return session_id

    session_dep = Depends(session)
    api = APIRouter(prefix="/api")

    def check_farm(session_id: str, farm_id: str) -> dict:
        return store.farm(session_id, farm_id)

    @api.get("/health")
    async def health(session_id: str = session_dep):
        return {"status": "ok", "model_mode": model.mode,
                "model_configured": model.mode == "fake" or bool(os.environ.get("COPILOT_GITHUB_TOKEN"))}

    @api.get("/farms/demo")
    async def demo(session_id: str = session_dep):
        return {**store.farm(session_id, "demo"), "model_mode": model.mode}

    @api.post("/farms", status_code=201)
    async def register(body: FarmInput, session_id: str = session_dep):
        return {**store.create_farm(session_id, body), "model_mode": model.mode}

    @api.get("/farms/{farm_id}")
    async def farm_details(farm_id: str, session_id: str = session_dep):
        return {**store.farm(session_id, farm_id), "model_mode": model.mode}

    @api.get("/farms/{farm_id}/logs")
    async def logs(farm_id: str, session_id: str = session_dep):
        return store.logs(session_id, farm_id)

    @api.post("/farms/{farm_id}/logs", status_code=201)
    async def add_log(farm_id: str, body: LogInput, session_id: str = session_dep):
        return store.add_log(session_id, farm_id, body)

    @api.put("/farms/{farm_id}/logs/{log_id}")
    async def update_log(farm_id: str, log_id: str, body: LogInput, session_id: str = session_dep):
        return store.update_log(session_id, farm_id, log_id, body)

    @api.delete("/farms/{farm_id}/logs/{log_id}", status_code=204)
    async def delete_log(farm_id: str, log_id: str, session_id: str = session_dep):
        store.delete_log(session_id, farm_id, log_id)
        return Response(status_code=204)

    @api.get("/farms/{farm_id}/weather")
    async def weather_forecast(farm_id: str, days: int = Query(default=3, ge=1, le=7),
                               session_id: str = session_dep):
        farm = check_farm(session_id, farm_id)
        return await service.weather.get(farm["region"], days)

    @api.get("/farms/{farm_id}/today")
    async def today(farm_id: str, session_id: str = session_dep):
        check_farm(session_id, farm_id)
        try:
            return await service.today(session_id, farm_id)
        except StoreError:
            raise
        except PolicyError:
            raise HTTPException(502, "응답이 안전성 또는 출처 검사를 통과하지 못했습니다.") from None
        except Exception:
            raise HTTPException(503, "모델을 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None

    @api.post("/farms/{farm_id}/chat")
    async def chat(farm_id: str, body: ChatInput, session_id: str = session_dep):
        check_farm(session_id, farm_id)
        return StreamingResponse(service.chat(session_id, body.message, farm_id), media_type="text/event-stream",
                                 headers={"X-Accel-Buffering": "no"})

    @api.get("/farms/{farm_id}/calendar")
    async def calendar(farm_id: str, session_id: str = session_dep):
        check_farm(session_id, farm_id)
        return store.calendar(session_id, farm_id)

    @api.post("/proposals/{proposal_id}/approve")
    async def approve(proposal_id: str, session_id: str = session_dep):
        return store.decide(session_id, proposal_id, "approve")

    @api.post("/proposals/{proposal_id}/reject")
    async def reject(proposal_id: str, session_id: str = session_dep):
        return store.decide(session_id, proposal_id, "reject")

    app.include_router(api)
    app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
    return app


app = create_app()
