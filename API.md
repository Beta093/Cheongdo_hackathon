# API 문서 - 프론트엔드 통합

## 🔗 Base URL

```
http://localhost:8000       # 로컬 개발
https://<CONTAINER_APP_URL> # Azure 배포 후
```

---

## 📋 엔드포인트 목록

### 1️⃣ 헬스 체크
```
GET /api/health
```

**응답 (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-11-05T14:26:20Z"
}
```

---

### 2️⃣ 데모 과원 조회
```
GET /api/farms/demo
```

**응답 (200):**
```json
{
  "success": true,
  "farm": {
    "id": "demo",
    "name": "청도 데모 과원",
    "location": "경주시 청도",
    "variety": "청도반시",
    "planted_year": 2021,
    "tree_age_years": 5,
    "area_m2": 330,
    "current_growth_stage": "열매 비대기"
  }
}
```

---

### 3️⃣ 과원별 오늘의 작업
```
GET /api/farms/{farm_id}/today
```

**경로 파라미터:**
- `farm_id`: 과원 ID (문자열)

**응답 (200):**
```json
{
  "success": true,
  "farm_id": "demo",
  "today_tasks": [
    {
      "task": "열매 관찰",
      "description": "현재 열매 상태 점검",
      "reason": "11월은 수확 준비 시기",
      "priority": "high",
      "sources": [
        {
          "source_id": "agro-center-2024",
          "source_title": "청도 농업기술센터",
          "source_url": "https://example.com"
        }
      ]
    }
  ]
}
```

---

### 4️⃣ 에이전트와 채팅 (SSE 스트리밍)
```
POST /api/farms/{farm_id}/chat
Content-Type: application/json

{
  "message": "오늘 할 일이 뭐야?"
}
```

**응답 (200):**
- Content-Type: `text/event-stream`
- 스트리밍 응답 (Server-Sent Events)

**스트림 데이터:**
```
data: {"tool":"search_knowledge","status":"running"}
data: {"tool":"search_knowledge","status":"complete","result":{...}}
data: {"response":"🌳 오늘은 열매 관찰을 해주세요...","final":true}
```

**클라이언트 예제 (JavaScript):**
```javascript
const eventSource = new EventSource(
  '/api/farms/demo/chat?message=오늘 할 일이 뭐야?'
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.final) {
    console.log("최종 응답:", data.response);
    eventSource.close();
  } else {
    console.log("도구 호출:", data.tool, data.status);
  }
};

eventSource.onerror = (error) => {
  console.error("에러:", error);
  eventSource.close();
};
```

---

### 5️⃣ 작업 제안 조회
```
GET /api/proposals
```

**쿼리 파라미터:**
- `farm_id` (선택): 특정 과원의 제안만 조회
- `status` (선택): "pending" | "approved" | "rejected"

**응답 (200):**
```json
{
  "success": true,
  "proposals": [
    {
      "id": "prop_demo_1730794980",
      "farm_id": "demo",
      "task": "적과 (열매 솎기)",
      "recommended_date": "2026-11-15",
      "reason": "5월 중순이 적과 시기입니다",
      "status": "pending",
      "sources": [
        {
          "source_id": "agro-center-2024-persimmon-01",
          "source_title": "청도 농업기술센터 단감 재배 관리법",
          "source_url": "https://example.com"
        }
      ],
      "ai_generated": true,
      "created_at": "2026-11-05T14:26:20Z"
    }
  ]
}
```

---

### 6️⃣ 제안 승인
```
POST /api/proposals/{proposal_id}/approve
Content-Type: application/json

{
  "approved": true,
  "notes": "일정 추가됨"
}
```

**응답 (200):**
```json
{
  "success": true,
  "proposal_id": "prop_demo_1730794980",
  "status": "approved",
  "calendar_event": {
    "id": "event_demo_1730794980",
    "task": "적과 (열매 솎기)",
    "date": "2026-11-15",
    "farm_id": "demo"
  }
}
```

---

### 7️⃣ 과원별 일정 조회
```
GET /api/farms/{farm_id}/calendar
```

**응답 (200):**
```json
{
  "success": true,
  "farm_id": "demo",
  "calendar_events": [
    {
      "id": "event_demo_1730794980",
      "date": "2026-11-15",
      "task": "적과 (열매 솎기)",
      "description": "과실 크기 2cm 정도일 때 솎아 과실당 잎 50장 비율 유지",
      "status": "scheduled",
      "completed": false
    }
  ]
}
```

---

## 🔐 에러 처리

모든 에러는 다음 형식으로 반환됩니다:

```json
{
  "success": false,
  "error": "에러 메시지",
  "error_code": "INVALID_FARM_ID",
  "timestamp": "2026-11-05T14:26:20Z"
}
```

**일반적인 에러 코드:**
- `400` - Bad Request (필드 누락 등)
- `404` - Not Found (농장/제안 없음)
- `429` - Too Many Requests (속도 제한)
- `500` - Internal Server Error

---

## 📱 UI 컴포넌트 제안

### 페이지 1: 과원 선택
```
[데모 과원 선택]
이름: 청도 데모 과원
위치: 경주시 청도
품종: 청도반시
```

### 페이지 2: 오늘의 작업
```
[오늘의 할 일]

🌳 청도 데모 과원

[시작 대화 버튼]
"오늘 할 일이 뭐야?"
```

### 페이지 3: 채팅 UI
```
사용자: 오늘 할 일이 뭐야?

🤖 에이전트:
🔍 [지식 검색 중...]
🌤️ [날씨 조회 중...]
🌳 [과원 정보 조회 중...]

✅ 응답:
- 열매 관찰
- 토양 수분 확인
...

[제안 일정에 추가] 버튼
```

### 페이지 4: 일정 승인
```
[작업 제안]

제안 ID: prop_demo_...
작업: 적과 (열매 솎기)
날짜: 2026-11-15

[출처]
✓ 청도 농업기술센터
✓ 농촌진흥청

[승인] [거절] 버튼
```

### 페이지 5: 달력
```
[11월 일정]

15일 (화): 적과 (열매 솎기)
20일 (일): 병해충 관찰
...
```

---

## 🔄 통합 흐름

```
1. 사용자 "오늘 할 일이 뭐야?" 입력
   ↓
2. POST /api/farms/demo/chat (SSE 스트리밍 시작)
   ↓
3. 백엔드 에이전트가 4종 도구 호출
   - search_knowledge (지식 검색)
   - get_weather (날씨 조회)
   - get_farm_context (과원 정보)
   - propose_calendar_event (일정 제안)
   ↓
4. SSE로 스트리밍 응답 (도구별 진행 상황 + 최종 응답)
   ↓
5. 사용자가 제안 승인
   POST /api/proposals/{id}/approve
   ↓
6. 일정이 달력에 추가됨
   GET /api/farms/demo/calendar
```

---

## 🧪 테스트 방법

### cURL로 테스트
```bash
# 헬스 체크
curl http://localhost:8000/api/health

# 데모 과원
curl http://localhost:8000/api/farms/demo

# 채팅 (SSE)
curl -N "http://localhost:8000/api/farms/demo/chat?message=오늘%20할%20일이%20뭐야"

# 제안 조회
curl http://localhost:8000/api/proposals

# 제안 승인
curl -X POST http://localhost:8000/api/proposals/prop_demo_1730794980/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### Postman으로 테스트
1. Postman 임포트: [postman_collection.json](./docs/postman_collection.json)
2. 환경 설정: `{{BASE_URL}}` = `http://localhost:8000`
3. 각 요청 실행

---

## 📈 성능 고려사항

- **타임아웃**: 30초 (에이전트 응답 대기)
- **동시 연결**: 최대 100 (컨테이너 설정)
- **캐싱**: 응답 헤더에 `Cache-Control: no-cache` (실시간 업데이트)

---

## 🚀 배포 후 수정 사항

### Azure 배포 시 Base URL 변경
```javascript
// 개발
const API_URL = "http://localhost:8000";

// 배포 후
const API_URL = "https://cheongdo-hackathon-backend-dev.azurecontainerapps.io";
```

### CORS 허용 도메인 추가
프론트엔드 배포 도메인을 CORS 허용 목록에 추가:
```bash
az containerapp update \
  -n cheongdo-hackathon-backend-dev \
  -g cheongdo-hackathon-dev-rg \
  --set-env-vars \
    ALLOWED_ORIGINS="https://gamjapia.kr,https://www.gamjapia.kr"
```

