#!/bin/bash
# deploy.sh - Azure에 감잡아 백엔드 배포

set -e

echo "🚀 감잡아 Azure 배포 시작"
echo "================================"

# 설정
PROJECT_NAME="cheongdo-hackathon"
ENVIRONMENT="${1:-dev}"
LOCATION="${2:-koreacentral}"
RESOURCE_GROUP="${PROJECT_NAME}-${ENVIRONMENT}-rg"

echo "📍 배포 설정:"
echo "  프로젝트: $PROJECT_NAME"
echo "  환경: $ENVIRONMENT"
echo "  위치: $LOCATION"
echo "  리소스 그룹: $RESOURCE_GROUP"
echo ""

# 1. Azure CLI 설정 확인
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI가 설치되지 않았습니다."
    echo "   https://docs.microsoft.com/en-us/cli/azure/install-azure-cli 에서 설치하세요."
    exit 1
fi

# 2. 로그인 확인
echo "🔑 Azure 계정 확인 중..."
if ! az account show &> /dev/null; then
    echo "🔐 Azure에 로그인하세요:"
    az login
fi

# 3. 리소스 그룹 생성
echo "📦 리소스 그룹 생성/확인: $RESOURCE_GROUP"
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --tags project="$PROJECT_NAME" environment="$ENVIRONMENT" \
    || true

# 4. Dockerfile 빌드
echo "🔨 Docker 이미지 빌드 중..."
cd "$(dirname "$0")/backend"
docker build -t "${PROJECT_NAME}:latest" .
cd - > /dev/null

# 5. Container Registry 로그인 및 푸시
echo "📤 이미지를 Azure Container Registry에 푸시 중..."

# Bicep 배포로 Registry 정보 얻기
echo "⚙️  Bicep 배포 중..."
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file bicep/main.bicep \
    --parameters \
        location="$LOCATION" \
        projectName="$PROJECT_NAME" \
        environment="$ENVIRONMENT" \
    --query "properties.outputs" \
    --output json)

REGISTRY_LOGIN_SERVER=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.containerRegistryLoginServer.value')
REGISTRY_NAME=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.containerRegistryName.value')
CONTAINER_APP_URL=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.containerAppUrl.value')

echo "✅ 배포 완료!"
echo ""
echo "📊 배포 결과:"
echo "  Container Registry: $REGISTRY_LOGIN_SERVER"
echo "  Backend URL: $CONTAINER_APP_URL"
echo ""
echo "🔐 Registry에 로그인 중..."
az acr login --name "$REGISTRY_NAME"

echo "📦 이미지 태그 및 푸시..."
docker tag "${PROJECT_NAME}:latest" "${REGISTRY_LOGIN_SERVER}/${PROJECT_NAME}:latest"
docker push "${REGISTRY_LOGIN_SERVER}/${PROJECT_NAME}:latest"

echo ""
echo "✨ 배포 완료!"
echo "🌐 앱 URL: $CONTAINER_APP_URL"
echo "💡 헬스 체크: $CONTAINER_APP_URL/api/health"
