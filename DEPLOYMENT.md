# Azure 배포 가이드

## 🚀 빠른 시작

### 전제 조건
1. Azure 구독 (프리 tier 가능)
2. Azure CLI 설치: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
3. Docker 설치 (로컬 빌드 시)
4. Git Bash 또는 Bash (Windows는 WSL 또는 Git Bash)

### 배포 단계

#### 1️⃣ Azure 로그인
```bash
az login
```

#### 2️⃣ 배포 스크립트 실행
```bash
cd /path/to/Cheongdo_hackathon
chmod +x deploy.sh
./deploy.sh dev koreacentral
```

**파라미터:**
- `dev`: 환경 (dev/prod) - 기본값: dev
- `koreacentral`: 지역 (기본값: koreacentral)

#### 3️⃣ 배포 후 확인
```bash
# 헬스 체크
curl https://<CONTAINER_APP_URL>/api/health

# 데모 과원 조회
curl https://<CONTAINER_APP_URL>/api/farms/demo
```

---

## 📊 배포되는 리소스

| 리소스 | SKU | 비용 예상 | 설명 |
|--------|-----|---------|------|
| **Container Registry** | Basic | ~$0.10/일 | 도커 이미지 저장소 |
| **Container Apps** | Pay-as-you-go | ~$0.50/일 | FastAPI 백엔드 호스팅 |
| **Log Analytics** | 1GB/일 | 프리 | 로그 및 모니터링 |

**총 예상 비용: ~$15-20/월** (프리 tier 사용)

---

## 🔧 수동 배포 (스크립트 사용 불가 시)

### 1단계: 리소스 그룹 생성
```bash
az group create \
  --name cheongdo-hackathon-dev-rg \
  --location koreacentral
```

### 2단계: Bicep 배포
```bash
az deployment group create \
  --resource-group cheongdo-hackathon-dev-rg \
  --template-file bicep/main.bicep \
  --parameters projectName=cheongdo-hackathon environment=dev
```

### 3단계: 이미지 빌드 및 푸시
```bash
# 1. 로컬 빌드
cd backend
docker build -t cheongdo-hackathon:latest .

# 2. Registry 정보 확인
REGISTRY_LOGIN_SERVER=$(az acr list -g cheongdo-hackathon-dev-rg \
  --query "[0].loginServer" -o tsv)

# 3. Registry 로그인
az acr login --name $(echo $REGISTRY_LOGIN_SERVER | cut -d. -f1)

# 4. 태그 및 푸시
docker tag cheongdo-hackathon:latest $REGISTRY_LOGIN_SERVER/cheongdo-hackathon:latest
docker push $REGISTRY_LOGIN_SERVER/cheongdo-hackathon:latest
```

### 4단계: Container App 업데이트
```bash
az containerapp update \
  --name cheongdo-hackathon-backend-dev \
  --resource-group cheongdo-hackathon-dev-rg \
  --image $REGISTRY_LOGIN_SERVER/cheongdo-hackathon:latest
```

---

## 🐛 문제 해결

### Docker Desktop이 없는 경우
Azure Container Registry 빌드 작업 사용:
```bash
az acr build \
  --registry <registry-name> \
  --image cheongdo-hackathon:latest \
  --file backend/Dockerfile \
  backend/
```

### 배포 실패 (권한 오류)
```bash
# 구독에서 Owner/Contributor 역할 확인
az role assignment list --output table
```

### Container App 접속 불가
```bash
# 로그 확인
az containerapp logs show \
  --name cheongdo-hackathon-backend-dev \
  --resource-group cheongdo-hackathon-dev-rg \
  --follow
```

---

## 📝 환경 변수 설정

배포 후 Container App에 환경 변수 추가:

```bash
az containerapp update \
  --name cheongdo-hackathon-backend-dev \
  --resource-group cheongdo-hackathon-dev-rg \
  --set-env-vars \
    GITHUB_TOKEN=your-token \
    DEBUG=false \
    ENVIRONMENT=dev
```

---

## 🧪 배포 후 테스트

### 1. 헬스 체크
```bash
curl https://<APP_URL>/api/health
# 응답: {"status":"healthy","timestamp":"2026-11-05T..."}
```

### 2. 데모 과원
```bash
curl https://<APP_URL>/api/farms/demo
```

### 3. 에이전트 테스트
```bash
curl -X POST https://<APP_URL>/api/farms/demo/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"오늘 할 일이 뭐야?"}'
```

---

## 🔐 보안 체크리스트

- [ ] GITHUB_TOKEN은 Azure Key Vault에 저장
- [ ] CORS 설정 검토 (필요 시 제한)
- [ ] HTTPS 강제 (자동 설정됨)
- [ ] 컨테이너 이미지 스캔 (ACR 기본 제공)
- [ ] 로그 보존 정책 설정 (프로덕션)

---

## 💡 다음 단계

1. **Cosmos DB 통합** - 현재 in-memory → 데이터베이스
2. **프론트엔드 배포** - React 앱을 Azure Static Web Apps에
3. **모니터링** - Application Insights 연결
4. **CI/CD** - GitHub Actions 자동 배포 설정

