# 배포 체크리스트 (Deploy Checklist)

## ✅ 백엔드 준비 완료

### 코드 상태
- [x] FarmAdvisorAgent (SDK 통합)
- [x] PolicyChecker (책임 있는 AI)
- [x] FastAPI 엔드포인트 7개
- [x] 테스트 14/14 통과
- [x] Dockerfile 작성
- [x] .dockerignore 작성

### Azure 인프라
- [x] Bicep 템플릿 (Container Registry + Container Apps + Log Analytics)
- [x] 배포 스크립트 (deploy.sh)
- [x] 배포 가이드 (DEPLOYMENT.md)
- [x] CORS 환경별 설정

### 보안 & 최적화
- [x] 헬스 체크 엔드포인트 (/api/health)
- [x] 환경 변수 분리 (DEBUG, ENVIRONMENT)
- [x] HEALTHCHECK 설정 (Dockerfile)
- [x] CPU/메모리 제한 설정 (Bicep)

---

## 🚀 배포 명령어

### 옵션 1: 자동 배포 스크립트
```bash
cd /Users/isabel/.copilot/chats/2026-11-05/animated-doodle-f71d6d11/Cheongdo_hackathon
./deploy.sh dev koreacentral
```

### 옵션 2: 수동 배포 (Bicep만)
```bash
az group create -n cheongdo-hackathon-dev-rg -l koreacentral
az deployment group create \
  -g cheongdo-hackathon-dev-rg \
  -f bicep/main.bicep \
  -p projectName=cheongdo-hackathon environment=dev
```

---

## 📊 예상 배포 시간

| 단계 | 시간 |
|------|------|
| Azure 로그인 | 1분 |
| 리소스 그룹 생성 | 1분 |
| Bicep 배포 (리소스 생성) | 5-10분 |
| Docker 빌드 | 3-5분 |
| Registry 푸시 | 2-3분 |
| Container App 배포 | 3-5분 |
| **총 예상 시간** | **~20-30분** |

---

## 📝 배포 후 필수 작업

### 1. 환경 변수 설정
```bash
az containerapp update \
  -n cheongdo-hackathon-backend-dev \
  -g cheongdo-hackathon-dev-rg \
  --set-env-vars \
    ENVIRONMENT=prod \
    DEBUG=false \
    GITHUB_TOKEN=$GITHUB_TOKEN
```

### 2. 헬스 체크 확인
```bash
curl https://<CONTAINER_APP_URL>/api/health
```

### 3. 데모 API 테스트
```bash
curl https://<CONTAINER_APP_URL>/api/farms/demo
```

### 4. 로그 모니터링
```bash
az containerapp logs show \
  -n cheongdo-hackathon-backend-dev \
  -g cheongdo-hackathon-dev-rg \
  --follow
```

---

## 🔄 다음 단계 우선순위

### Phase 3: Azure 배포 (현재 단계)
- [x] Dockerfile & Bicep 작성
- [ ] Docker 빌드 & ACR 푸시
- [ ] Container App 배포
- [ ] 배포된 URL 확인

### Phase 4: 프론트엔드 (다른 팀원)
- [ ] React + Vite 프로젝트
- [ ] Azure Static Web Apps 배포
- [ ] 백엔드 API 통합

### Phase 5: E2E 테스트
- [ ] Playwright 테스트 작성
- [ ] 통합 테스트 실행
- [ ] PRD 체크리스트 확인

---

## 💡 팀 역할 분담 제안

| 역할 | 담당자 | 작업 |
|------|--------|------|
| **AI/Agent** | Isabel (현재) | ✅ 백엔드 + SDK 통합 + 배포 준비 |
| **DevOps** | ? | Azure 배포 실행 + 모니터링 설정 |
| **프론트엔드** | ? | React UI 개발 + 배포 |
| **테스트/QA** | ? | E2E 테스트 + 통합 검증 |

**Isabel의 다음 작업:**
1. ✅ 백엔드 준비 완료
2. → 프론트엔드 팀과 API 명세 확인
3. → 팀이 배포 실행 중 필요 시 지원

---

## 🎯 해커톤 일정 (예상)

- **지금**: 백엔드 + SDK 통합 완료
- **30분 내**: Azure 배포
- **60분 내**: 프론트엔드 + 백엔드 통합
- **90분 내**: E2E 테스트 + 최종 검증
- **120분 내**: 데모 영상 + 발표 자료 준비

