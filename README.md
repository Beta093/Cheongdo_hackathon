# 감잡아

청도반시 초보 농부를 위한 P0 코드 초안입니다. 데모 과원 → 오늘의 할 일 → 채팅 → 일정 제안 승인 → 일정 조회를 대상으로 합니다. Python 3.12 / FastAPI와 빌드 없는 한국어 단일 페이지를 같은 서버에서 제공합니다.

**현재 상태:** 파일 작성만 수행했습니다. 패키지 설치, 테스트·린트 실행, 네트워크 조회, Docker 빌드, Azure 배포, git commit/push는 수행하지 않았습니다. 실제 Copilot 응답과 컨테이너 호환성은 미검증입니다. `references/` 원본은 수정하지 않았으며 PRD/TRD를 루트에 복사했습니다.

## 구조

```text
backend/
  app/         API, 스키마, 정책 검사, 요청 제한, 인메모리 저장소, 서비스
  agents/      Model 인터페이스, Copilot 어댑터, 허용 목록 권한 핸들러, FakeModel
  tools/       요청별 지식 검색·저장 권한 없는 일정 제안 도구
  tests/       가짜 모델을 사용하는 P0 pytest
frontend/      index.html, app.js, style.css
data/knowledge/  수확·곶감 준비 자료 틀 6개 (전부 확인 필요)
infra/         Container Apps + ACR + Log Analytics Bicep 초안
Dockerfile     Python 3.12 + Node 22 + Copilot CLI
azure.yaml     azd 서비스 구성 초안
references/    제공받은 원본 문서
```

## 로컬 실행 (사용자가 별도로 실행)

아래 설치 명령은 향후 실행용 안내이며 이번 작업에서 실행하지 않았습니다. Python 3.12가 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
$env:GAMJABA_MODEL = 'fake'
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers --no-access-log
```

브라우저에서 `http://127.0.0.1:8000`에 접속하고 **데모 과원으로 시작**을 누릅니다. 프런트엔드를 `file://`로 열지 마세요. 가짜 모드는 화면에 명시되며 실제 모델이 실패했을 때 자동 전환되지 않습니다.

실제 모델 모드의 기본값은 `copilot`입니다. Copilot CLI가 PATH에 있어야 하며, 참조 문서의 검증 버전은 `@github/copilot@1.0.105`입니다. 토큰은 비밀 관리 도구 등으로 **프로세스 환경변수 `COPILOT_GITHUB_TOKEN`에만 주입**하세요. 코드·설정 파일에 값을 적지 마세요. 토큰이 없으면 모델 요청이 명시적으로 실패하며 로컬 로그인 인증으로 우회하지 않습니다. `.env`는 자동 로드하지 않습니다.

```powershell
$env:GAMJABA_MODEL = 'copilot'
# COPILOT_GITHUB_TOKEN은 별도의 안전한 환경변수 주입 절차로 설정
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers --no-access-log
```

## 테스트와 린트 (미실행)

저장소 루트에서 실행합니다. 테스트는 외부 모델·CLI·네트워크·토큰이 필요하지 않습니다. 라이브 어댑터의 import와 호출은 지연되어 있습니다.

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
.\.venv\Scripts\python -m ruff check backend
```

정책 패턴, 미측정 수치 차단, 요청별 출처 ID 검증, SSE 순서·검사 전 본문 미노출, 승인 멱등·동시 승인·승인/거절 경합, 세션 격리·만료, 길이/본문 크기·세션/IP 속도 제한, 모델 장애·타임아웃, 형식 재시도 상한, 오늘의 할 일 캐시, 미검증 자료 처리를 검사합니다. 검토된 자료를 가정하는 합성 테스트 fixture의 `example.org`는 실제 농업 근거가 아닙니다.

## API 계약

모든 `/api/*` 요청은 UUID 형식 `X-Session-Id` 헤더가 필수입니다. 로그인은 없으며 브라우저가 생성한 UUID를 localStorage에 보관합니다. 이 ID는 세션 접근 키이므로 다른 사람에게 공유하지 마세요. 쿠키와 CORS는 사용하지 않습니다.

| 메서드 | 경로 | 응답 |
| --- | --- | --- |
| GET | `/api/health` | 프로세스 상태, 모델 모드, 설정 여부 (실제 모델 연결 검사는 아님) |
| GET | `/api/farms/demo` | 읽기 전용 데모 과원 + 세션 ID |
| GET | `/api/farms/demo/today` | `tasks`, `notices`, 날짜, AI 표시, 날씨 정보 없음 |
| POST | `/api/farms/demo/chat` | JSON `{"message":"수확 준비를 알려줘"}` → SSE |
| GET | `/api/farms/demo/calendar` | 해당 세션의 승인된 일정 배열 |
| POST | `/api/proposals/{id}/approve` | 생성된 일정; 재승인 시 같은 일정 |
| POST | `/api/proposals/{id}/reject` | 거절된 제안; 재거절도 멱등 |

정상 SSE 순서는 `status` → `tool_call`(0회 이상, 실제 도구 시작만) → `message`(검사 후 한 번) → `done`입니다. 오류는 `error` → `done`이며 본문을 부분 전송하지 않습니다. 도구 인자·검색 원문·모델 원문은 진행 이벤트에 포함되지 않습니다. JSON 형식 실패만 1회 재시도하며, 재시도에도 실패하면 고정된 `확인 필요` 메시지를 반환합니다. UI 재시도는 실패한 요청당 최대 2회입니다. 마지막 `done`은 스트림 종료를 의미하며 성공 여부는 `ok`로 표시합니다.

누락/잘못된 입력은 422, 요청 본문 16KiB 초과는 413, 한도 초과는 429, 없는 과원/다른 세션의 제안은 404, 만료·상태 충돌은 409입니다. today의 모델 오류는 503, 정책 오류는 502입니다. 이미 시작한 SSE의 오류는 HTTP 200 내부의 `error` 이벤트로 전달합니다.

## 저장·보호 정책

- 세션별 인메모리 저장, 유휴 세션 TTL 2시간, 제안 TTL 30분. 세션 최대 1,000개, 세션당 제안 최대 100개. 재시작·재배포 시 데이터가 사라집니다.
- `(세션, 과원, Asia/Seoul 날짜)`로 오늘의 할 일을 캐시합니다. 과원·날짜 키에 세션을 추가해 개인화 결과가 다른 방문자에게 섞이지 않게 했습니다. 동일 세션의 동시 today 요청은 한 번만 생성합니다.
- 도구는 요청 내 `Proposal(pending)`만 만듭니다. 최종 출력 전체 검사를 통과한 뒤 서버가 승인 대기 목록에 등록하며, **CalendarEvent는 승인 API에서만** 저장합니다. 단일 프로세스 `RLock`으로 승인·거절을 원자적으로 처리합니다.
- 출처는 해당 모델 시도의 검색 결과 ID와 로컬 `reviewed: true` 메타데이터를 서버에서 대조합니다. 작업 제목은 검토된 문서의 `task_title`과 같아야 합니다. 존재하는 다른 문서의 ID라도 이번 요청에 검색되지 않았다면 거부합니다.
- 채팅 최대 2,000자, 세션당 60회/분·IP당 240회/분(API 전체), 모델 동시 호출 2개, 요청 대기 포함 타임아웃 40초, 모델 시도당 도구 호출 최대 12회·일정 제안 최대 3개. 최근 대화는 세션별 4턴만 사용합니다.
- `custom-tool`이면서 두 도구 이름과 정확히 일치할 때만 `PermissionDecisionApproveOnce`, 그 외에는 `PermissionDecisionUserNotAvailable`입니다. 내장 셸·파일·URL 권한은 승인하지 않습니다.
- AI 본문과 일정 설명에 보수적인 농약/용량·미측정 수치 패턴 검사를 적용합니다. 근거 없는 자유 답변은 고정 안내로 대체합니다. 이는 의미적 사실 검증이나 모든 제품명 탐지를 보장하지 않습니다. 원문 검토와 실제 모델 대상 정책 평가가 추가로 필요합니다.
- 프런트엔드는 텍스트를 `textContent`로 렌더링하고 검토된 HTTPS 출처만 링크합니다. 서버는 CSP 등 보안 헤더를 적용하고 사용자 원문이나 SDK 예외 내용을 로그로 남기지 않습니다.
- **workers=1, replica=1** 전제입니다. 여러 프로세스·인스턴스에서는 승인 원자성·세션·제한 카운터가 공유되지 않습니다. 재배포 중 구·신 리비전 전환도 세션 연속성을 보장하지 않습니다.

## 지식 자료 상태

외부 조회가 금지된 작업이므로 농업 출처를 확인하거나 인용했다고 주장하지 않습니다. 6개 문서는 수확 판단, 도구, 선별·운반, 가공 적합성, 건조 공간, 전문가 상담의 **확인 질문용 틀**입니다. `source_url`과 `retrieved_at`은 `확인 필요`, `reviewed`는 false입니다. 실제 수확 날짜·가공 조건·사용량을 지어내지 않았습니다.

따라서 기본 데이터로는 today에 확인 필요 안내만 나오며, 검토된 자료가 없으면 승인 가능한 일정 제안도 만들지 않습니다. 완전한 승인 흐름은 합성 자료를 사용하는 테스트로 작성되어 있습니다. 실제 데모 전에 담당자가 원문·라이선스를 확인하고 아래 형식으로 큐레이션해야 합니다. 사실 검토 없이 플래그만 변경하면 안 됩니다.

```text
---
source_title: "실제로 확인한 원문 제목"
source_url: "실제로 확인한 HTTPS 원문 URL"
retrieved_at: "실제 조회 날짜 YYYY-MM-DD"
reviewed: true
task_title: "검토된 작업 제목"
---
해당 제목의 작업을 뒷받침하는 짧고 검토된 내용
```

파서는 평면 프런트매터만 지원합니다. 문자열은 JSON 큰따옴표, 불리언은 true/false로 씁니다. 외부 사이트를 자동으로 조회하지 않으며, `reviewed`는 담당자의 검토 표시입니다.

## 컨테이너·Azure 초안과 미완 항목

`Dockerfile`은 Python 3.12, Node 22, Copilot CLI 1.0.105를 구성합니다. 실행 시 비루트 사용자와 단일 uvicorn worker를 사용합니다. 이미지를 실제로 빌드하거나 패키지 의존성을 해결하지 않았습니다. Python 3.12 지원·고정 버전 간 호환성·CLI 플랫폼 바이너리를 먼저 검증해야 합니다. SDK 생성자/응답·권한 콜백은 `references/TRD.md`의 spike를 기준으로 작성했으며, 이 저장소에서 실제 호출한 결과가 아닙니다.

`azure.yaml`과 `infra/`는 Container Apps(최소/최대 replica 1), ACR Basic, Log Analytics를 만듭니다. 토큰은 Bicep `@secure()` 매개변수 → Container Apps secret → `secretRef` 환경변수 경로입니다. 토큰을 출력하지 않습니다. ACR은 P0용 admin credential을 secret으로 사용하며 Managed Identity 전환은 P1입니다.

향후 배포 검증 명령은 `azd up`입니다. 이번 작업에서는 실행하지 않았습니다. 다음 항목은 배포 전에 확정해야 합니다.

1. 초기 프로비저닝은 임시 hello-world 이미지(포트 80)이며 실제 감잡아 이미지가 아닙니다. 실제 이미지는 포트 8000입니다. ACR 빌드 후 **`containerImage` 매개변수를 실제 앱 이미지로 지정해 다시 프로비저닝**하여 ingress와 프로브도 8000으로 전환해야 합니다. `azd deploy`의 이미지 교체만으로 포트가 자동 갱신된다고 가정하지 않습니다. 실제 이미지 매개변수 전달·azd 서비스 연결을 확정하기 전에는 초안의 단일 명령 배포 성공을 보장하지 않습니다.
2. `main.parameters.json`의 환경변수 치환과 azd 버전 동작, Bicep API 버전·구문을 검증해야 합니다. 비밀값을 azd의 로컬 `.azure` 파일에 저장하지 말고 안전한 환경변수/배포 비밀 입력을 사용하세요.
3. 실제 모델 응답·도구 호출·승인·조회 및 모바일 화면을 수동 검증해야 합니다. 가짜 모드는 필수 기술 실사용 증명이 아닙니다.
4. IP 제한은 직접 연결 peer를 사용합니다. 기본 실행에서 전달 헤더를 신뢰하지 않으므로 Azure 프록시 뒤에서는 여러 방문자가 같은 IP 한도를 공유할 수 있습니다. 배포 환경의 신뢰 가능한 프록시 범위를 확인한 뒤 설정해야 합니다.
5. Copilot 공개 데모 구독 사용 허용·과금과 토큰 권한/만료, Azure 예산 알림은 별도 확인이 필요합니다. 농업 데이터 검토·실제 배포·완료 정의의 수동 스모크는 미완입니다.

과원 등록, 날씨 연동, 작업 기록, 로그인, 일정 수정/삭제, Cosmos DB 등 P1/P2는 구현하지 않았습니다. 참조 AGENTS에는 대회 코딩 도구 제한도 있으므로, 이 초안의 제출 적합성은 대회 규칙에 따라 별도 확인해야 합니다.
