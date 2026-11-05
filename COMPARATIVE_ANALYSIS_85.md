# 🎯 85점 팀 분석: "비서실" vs 감농장 AI

## 📊 프로젝트 개요

| 항목 | 비서실 | 감농장 AI |
|------|-------|----------|
| **점수** | 85점 | 60→75점 |
| **주제** | 직장인 일정/할 일 정리 | 감 재배 컨설턴트 |
| **복잡도** | 매우 높음 (멀티에이전트) | 중간 (단일 에이전트) |
| **기술 스택** | Agent Framework + GitHub Copilot SDK | FastAPI + Pydantic |
| **코드 규모** | 2,284줄 (Python) | ~700줄 (Python + JS) |

---

## 🔍 85점 팀이 잘한 것

### 1️⃣ **멀티 에이전트 오케스트레이션**

**비서실의 아키텍처:**
```
input → collect(카톡·메일·캘린더·메모) 
      → lead(팀장: 우선순위 정하기)
      → [todo + schedule + reply] (전문 비서 3개 동시)
      → review(검토: 근거 검증 + 조정)
      → output
```

**특징:**
- ✅ **Fan-out/Fan-in 패턴**: 채널별 수집과 전문 비서들이 병렬로 실행
- ✅ **체계적 컨텍스트 전달**: 팀장이 각 전문 비서에게 "작업 지시(brief)"를 줌
- ✅ **검토 단계의 조정**: 일정 충돌 발생 시 일정 비서가 다시 작업
- ✅ **부분 실패 격리**: 한 비서가 실패해도 다른 비서 결과는 표시

**감농장에의 적용:**
- 현재: 단일 에이전트 (EnhancedFarmAdvisor)
- 개선안: **병렬 에이전트 도입**
  - Agent 1: 환경 분석 (날씨, 토양, 해충)
  - Agent 2: 작업 추천 (적과, 방제, 시비)
  - Agent 3: 경제성 검증 (비용, 수익률)
  - 최종: 검토 에이전트가 종합

### 2️⃣ **원문 근거 검증 (Evidence Validation)**

**비서실의 구현:**
```python
# 모든 항목이 원문 근거를 가짐
"evidence": {
    "message_id": "s1-m3",      # 어느 입력의 어느 메시지?
    "quote": "원문 그대로의 짧은 인용"
}
```

**특징:**
- ✅ 모든 결과에 `message_id` 기록
- ✅ AI가 말한 것과 원문을 대조
- ✅ 원문 없으면 결과 삭제
- ✅ 사용자가 결과를 믿을 수 있게 함

**감농장에의 적용:**
```python
# 현재 없는 기능
response = agent.run()  # 근거 X

# 개선 후
response = {
    "recommendation": "5월에 적과를 추천합니다",
    "evidence": {
        "source": "청도농업기술센터 자료",
        "reference": "감 재배 가이드 p.12",
        "confidence": 0.95
    }
}
```

### 3️⃣ **프롬프트 인젝션 방어**

**비서실의 안전 규칙:**
```python
_INJECTION = re.compile(
    r"(이전|앞의|기존)\s*(지시|명령|규칙|프롬프트)[^\n]{0,12}(무시|잊)"
    r"|시스템\s*(안내|메시지|프롬프트)\s*[:：]"
    r"|ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)"
    # ... 더 많은 패턴
)

def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))

# 의심 메시지는 격리
if looks_like_injection(message):
    message = QUARANTINED  # AI에게 보내지 않음
    flagged.append(message_id)
```

**특징:**
- ✅ 다국어 지시문 감지 (한글 + 영문)
- ✅ 다양한 변형 패턴 대응
- ✅ 의심 메시지를 완전히 걸러냄
- ✅ 사용자에게 격리 건수 표시

**감농장에의 적용:**
```python
# 현재 기본 검증만 함
if not request.text.strip():
    raise HTTPException(400, "입력이 비어있습니다")

# 개선: 인젝션 필터 추가
INJECTION_PATTERNS = [
    r"(시스템|프롬프트|지시)[를를이].*무시",
    r"(너의|너는|당신의|당신은).*역할.*바꿔",
    r"이전.*지시.*따르",
]

def is_injection_suspected(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in INJECTION_PATTERNS)

if is_injection_suspected(request.text):
    raise HTTPException(403, "지시문 형식의 입력이 감지되었습니다")
```

### 4️⃣ **세 가지 채널 파싱 + 자동 포맷 감지**

**비서실의 채널 지원:**
| 채널 | 입력 형식 | 파서 |
|------|---------|------|
| 카카오톡 | `.txt` (내보내기) | kakao.py (143줄) |
| 메일 | `.eml` 또는 붙여넣기 | channels.py (217줄) |
| 캘린더 | `.ics` (Google/Outlook) | channels.py |
| 메모 | 자유 텍스트 | channels.py |

**특징:**
- ✅ 날짜 자동 파싱
- ✅ 보낸 사람 추출
- ✅ 채널별 메타데이터 (시간, 제목, 본문)
- ✅ 형식 자동 감지

**감농장에의 적용:**
```python
# 현재: 텍스트만 받음
class ChatRequest(BaseModel):
    message: str

# 개선: 여러 형식 지원
class FarmInputRequest(BaseModel):
    """채널별 입력 지원"""
    text: str  # 자유 텍스트
    images: List[bytes] = []  # 작물 사진
    weather_file: Optional[bytes] = None  # CSV (기상청 데이터)
    calendar_ics: Optional[bytes] = None  # 일정 파일
    channel: str = "memo"  # "kakao" / "email" / "memo"

# 파서 작성
def parse_farm_input(req: FarmInputRequest) -> List[Message]:
    if req.channel == "weather":
        return parse_weather_csv(req.weather_file)
    elif req.channel == "schedule":
        return parse_ics(req.calendar_ics)
    else:
        return parse_memo(req.text)
```

### 5️⃣ **스트리밍 + 실시간 진행판**

**비서실의 구현:**
```python
# Agent Framework의 WorkflowEvent로 각 단계 진행을 실시간 전송
@handler("state_changed")
async def on_state_changed(ctx: WorkflowContext):
    await ctx.add_event(WorkflowEvent(
        type="state_changed",
        source="schedule",  # 어느 비서?
        status="running",
        data={"current_tool": "resolve_korean_date"}
    ))
    # 프론트엔드는 SSE로 이벤트를 받음

# 프론트엔드
<div class="progress-board">
    <Card title="채널별 수집">
        <Status node="collect-1">완료 ✓</Status>
        <Status node="collect-2">실행 중...</Status>
    </Card>
    <Card title="팀장 비서">
        <Status>로딩 중...</Status>
    </Card>
</div>
```

**특징:**
- ✅ 비서별 진행 상황 실시간 표시
- ✅ 도구 호출 내역 표시
- ✅ 에러 발생 시 즉시 알림
- ✅ 사용자가 과정을 신뢰할 수 있음

**감농장에의 적용:**
```javascript
// 현재: 단순 로딩
setLoading(true);
await api.streamChat(...);
setLoading(false);

// 개선: 단계별 진행판
const [stages, setStages] = useState([
    { id: 'analyze', name: '환경 분석', status: 'pending' },
    { id: 'recommend', name: '작업 추천', status: 'pending' },
    { id: 'validate', name: '경제성 검증', status: 'pending' },
    { id: 'review', name: '최종 검토', status: 'pending' }
]);

// WebSocket으로 진행 상황 수신
ws.onmessage = (event) => {
    const { stage, status, tool_call } = JSON.parse(event.data);
    setStages(prev => prev.map(s => 
        s.id === stage ? { ...s, status, tool_call } : s
    ));
};
```

### 6️⃣ **도구(Tool) 권한 제한**

**비서실의 구현:**
```python
# Agent Framework의 권한 정책: 우리가 정의한 함수만 허용
allowed_tools = [
    "resolve_korean_date",  # ✓ 우리가 만든 도구
    "find_free_slots",      # ✓ 우리가 만든 도구
]

# 내장 도구는 제외
# ❌ file_read
# ❌ file_write
# ❌ shell_exec
# ❌ internet_search

# 권한 검사기가 요청된 도구를 화이트리스트에 대조
def check_tool_permission(tool_name: str) -> bool:
    return tool_name in allowed_tools
```

**특징:**
- ✅ LLM이 임의로 파일·셸 실행 불가
- ✅ 우리가 정의한 도구만 사용 가능
- ✅ 보안 침해 방지

**감농장에의 적용:**
```python
# 현재: 도구 제한 없음
class EnhancedFarmAdvisor:
    tools = {
        "get_farm_context",
        "get_weather",
        "search_knowledge",
        # ... 더 많은 도구
    }

# 개선: 권한 제한 추가
ALLOWED_TOOLS = {
    "get_farm_context": {"category": "readonly"},
    "search_knowledge": {"category": "readonly"},
    "calculate_optimal_timing": {"category": "deterministic"},
    # ❌ file_write는 포함하지 않음
    # ❌ external_api_call은 포함하지 않음
}

def verify_tool_access(tool_name: str, user_level: str) -> bool:
    if tool_name not in ALLOWED_TOOLS:
        raise PermissionError(f"도구 {tool_name}는 사용 불가")
    return True
```

---

## 🚀 감농장이 구현해야 할 개선사항 (우선순위)

### **Tier 1: 즉시 도입 (+15점 → 90점)**

#### 1-1. 도구 권한 제한
```python
# app/permissions.py
TOOL_WHITELIST = {
    "get_farm_context": True,
    "search_knowledge": True,
    "calculate_dates": True,
    # 나머지는 거부
}

@app.middleware("http")
async def check_tool_access(request, call_next):
    # 도구 호출 검증
    pass
```
**예상 효과**: +3점 (책임 있는 AI)

#### 1-2. 원문 근거 추가
```python
class FarmResponse(BaseModel):
    recommendation: str
    evidence: {
        source: str  # "청도농업기술센터"
        reference: str  # "감 재배 가이드 p.12"
        confidence: float  # 0-1
    }
```
**예상 효과**: +5점 (투명성)

#### 1-3. 인젝션 필터 강화
```python
INJECTION_PATTERNS = [
    r"(시스템|프롬프트|지시)[를를이].*무시",
    r"(역할|목표|지시).*변경",
]

def block_injection(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in INJECTION_PATTERNS)
```
**예상 효과**: +3점 (보안)

#### 1-4. 입력 채널 다양화
```python
class FarmInputRequest(BaseModel):
    text: str
    images: List[bytes] = []
    csv_weather: Optional[bytes] = None
    channel: str  # "text" / "image" / "weather"
```
**예상 효과**: +4점 (사용성)

---

### **Tier 2: 선택사항 (+10점 → 100점)**

#### 2-1. 멀티에이전트 병렬 처리
```python
# Agent 1: 환경 분석
env_agent = EnvAnalysisAgent()

# Agent 2: 작업 추천
task_agent = TaskRecommendationAgent()

# Agent 3: 경제성 검증
econ_agent = EconomicValidationAgent()

# 병렬 실행
results = await asyncio.gather(
    env_agent.run(input),
    task_agent.run(input),
    econ_agent.run(input)
)

# 최종 검토
final = review_agent.synthesize(results)
```
**예상 효과**: +5점 (복잡도)

#### 2-2. 실시간 진행판
```javascript
// WebSocket 대신 Server-Sent Events (SSE) 사용
const events = new EventSource('/api/farms/demo/events');
events.onmessage = (e) => {
    const { stage, status, tool } = JSON.parse(e.data);
    updateProgressBoard(stage, status, tool);
};
```
**예상 효과**: +3점 (UX)

#### 2-3. 조정 대화 (Iterative Refinement)
```python
# 첫 제안에서 충돌 발견 시 자동 조정
if has_conflict(proposed_schedule):
    # 일정 에이전트가 다시 작업
    revised = await schedule_agent.revise(
        conflicts=conflicts,
        free_slots=find_free_slots()
    )
```
**예상 효과**: +2점 (기능)

---

## 📊 기대 효과

| 단계 | 구현 항목 | 점수 | 누적 |
|------|---------|------|------|
| 현재 | 마스킹 + 토큰 | 75점 | 75점 |
| Tier 1-1 | 도구 권한 제한 | +3점 | 78점 |
| Tier 1-2 | 원문 근거 | +5점 | 83점 |
| Tier 1-3 | 인젝션 필터 | +3점 | 86점 |
| Tier 1-4 | 채널 다양화 | +4점 | **90점** |
| Tier 2 | 멀티에이전트 + 진행판 | +10점 | **100점** |

---

## 🎯 다음 단계 액션 플랜

### 1. 인젝션 필터 강화 (1시간)
```python
# app/security.py 추가/수정
INJECTION_PATTERNS = [...]
def block_injection(text): ...
```

### 2. 원문 근거 시스템 (2시간)
```python
# app/evidence.py 추가
class EvidenceTracker: ...
# agent에 증거 추적 추가
```

### 3. 도구 권한 제한 (1시간)
```python
# app/permissions.py 추가
TOOL_WHITELIST = {...}
```

### 4. 채널 다양화 (2시간)
```python
# app/channels.py 추가
class MultiChannelParser: ...
```

**총 소요 시간**: 약 6시간

---

## 📌 요약

**비서실이 85점을 받은 이유:**
1. ✅ 멀티에이전트 오케스트레이션 (복잡도 고점수)
2. ✅ 원문 근거 검증 (투명성)
3. ✅ 프롬프트 인젝션 방어 (보안)
4. ✅ 다채널 입력 + 파싱 (사용성)
5. ✅ 실시간 진행판 (신뢰도)
6. ✅ 도구 권한 제한 (책임성)

**감농장의 다음 목표 (90점+):**
1. 인젝션 필터 강화
2. 원문 근거 시스템
3. 도구 권한 제한
4. 채널 다양화
5. (선택) 멀티에이전트 병렬화

---

**작성일**: 2026년 11월 5일
**분석자**: Copilot App
**출처**: Issue #130 비서실 프로젝트 분석
