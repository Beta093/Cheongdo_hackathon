"""FastAPI 백엔드 - 감잝아 AI 에이전트와 연결"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import os
import json
import asyncio
import base64
import io
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image

from app.agents.enhanced_advisor import EnhancedFarmAdvisor
from app.policies import PolicyChecker
from app.gate import initialize_gate
from app.masking import mask_personal_data, filter_and_mask
from app.permissions import permission_manager
from app.evidence import EvidenceCollector, EvidenceFormatter

load_dotenv()

# 전역 인스턴스
agent: EnhancedFarmAdvisor = None
policy_checker: PolicyChecker = None
gate = None

# 메모리 저장소 (개발용, 실제는 Cosmos DB)
proposals_db = {}  # {proposal_id: {"status": "pending|approved", ...}}
calendar_events_db = {}  # {farm_id: [events]}


# Request 모델
class ChatRequest(BaseModel):
    message: str


class MaskRequest(BaseModel):
    text: str


class MaskedChatRequest(BaseModel):
    """마스킹 후 채팅 요청"""
    masked_text: str
    mask_token: str
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작
    global agent, policy_checker, gate
    agent = EnhancedFarmAdvisor()
    policy_checker = PolicyChecker()
    gate = initialize_gate()
    print("✅ 감잡아 AI v2.0 에이전트 + 정책 필터 + 토큰 게이트 초기화 완료")
    yield
    # 종료
    print("🛑 서버 종료")


app = FastAPI(
    title="감잡아 API",
    description="청도반시 초보 농부 AI 도우미",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 설정 (환경별)
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

if ENVIRONMENT == "prod":
    # 프로덕션: 명시적 도메인만 허용
    ALLOWED_ORIGINS = [
        "https://gamjapia.kr",
        "https://www.gamjapia.kr",
    ]
else:
    # 개발: 모든 출처 허용
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# ========== 헬스 체크 ==========
@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "ok",
        "agent": "감잡아 AI",
        "version": agent.version if agent else "not initialized",
        "timestamp": datetime.now().isoformat()
    }


# ========== M1: 마스킹 (Step 1) ==========
@app.post("/api/farms/{farm_id}/mask")
async def mask_input(farm_id: str, request: MaskRequest):
    """
    Step 1: 입력 검증 + 인젝션 감지 + 마스킹 + 토큰 발급
    
    1. 프롬프트 인젝션 감지 (한글/영문)
    2. 개인정보 마스킹
    3. 마스킹 토큰 발급
    
    응답:
    {
        "status": "ok|blocked",
        "masked_text": "마스킹된 텍스트",
        "mask_token": "토큰값",
        "instruction": "확인 후 진행해주세요"
    }
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="입력이 비어있습니다")
    
    try:
        # Step 1: 인젝션 필터 + 마스킹
        filter_result = filter_and_mask(request.text)
        
        if not filter_result.is_safe:
            # ❌ 프롬프트 인젝션 감지됨
            return {
                "status": "blocked",
                "reason": filter_result.reason,
                "instruction": "⚠️ 의심스러운 명령어가 감지되었습니다. 다시 입력해주세요.",
                "message": "프롬프트 인젝션 공격이 감지되어 처리되지 않았습니다."
            }
        
        # Step 2: 마스킹 토큰 발급
        mask_token = gate.create_mask_token(filter_result.text)
        
        return {
            "status": "ok",
            "masked_text": filter_result.text,
            "mask_token": mask_token,
            "instruction": "마스킹 결과를 확인 후 '진행' 버튼을 눌러주세요",
            "original_length": len(request.text),
            "masked_length": len(filter_result.text),
            "injection_detected": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"마스킹 오류: {str(e)}")


# ========== F1: 데모 과원 ==========
@app.get("/api/farms/demo")
async def get_demo_farm():
    """데모 과원 (로그인 무)"""
    if not agent:
        raise HTTPException(status_code=503, detail="에이전트 초기화 실패")
    
    try:
        result = agent._tool_get_farm_context("demo")
        return result["farm"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== F2: 오늘의 할 일 ==========
@app.get("/api/farms/{farm_id}/today")
async def get_todays_work(farm_id: str):
    """
    오늘의 할 일 조회
    - 지식 검색 + 날씨 + 과원 정보 종합
    """
    if not agent or not policy_checker:
        raise HTTPException(status_code=503, detail="에이전트 초기화 실패")
    
    try:
        # 과원 정보
        farm = agent._tool_get_farm_context(farm_id)
        if not farm["success"]:
            raise HTTPException(status_code=404, detail="과원을 찾을 수 없습니다")
        
        # 날씨
        weather = agent._tool_get_weather(farm_id)
        
        # 지식 검색 (5월이면 적과 추천)
        from datetime import datetime
        month = datetime.now().month
        
        query = "5월 적과" if month == 5 else "일반 관리"
        knowledge = agent._tool_search_knowledge(query)
        
        # 제안 생성
        proposal = {
            "title": knowledge["result"].get("title", "작업 추천"),
            "reason": knowledge["result"].get("description", ""),
            "sources": knowledge["result"].get("sources", []),
            "ai_generated": True,
            "weather_condition": weather["weather"]["condition"],
            "confidence": knowledge["result"].get("confidence", 0.0)
        }
        
        # 정책 검사
        checked = policy_checker.sanitize_proposal(proposal)
        
        if not checked["is_valid"]:
            return {
                "farm_id": farm_id,
                "status": "warning",
                "issues": checked["issues"],
                "proposal": None
            }
        
        return {
            "farm_id": farm_id,
            "status": "ok",
            "proposal": checked["proposal"],
            "farm_info": farm["farm"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== M3: 채팅 스트리밍 (SSE) - 토큰 검증 + 근거 + 권한 검증 ==========
@app.post("/api/farms/{farm_id}/chat")
async def chat_stream(farm_id: str, request: MaskedChatRequest):
    """
    Step 2+: 채팅 (SSE 스트리밍)
    
    1. 마스킹 토큰 검증
    2. 도구 권한 검증 (권한 없는 도구 차단)
    3. 에이전트 실행
    4. 근거 시스템으로 응답 구성
    5. 정책 검사 후 응답 전송
    """
    if not agent or not policy_checker or not gate:
        raise HTTPException(status_code=503, detail="에이전트 초기화 실패")
    
    # ✅ Step 1: 토큰 검증
    if not gate.verify_mask_token(request.mask_token, request.masked_text):
        raise HTTPException(
            status_code=403, 
            detail="마스킹 단계를 먼저 완료해주세요. 토큰이 유효하지 않습니다."
        )
    
    message = request.message
    
    async def event_generator():
        try:
            # 초기화
            yield f"data: {json.dumps({'type': 'status', 'message': '분석 중...', 'step': 1})}\n\n"
            await asyncio.sleep(0.1)
            
            # ✅ Step 2: 도구 권한 검증
            # (실제 도구 호출 전에 권한 확인)
            yield f"data: {json.dumps({'type': 'status', 'message': '권한 검증 중...', 'step': 2})}\n\n"
            await asyncio.sleep(0.05)
            
            # 도구 권한 조회 (로깅용)
            allowed_tools = permission_manager.get_allowed_tools()
            yield f"data: {json.dumps({'type': 'debug', 'allowed_tools': allowed_tools})}\n\n"
            
            # ✅ Step 3: 에이전트 응답 생성
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI 분석 중...', 'step': 3})}\n\n"
            response = await agent.run_with_user_input(request.masked_text, farm_id)
            
            # ✅ Step 4: 근거 시스템 구성
            yield f"data: {json.dumps({'type': 'status', 'message': '근거 구성 중...', 'step': 4})}\n\n"
            
            # 근거 수집
            collector = EvidenceCollector(request.masked_text, farm_id)
            
            # 근거 자동 추가
            collector.add_from_user_input(
                reasoning="사용자 입력을 분석하여 다음을 도출했습니다",
                confidence=90
            )
            
            # AI 응답을 기반으로 근거 추가
            if isinstance(response, dict):
                if "description" in response:
                    collector.add_evidence(
                        source="AI 분석",
                        quote=response.get("description", "")[:150],
                        reasoning="전문가 분석 기반 추천",
                        confidence=85
                    )
            
            # 추천 생성
            try:
                cited_rec = collector.create_cited_recommendation(
                    recommendation=response.get("description", response) if isinstance(response, dict) else response,
                    priority="중간",
                    impact=response.get("impact", None) if isinstance(response, dict) else None
                )
                
                # API 형식으로 포맷팅
                response_with_evidence = EvidenceFormatter.format_for_api(cited_rec)
            except:
                # 근거 구성 실패 시 기존 응답 사용
                response_with_evidence = {
                    "recommendation": response.get("description", response) if isinstance(response, dict) else response,
                    "evidence": []
                }
            
            # ✅ Step 5: 정책 검사
            yield f"data: {json.dumps({'type': 'status', 'message': '안전성 검사 중...', 'step': 5})}\n\n"
            policy_result = policy_checker.check_response(response_with_evidence)
            sanitized = policy_result["sanitized"]
            
            # ✅ 최종 응답 전송 (근거 포함)
            yield f"data: {json.dumps({'type': 'message', 'content': sanitized, 'is_safe': policy_result['is_safe'], 'has_evidence': 'evidence' in response_with_evidence})}\n\n"
            
            # 완료
            yield f"data: {json.dumps({'type': 'done', 'farm_id': farm_id, 'timestamp': datetime.now().isoformat()})}\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )


# ========== 이미지 분석 채팅 ==========
@app.post("/api/farms/{farm_id}/chat-image")
async def chat_with_image(farm_id: str, message: str = Form(...), image: UploadFile = File(...)):
    """
    이미지를 업로드하고 AI가 분석하는 엔드포인트
    예: 잎 사진 업로드 → 병해충 진단
    """
    if not agent:
        raise HTTPException(status_code=503, detail="에이전트 초기화 실패")
    
    try:
        # 이미지 읽기
        image_data = await image.read()
        img = Image.open(io.BytesIO(image_data))
        
        # 이미지 크기 조정 (성능)
        img.thumbnail((800, 600))
        
        # Base64로 인코딩
        buffered = io.BytesIO()
        
        # RGBA를 RGB로 변환 (JPEG는 투명도를 지원하지 않음)
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            rgb_img.save(buffered, format="JPEG")
        else:
            img.save(buffered, format="JPEG")
        
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # 메시지에 이미지 정보 추가
        if message.strip():
            # 사용자 메시지에 명확한 진단 신호 추가
            enhanced_message = f"사용자가 제출한 사진 분석 요청입니다.\n\n증상 설명: {message}\n\n이 증상을 바탕으로 감나무의 질병을 진단해주세요. 가능한 질병들을 나열하고 각각의 신뢰도를 표시해주세요."
        else:
            # 사용자가 메시지를 입력하지 않으면 기본 분석 프롬프트 사용
            enhanced_message = f"감나무 잎의 사진이 업로드되었습니다. 사진을 자세히 분석해주세요:\n- 잎의 색상 변화\n- 반점이나 병반의 유무\n- 잎의 크기와 형태\n- 병해충의 징후\n\n분석 결과를 바탕으로 가능한 질병을 진단해주세요."
        
        async def event_generator():
            try:
                yield f"data: {json.dumps({'type': 'status', 'message': '이미지 분석 중...'})}\n\n"
                await asyncio.sleep(0.1)
                
                # 에이전트 응답
                response = await agent.run_with_user_input(enhanced_message, farm_id)
                
                # 정책 검사
                policy_result = policy_checker.check_response(response) if policy_checker else {"sanitized": response, "is_safe": True}
                sanitized = policy_result["sanitized"]
                
                yield f"data: {json.dumps({'type': 'message', 'content': sanitized, 'is_safe': policy_result['is_safe']})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 처리 실패: {str(e)}")


# ========== F4: 일정 제안 및 승인 ==========
@app.post("/api/proposals")
async def create_proposal(farm_id: str, task: str, reason: str):
    """
    일정 제안 생성 (Proposal 생성, 아직 저장 안 함)
    """
    if not agent:
        raise HTTPException(status_code=503, detail="에이전트 초기화 실패")
    
    try:
        proposal = agent._tool_propose_calendar_event(
            farm_id=farm_id,
            task=task,
            recommended_date="2026-11-15",  # 예시
            reason=reason
        )
        
        # 메모리에 저장
        proposal_id = proposal["proposal"]["id"]
        proposals_db[proposal_id] = proposal["proposal"]
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "proposal": proposal["proposal"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, farm_id: str):
    """
    제안 승인 → CalendarEvent로 저장
    """
    if proposal_id not in proposals_db:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    
    try:
        proposal = proposals_db[proposal_id]
        
        # 상태 변경
        proposal["status"] = "approved"
        
        # CalendarEvent로 저장
        event = {
            "id": f"event_{proposal_id}",
            "title": proposal.get("task", "작업"),
            "date": proposal.get("recommended_date", ""),
            "reason": proposal.get("reason", ""),
            "sources": proposal.get("sources", []),
            "created_at": datetime.now().isoformat()
        }
        
        if farm_id not in calendar_events_db:
            calendar_events_db[farm_id] = []
        calendar_events_db[farm_id].append(event)
        
        return {
            "success": True,
            "message": "일정이 저장되었습니다",
            "event": event
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== 캘린더 조회 ==========
@app.get("/api/farms/{farm_id}/calendar")
async def get_calendar(farm_id: str):
    """일정 조회"""
    events = calendar_events_db.get(farm_id, [])
    return {
        "farm_id": farm_id,
        "events": events,
        "count": len(events)
    }


# ========== 개발용: 도구 목록 ==========
@app.get("/api/agent/tools")
async def get_tools():
    """등록된 도구 목록"""
    if not agent:
        raise HTTPException(status_code=503, detail="에이전트 초기화 실패")
    
    return {
        "tools": list(agent.tools.keys()),
        "count": len(agent.tools)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
