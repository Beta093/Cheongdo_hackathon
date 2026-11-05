# 감잡아 - 프론트엔드 테스트 & 배포 가이드

## 📋 테스트 시나리오

### 시나리오 1: 홈에서 오늘 할 일로 이동
```bash
1. http://localhost:5173 접속
2. "📋 오늘 할 일 보기" 클릭
3. 오늘의 작업 목록이 표시되는지 확인
```

### 시나리오 2: AI 상담 채팅
```bash
1. 홈에서 "💬 AI 상담하기" 클릭
2. "언제 열매 솎기를 해야 하나요?" 입력
3. AI 응답이 실시간으로 스트리밍되는지 확인
4. 응답 받은 후 새로운 메시지 입력 가능한지 확인
```

### 시나리오 3: 제안 승인
```bash
1. 홈에서 "✅ 제안 확인" 클릭
2. AI 제안 목록이 표시되는지 확인
3. "이 제안 수용하기" 클릭
4. 제안 상태가 "승인됨"으로 변경되는지 확인
```

### 시나리오 4: 캘린더 보기
```bash
1. 홈에서 "📅 일정 보기" 클릭
2. 월별로 정렬된 일정이 표시되는지 확인
3. 체크박스를 클릭해 일정 완료 표시
4. 완료된 일정이 회색으로 처리되는지 확인
```

---

## 🚀 로컬 실행

### 개발 서버 실행
```bash
cd Cheongdo_hackathon/frontend
npm install  # 처음 한 번만
npm run dev  # http://localhost:5173
```

### 백엔드 서버 실행 (동시에 새로운 터미널에서)
```bash
cd Cheongdo_hackathon
docker run -d -p 8000:8000 --name gamjapia-backend gamjapia-backend
# 또는
python -m uvicorn backend.main:app --reload --port 8000
```

### 프로덕션 빌드
```bash
cd frontend
npm run build
npm install -g serve
serve -s dist -l 3000  # http://localhost:3000
```

---

## 🧪 자동화 테스트 (Playwright)

### 설치
```bash
npm install -D @playwright/test
npx playwright install
```

### 테스트 작성 (tests/e2e.spec.ts)
```javascript
import { test, expect } from '@playwright/test';

test.describe('감잡아 E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
  });

  test('홈페이지 로드', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('감잡아');
  });

  test('오늘 할 일 페이지', async ({ page }) => {
    await page.click('button:has-text("오늘 할 일 보기")');
    await expect(page).toHaveURL(/.*\/today/);
  });

  test('AI 채팅', async ({ page }) => {
    await page.click('button:has-text("AI 상담하기")');
    const input = page.locator('input');
    await input.fill('언제 물을 줘야 하나요?');
    await page.click('button:has-text("전송")');
    await expect(page.locator('.bg-gray-100')).toContainText(/\S+/);
  });

  test('제안 승인', async ({ page }) => {
    await page.click('button:has-text("제안 확인")');
    const btn = page.locator('button:has-text("이 제안 수용하기")').first();
    if (await btn.isVisible()) {
      await btn.click();
    }
  });

  test('캘린더', async ({ page }) => {
    await page.click('button:has-text("일정 보기")');
    const checkbox = page.locator('button').first();
    await checkbox.click();
  });
});
```

### 테스트 실행
```bash
npx playwright test
npx playwright test --ui  # UI 모드
```

---

## 📦 Docker 컨테이너

### 프론트엔드 실행
```bash
docker run -d -p 3000:80 --name gamjapia-frontend gamjapia-frontend
# http://localhost:3000 접속
```

### 백엔드 + 프론트엔드 함께 실행
```bash
docker run -d -p 8000:8000 --name backend gamjapia-backend
docker run -d -p 3000:80 --link backend:gamjapia-backend --name frontend gamjapia-frontend
```

---

## ✅ QA 체크리스트

### 기능 검증
- [ ] 홈페이지 로드 확인
- [ ] 각 메뉴 클릭 동작
- [ ] 채팅 SSE 스트리밍 정상 작동
- [ ] 제안 승인 API 호출
- [ ] 캘린더 일정 표시
- [ ] 네비게이션 뒤로가기 동작

### 성능 검증
- [ ] 홈페이지 로드 < 2초
- [ ] API 응답 < 1초
- [ ] 채팅 스트리밍 시작 < 500ms

### 호환성 검증
- [ ] Chrome/Edge 최신 버전
- [ ] Firefox 최신 버전
- [ ] Safari 15+
- [ ] 모바일 반응형 (iPhone, Android)

### 에러 처리
- [ ] 백엔드 연결 실패 시 메시지 표시
- [ ] 네트워크 타임아웃 처리
- [ ] API 오류 시 사용자 친화적 메시지

---

## 🔗 API 통합 포인트

| 엔드포인트 | 메서드 | 용도 |
|-----------|--------|------|
| `/api/farms/demo` | GET | 데모 농장 정보 |
| `/api/farms/{id}/today` | GET | 오늘의 작업 |
| `/api/farms/{id}/chat` | POST | SSE 채팅 (스트리밍) |
| `/api/proposals` | GET | 제안 목록 |
| `/api/proposals/{id}/approve` | POST | 제안 승인 |
| `/api/farms/{id}/calendar` | GET | 재배 캘린더 |

---

## 🌐 배포 후 설정

### Azure Static Web Apps (권장)
```bash
# .env.production 업데이트
VITE_API_URL=https://gamjapia-backend.azurecontainerapps.io/api

# 빌드 및 배포
npm run build
# Azure CLI로 배포
az staticwebapp create --resource-group gamjapia --name gamjapia-frontend --source ./dist
```

### 또는 Azure Container Apps
```bash
# 프론트엔드 이미지를 ACR에 푸시
docker tag gamjapia-frontend gamjapia.azurecr.io/gamjapia-frontend:latest
docker push gamjapia.azurecr.io/gamjapia-frontend:latest

# Bicep에서 프론트엔드 Container App 추가
# (backend와 동일한 방식)
```

---

## 📝 주요 파일 구조

```
frontend/
├── src/
│   ├── pages/
│   │   ├── Home.jsx         # 홈페이지
│   │   ├── Today.jsx        # 오늘 할 일
│   │   ├── Chat.jsx         # AI 상담
│   │   ├── Proposals.jsx    # 제안 확인
│   │   └── Calendar.jsx     # 캘린더
│   ├── services/
│   │   └── api.js           # API 클라이언트
│   ├── App.jsx              # 라우팅
│   ├── main.jsx             # 진입점
│   └── index.css            # 전역 스타일
├── Dockerfile               # 프로덕션 이미지
├── nginx.conf               # Nginx 설정
├── package.json
├── vite.config.js
└── .env.development         # 개발 환경 설정
```

---

## 🎯 다음 단계

1. **로컬 테스트**: `npm run dev` 후 모든 페이지 확인
2. **자동화 테스트**: Playwright로 E2E 테스트 작성
3. **Docker 테스트**: `docker run -p 3000:80 gamjapia-frontend`
4. **Azure 배포**: 팀의 DevOps 담당자가 deploy.sh 실행
5. **프로덕션 테스트**: 배포된 URL에서 전체 플로우 검증
