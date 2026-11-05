# 🎯 감농장 즉시 시작 가능한 액션 플랜

## 📋 최우선 순위 (30분 안에 시작 가능)

### 1️⃣ 마스킹 & 토큰 인증 레이어 추가
**파일:** `backend/app/gate.py` (청도 팀 코드 참고)

```python
import hmac
import hashlib
from datetime import datetime, timedelta

class TokenGate:
    """토큰 기반 단계 강제"""
    def __init__(self, secret: str):
        self.secret = secret.encode()
    
    def text_hash(self, text: str) -> str:
        """텍스트의 MD5 해시"""
        return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    
    def sign_token(self, step: str, text_hash: str) -> str:
        """토큰 생성 (단계 + 해시 + 타임스탐프)"""
        data = f"{step}:{text_hash}:{int(datetime.now().timestamp())}"
        sig = hmac.new(self.secret, data.encode(), hashlib.sha256).hexdigest()
        return f"{data}:{sig}"
    
    def verify_token(self, token: str, expected_step: str, expected_hash: str) -> bool:
        """토큰 검증"""
        try:
            parts = token.rsplit(":", 1)
            data, sig = parts[0], parts[1]
            expected_sig = hmac.new(self.secret, data.encode(), hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(sig, expected_sig):
                return False
            
            step, text_hash, timestamp = data.split(":")
            if step != expected_step or text_hash != expected_hash:
                return False
            
            # 1시간 만료
            if datetime.now().timestamp() - int(timestamp) > 3600:
                return False
            
            return True
        except:
            return False
```

### 2️⃣ 마스킹 API 추가
**파일:** `backend/app/main.py` - 다음 코드 추가

```python
from pydantic import BaseModel
from fastapi import HTTPException

gate = TokenGate(secret=os.getenv("SIGNING_KEY", "dev-secret"))

class MaskRequest(BaseModel):
    text: str

@app.post("/api/farms/{farm_id}/mask")
async def mask_input(farm_id: str, req: MaskRequest):
    """Step 1: 입력 마스킹 + 토큰 발급"""
    if not req.text.strip():
        raise HTTPException(400, detail="입력이 비어있습니다")
    
    masked_text = mask_personal_data(req.text)  # 기존 함수 재사용
    text_hash = gate.text_hash(masked_text)
    mask_token = gate.sign_token("mask", text_hash)
    
    return {
        "masked_text": masked_text,
        "mask_token": mask_token,
        "instruction": "마스킹 결과를 확인 후 '진행' 버튼을 눌러주세요"
    }
```

### 3️⃣ 채팅 API 보안 강화
**파일:** `backend/app/main.py` - 기존 채팅 엔드포인트 수정

```python
class ChatRequest(BaseModel):
    masked_text: str
    mask_token: str
    message: str

@app.post("/api/farms/{farm_id}/chat")
async def chat(farm_id: str, req: ChatRequest):
    """Step 2: 토큰 검증 후 AI 상담"""
    
    # ✅ 마스킹 단계 확인
    text_hash = gate.text_hash(req.masked_text)
    if not gate.verify_token(req.mask_token, "mask", text_hash):
        raise HTTPException(403, detail="마스킹 단계를 먼저 완료해주세요")
    
    # ✅ 마스킹된 텍스트만 AI에 전달
    response = await agent.stream_chat(req.masked_text, req.message)
    
    return response  # 기존과 동일
```

---

## 🎨 프론트엔드 개선 (1시간)

### 단계별 UI 플로우

**파일:** `frontend/src/pages/Chat.jsx` - 기본 구조

```jsx
import { useState } from 'react';
import { api } from '../services/api';

export default function Chat() {
  const [step, setStep] = useState('input');  // input → masking → chat
  const [input, setInput] = useState('');
  const [masked, setMasked] = useState('');
  const [maskToken, setMaskToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [response, setResponse] = useState('');
  
  const handleMask = async () => {
    if (!input.trim()) {
      setError('입력을 해주세요');
      return;
    }
    
    setError(null);
    setLoading(true);
    
    try {
      const res = await api.post('/api/farms/demo/mask', {
        text: input
      });
      setMasked(res.masked_text);
      setMaskToken(res.mask_token);
      setStep('masking');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleChat = async (message) => {
    setLoading(true);
    setError(null);
    
    try {
      const res = await api.post('/api/farms/demo/chat', {
        masked_text: masked,
        mask_token: maskToken,
        message
      });
      setResponse(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="p-6">
      {/* Step 1: 입력 */}
      {step === 'input' && (
        <div>
          <h2 className="text-2xl font-bold mb-4">상담 내용 입력</h2>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={4000}
            className="w-full h-40 p-3 border rounded"
            placeholder="여기에 상담 내용을 입력해주세요 (4000자 이내)"
          />
          <p className="text-sm text-gray-500 mt-2">{input.length}/4000</p>
          
          {error && <div className="text-red-500 mt-2">{error}</div>}
          
          <button
            onClick={handleMask}
            disabled={loading}
            className="mt-4 px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '처리 중...' : '입력 분석'}
          </button>
        </div>
      )}
      
      {/* Step 2: 마스킹 확인 */}
      {step === 'masking' && (
        <div>
          <h2 className="text-2xl font-bold mb-4">개인정보 마스킹 확인</h2>
          <p className="text-gray-600 mb-4">
            다음과 같이 개인정보가 마스킹되었습니다. 확인 후 진행해주세요.
          </p>
          
          <div className="bg-gray-100 p-4 rounded mb-4 max-h-40 overflow-y-auto">
            <p className="whitespace-pre-wrap">{masked}</p>
          </div>
          
          <button
            onClick={() => setStep('chat')}
            className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            확인하고 진행 →
          </button>
        </div>
      )}
      
      {/* Step 3: 채팅 */}
      {step === 'chat' && (
        <div>
          <h2 className="text-2xl font-bold mb-4">AI 상담</h2>
          <div className="bg-blue-50 p-4 rounded mb-4">
            <p>{response}</p>
          </div>
          
          <button
            onClick={() => handleChat('계속 진행')}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded"
          >
            {loading ? '로딩...' : '계속'}
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## 🔐 PolicyChecker 추가 (30분)

**파일:** `backend/app/policies.py` - 새로 생성

```python
class FarmPolicyChecker:
    """AI 에이전트의 도구 사용 제한"""
    
    BLOCKED_TOOLS = [
        "shell",
        "exec", 
        "system_call",
        "file_write",
        "file_delete",
        "subprocess",
        "eval",
        "compile"
    ]
    
    def check(self, tool_name: str) -> bool:
        """도구 사용 허용 여부"""
        return tool_name not in self.BLOCKED_TOOLS
    
    def check_output(self, response: str) -> bool:
        """응답 안전성 검사"""
        dangerous_keywords = [
            "rm -rf",
            "drop table",
            "delete from",
            "exec(",
            "eval("
        ]
        return not any(kw in response.lower() for kw in dangerous_keywords)

# 사용
@app.post("/api/farms/{farm_id}/chat")
async def chat(farm_id: str, req: ChatRequest):
    policy = FarmPolicyChecker()
    response = await agent.stream_chat(req.masked_text, req.message)
    
    # ✅ 응답 검증
    if not policy.check_output(str(response)):
        logger.warning(f"Policy violation detected in response")
        return {"error": "부적절한 응답이 생성되었습니다"}
    
    return response
```

---

## ✅ 배포 체크리스트

```
□ 마스킹 API 구현 (`/api/farms/{id}/mask`)
□ 토큰 검증 추가 (ChatRequest)
□ PolicyChecker 구현 및 적용
□ 프론트엔드 단계별 UI 수정
□ `.env`에 SIGNING_KEY 추가
□ 로컬 테스트 (`npm run dev` + `python -m uvicorn ...`)
□ GitHub 푸시
□ Azure 배포
```

---

## 📊 예상 점수 변화

| 단계 | 시간 | 점수 증가 | 누적 |
|------|------|----------|------|
| **마스킹 + 토큰** | 2시간 | +15점 | **75점** |
| **PolicyChecker** | 30분 | +5점 | **80점** |
| **UI/UX** | 1시간 | +5점 | **85점** |
| **최종 검증** | 30분 | - | **85-90점** |

**총 소요: 4시간**

