import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agents.base import Model
from backend.agents.copilot import CopilotModel
from backend.agents.fake import FakeModel
from backend.app.policy import PolicyError
from backend.app.schemas import ChatInput
from backend.app.security import RateLimiter, SecurityMiddleware
from backend.app.service import AssistantService
from backend.app.settings import PROJECT_ROOT, Settings
from backend.app.store import MemoryStore, StoreError


DEMO_FARM = {"id": "demo", "farmId": "demo", "name": "청도반시 데모 과원", "cultivar": "청도반시",
             "region": "청도군 (데모)", "plantedYear": None, "areaM2": None, "isDemo": True,
             "weather": "날씨 정보 없음", "measurements": "현장 측정 정보 없음"}


def create_app(settings: Settings | None = None, model: Model | None = None) -> FastAPI:
    settings = settings or Settings()
    if model is None:
        mode = os.environ.get("GAMJABA_MODEL", "copilot")
        if mode not in ("copilot", "fake"):
            raise ValueError("GAMJABA_MODEL must be copilot or fake")
        model = FakeModel() if mode == "fake" else CopilotModel()
    store = MemoryStore(settings.session_ttl, settings.proposal_ttl, settings.max_sessions)
    limiter = RateLimiter(settings.session_rate, settings.ip_rate, settings.rate_window)
    service = AssistantService(settings, store, model)
    app = FastAPI(title="감잡아", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.state.store = store
    app.add_middleware(SecurityMiddleware, max_body_bytes=settings.max_body_bytes)

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

    def check_farm(farm_id: str) -> None:
        if farm_id != "demo":
            raise HTTPException(404, "데모 과원을 찾을 수 없습니다.")

    @api.get("/health")
    async def health(session_id: str = session_dep):
        return {"status": "ok", "model_mode": model.mode,
                "model_configured": model.mode == "fake" or bool(os.environ.get("COPILOT_GITHUB_TOKEN"))}

    @api.get("/farms/demo")
    async def demo(session_id: str = session_dep):
        return {**DEMO_FARM, "sessionId": session_id, "model_mode": model.mode}

    @api.get("/farms/{farm_id}/today")
    async def today(farm_id: str, session_id: str = session_dep):
        check_farm(farm_id)
        try:
            return await service.today(session_id)
        except StoreError:
            raise
        except PolicyError:
            raise HTTPException(502, "응답이 안전성 또는 출처 검사를 통과하지 못했습니다.") from None
        except Exception:
            raise HTTPException(503, "모델을 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None

    @api.post("/farms/{farm_id}/chat")
    async def chat(farm_id: str, body: ChatInput, session_id: str = session_dep):
        check_farm(farm_id)
        return StreamingResponse(service.chat(session_id, body.message), media_type="text/event-stream",
                                 headers={"X-Accel-Buffering": "no"})

    @api.get("/farms/{farm_id}/calendar")
    async def calendar(farm_id: str, session_id: str = session_dep):
        check_farm(farm_id)
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
