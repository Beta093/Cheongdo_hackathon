# 🔍 청도 팀(60점) vs 감농장 팀 비교 분석

## 📊 프로젝트 규모 비교

| 항목 | 청도 팀 (60점) | 감농장 팀 |
|------|-----------|---------|
| **백엔드 코드** | 761줄 | ~800줄 |
| **프론트엔드** | 단일 HTML 페이지 | Vite + React (5 페이지, ~1000줄) |
| **API 엔드포인트** | 4개 (/mask, /match, /draft, /approve) | 7개 |
| **테스트 커버리지** | 미기재 | 100% (14/14) |
| **배포 타입** | Azure App Service (단순) | Azure Container Apps + Bicep IaC |
| **인프라 코드** | 없음 | 있음 (Bicep) |
| **자동 배포** | 수동 `az webapp up` | `deploy.sh` 스크립트 |
| **모니터링** | 기본 건강 체크 | Log Analytics + 통합 모니터링 |
| **AI 프레임워크** | Microsoft Agent Framework | GitHub Copilot SDK + Agent Framework |
| **문서** | 6개 | 6개 |

---

## ⭐ 청도 팀이 잘한 것 (60점 얻은 이유)

### 1️⃣ **보안 & 개인정보 보호** 🔐
```python
# 핵심: 마스킹 토큰으로 단계 강제
mask_token = gate.sign_token("mask", text_hash)
# 다음 단계는 유효한 토큰이 없으면 진행 불가
if not gate.verify_token(mask_token, "mask", ...):
    raise 403 Forbidden
```
- ✅ **마스킹 먼저, AI 호출은 마지막** - 개인정보 안전
- ✅ **토큰 서명으로 단계 강제** - 프로세스 무시 방지
- ✅ **모델에 마스킹된 텍스트만 전달** - PII 보호
- ✅ **규칙 기반 폴백** - AI 오류 시 안전한 대체

### 2️⃣ **책임감 있는 AI**
- ✅ **PolicyChecker** - 결과 검증
- ✅ **사람이 최종 승인** (4단계: mask → match → draft → **approve**)
- ✅ **에이전트가 제도 ID를 조회한 후 서버가 재검증**
- ✅ **CLI 셸·파일 도구 제한** - 위험한 도구 비활성화

### 3️⃣ **응답 캐싱** 💾
```python
# 같은 입력에 대해 99.5% 빠른 응답
masking_cache = MaskingCache(max_size=1000)
matching_cache = MatchingCache(max_size=500)
drafting_cache = DraftingCache(max_size=500)
```
- ✅ 3단계 LRU 캐싱
- ✅ MD5 기반 해시
- ✅ 통계 트래킹 (`/api/cache-stats`)

### 4️⃣ **응답 압축**
```python
app.add_middleware(GZIPMiddleware, minimum_size=200)
```
- ✅ GZIP으로 네트워크 전송 84% 감소

### 5️⃣ **명확한 사용 사례**
- 복지 상담 → 개인정보 마스킹 → AI 제도 분석 → 담당자 승인
- 매우 구체적이고 실용적

### 6️⃣ **규칙 기반 폴백**
- AI 연결 안 되면? → 규칙 기반 결과 반환
- 사용자 경험 손상 없음

---

## 🎯 감농장이 할 수 있는 개선사항 (점수 올리기)

### ❌ 현재 문제점

#### 1. **보안 미흡** ⚠️
```tsx
// ❌ 프론트에서 직접 API 호출
const response = await api.post(`/api/farms/${id}/chat`, {
  farmerId: id,
  message: inputText  // 검증 없음
});
```
- 프론트엔드에서 직접 API 호출
- 입력 검증이 약함
- 마스킹/정제 단계 없음
- AI 호출 전 인간 검증 단계 없음

**👉 개선:** 청도처럼 **다단계 인증 & 마스킹 추가**

#### 2. **에이전트 안전성** 🤖
```python
# ❌ 도구 제한 없음
agent = FarmAdvisorAgent()  # 모든 도구 사용 가능?
```

**👉 개선:** PolicyChecker 추가, 위험한 도구 비활성화

#### 3. **프론트엔드 구조** 🎨
- 페이지가 많지만 **UI 최적화 미흡**
- **로딩 상태 표시 부족**
- **에러 핸들링 미흡**
- **입력 검증 UI 없음**

---

## 🚀 구체적 개선 전략

### Phase 1: 보안 강화 (우선순위: 최고)

**목표:** 청도처럼 **단계별 검증** 추가

```python
# 1. 마스킹 API 추가
@app.post("/api/farms/{farm_id}/mask")
async def mask_farm_input(farm_id: str, req: MaskRequest) -> dict:
    """입력 마스킹 + 토큰 발급"""
    masked = mask_personal_data(req.text)  # 이름, 전화, 주소 등 가리기
    mask_token = sign_token("mask", text_hash(masked))
    return {"masked_text": masked, "mask_token": mask_token}

# 2. 매칭 API
@app.post("/api/farms/{farm_id}/match")
async def match_conditions(farm_id: str, req: MatchRequest) -> dict:
    """토큰 검증 후 조건 매칭"""
    if not verify_token(req.mask_token, "mask", ...):
        raise 403  # 마스킹 단계 건너뛰면 안 됨!
    
    # 에이전트가 조건 매칭
    conditions = await agent.match_conditions(req.masked_text)
    match_token = sign_token("match", ...)
    return {"conditions": conditions, "match_token": match_token}

# 3. 상담 API
@app.post("/api/farms/{farm_id}/chat")
async def chat(farm_id: str, req: ChatRequest) -> AsyncGenerator:
    """토큰 검증 후 SSE 스트리밍"""
    if not verify_token(req.match_token, "match", ...):
        raise 403
    
    # AI 상담 (마스킹된 텍스트만 사용)
    async for chunk in agent.stream_chat(req.masked_text):
        yield f"data: {json.dumps(chunk)}\n\n"

# 4. 승인 API
@app.post("/api/farms/{farm_id}/approve")
async def approve(farm_id: str, req: ApproveRequest) -> dict:
    """사람이 최종 승인"""
    if not verify_token(req.chat_token, "chat", ...):
        raise 403
    
    return {"status": "approved", "timestamp": now()}
```

**프론트엔드 플로우:**
```
1. 입력 → /mask → 마스킹 표시 + "확인하고 진행" 버튼
2. 확인 → /match → 조건 매칭 결과 + "분석 시작" 버튼
3. 분석 → /chat → SSE 스트리밍 + "완료" 버튼
4. 완료 → /approve → 최종 승인
```

### Phase 2: AI 안전성 (우선순위: 높음)

```python
# PolicyChecker 추가
class FarmPolicyChecker(PolicyChecker):
    def check(self, tool_call):
        """위험한 도구 블록"""
        if tool_call.name in ["shell", "exec", "file_write"]:
            return False  # 블록!
        return True

agent = FarmAdvisorAgent(policy_checker=FarmPolicyChecker())
```

### Phase 3: 프론트엔드 개선 (우선순위: 중간)

```tsx
// ✅ 로딩 상태 추가
const [isLoading, setIsLoading] = useState(false);
const [error, setError] = useState(null);

// ✅ 단계별 진행
const [step, setStep] = useState("input");  // input → masking → matching → chat → approved

// ✅ 입력 검증
const validateInput = (text) => {
  if (!text.trim()) return "입력을 입력해주세요";
  if (text.length > 4000) return "4000자를 초과했습니다";
  return null;
};

// ✅ 에러 핸들링
const maskInput = async (text) => {
  const error = validateInput(text);
  if (error) {
    setError(error);
    return;
  }
  
  setIsLoading(true);
  try {
    const res = await api.post(`/api/farms/${farmId}/mask`, { text });
    setMaskedText(res.masked_text);
    setMaskToken(res.mask_token);
    setStep("masking");
  } catch (e) {
    setError(e.message);
  } finally {
    setIsLoading(false);
  }
};
```

---

## 📈 예상 점수 개선

| 항목 | 현재 | 개선 후 | 기대값 |
|------|------|--------|--------|
| 보안/개인정보 | 60점 | **+15점** (마스킹+토큰 단계 강제) | **75점** |
| AI 안전성 | - | **+5점** (PolicyChecker) | **80점** |
| 프론트엔드 UX | - | **+5점** (로딩, 에러 처리) | **85점** |
| 성능 (캐싱+압축) | - | **+10점** (이미 구현됨) | **95점** |
| **총합** | **60점** | → | **90-95점** |

---

## 🎬 구현 순서

1. **마스킹 + 토큰 검증 API** (2시간) → 보안 점수 +15점
2. **PolicyChecker 추가** (30분) → AI 안전성 +5점
3. **프론트엔드 UI 개선** (1시간) → UX +5점
4. **테스트 & 배포** (30분)

**총 소요 시간: 4시간**

---

## 💡 핵심 인사이트

✅ **청도 팀이 60점을 받은 이유:**
- 보안 > 기능 (개인정보 마스킹이 최우선)
- 단계 강제 (토큰으로 순서 보장)
- 사람 중심 (AI가 하지만 사람이 최종 승인)
- 폴백 (AI 실패해도 규칙 기반 대체)

🎯 **감농장이 할 수 있는 것:**
- 위의 4가지 원칙을 적용
- 그러면 90점대 가능!

