# TRD — 감잡아 기술 설계

상태: P1 구현 반영 (2026-11-05). Python 실행과 외부 연동 검증은 대기 중.

## 구성과 경계

Python 3.12/FastAPI가 정적 화면과 API를 제공한다. 기존 실행 연결·출처 검사·정책을 유지한다. backend/app/repository.py는 저장소 계약, store.py는 인메모리, cosmos.py는 영속 어댑터, weather.py는 예보, telemetry.py는 선택 추적을 담당한다.

읽기 전용 과원 조회는 요청에 묶인 과원·최근 기록 30개·승인 일정의 복사본을 반환한다. 다른 과원 ID는 거부하며 문맥에 저장소 자체를 주지 않는다. 기록과 외부 자료는 신뢰하지 않는 데이터 블록으로 전달한다. 최근 대화는 과원별 4턴이다.

날씨 조회는 바인딩된 과원 지역과 1~7일만 허용하고 요청 내 같은 일수는 재사용한다. 두 읽기 기능만 허용 목록에 추가한다. 셸·파일·임의 URL·기록 쓰기·직접 승인 권한은 없다. SSE는 내부 호출명·인자·원문 대신 일반 상태만 보낸다.

제안은 요청 메모리에만 만들고 전체 응답 검사를 통과한 후 대기 목록에 등록한다. 승인 API만 일정을 저장한다. 반복 승인·거절은 멱등이며 승인/거절 경쟁은 하나만 성공한다.

## API와 검증

| 메서드 | 경로 | 상태 |
| --- | --- | --- |
| GET | /api/health, /api/farms/demo | 기존 |
| GET | /api/farms/{id}/today, /calendar | 등록 과원으로 확장 |
| POST | /api/farms/{id}/chat | 등록 과원으로 확장 |
| POST | /api/proposals/{id}/approve 또는 /reject | 기존 계약 |
| POST | /api/farms | P1 완료, 201 |
| GET | /api/farms/{id} | 등록 과원 복원, 세션 확인 |
| GET/POST | /api/farms/{id}/logs | P1 완료, 목록/201 |
| PUT/DELETE | /api/farms/{id}/logs/{logId} | CRUD, 전체 교체/204 |
| GET | /api/farms/{id}/weather?days=3 | P1 완료 |

모든 API는 UUID X-Session-Id를 요구한다. 등록은 name·region 1~80자, cultivar=청도반시, plantedYear 정수 1900~서울 올해, areaM2 양수 최대 10,000,000이 필수다. 기록은 type=work|symptom|harvest, date=YYYY-MM-DD(1900~서울 오늘), note 1~2,000자다. 수확에만 amount 양수 kg가 필수다. 비유한 수·불리언 수치·빈 값·추가 필드를 거부한다. 검증 422, 타 세션/없는 객체 404, 만료·충돌 409를 반환한다.

## 저장 계약

GAMJABA_STORE 기본 memory, 선택 cosmos. Cosmos는 COSMOS_ENDPOINT가 필수이며 데이터베이스/컨테이너 기본 gamjaba/state다. 관리 ID를 기본 인증으로 사용하고 선택 키는 환경변수만 읽는다. SDK 대신 가짜 컨테이너를 주입할 수 있다.

인메모리는 잠금으로 직렬화한다. Cosmos는 실제 과원 ID를 /farmId 파티션 키로 사용한다. 세션 ID+세대 ID 문서 하나에 기록·제안·일정·캐시·대화를 넣고 ETag 조건부 교체한다. 승인 상태·일정 삽입·캐시 버전 증가가 단일 쓰기다. 409/412 충돌은 최신 상태로 최대 12회 재시도한다.

예약 파티션의 단일 디렉터리는 세션 유휴 만료·세대·과원 ID만 저장하며 조건부 갱신한다. 논리 접근 TTL은 유휴 2시간이다. 같은 ID로 다시 시작해도 세대가 달라 과거 상태는 접근 불가다. 제안 TTL은 30분이며 승인 완료 건의 반복 승인은 세션이 유효하면 같은 일정이다.

과원 물리 TTL은 4시간이고 세션 활동 때 모든 소유 과원을 갱신한다. 논리 접근 만료와 물리 정리를 구분한다. 만료 디렉터리 항목은 다음 접근에 정리한다. 과원 등록은 문서 생성 후 디렉터리 연결이며 고아 문서는 접근 불가·TTL 정리된다. 최대 세션 1,000개·등록 과원 20개·과원당 기록 200개/제안 100개다. 문서 1.9MB 상한과 단일 디렉터리는 데모 규모의 제약이다.

## 캐시·기록 반영

캐시는 세션 내부 (과원, 서울 날짜) 키다. 기록 생성·교체·삭제·승인 시 해당 과원 캐시를 제거하고 버전을 증가시킨다. 생성 시작 버전과 저장 버전이 다르면 캐시 저장을 거부한다. 다른 과원의 캐시는 유지한다. 오늘 work 메모가 작업 제목과 같거나 오늘 승인된 제목이면 재제안에서 제외한다. 임의 메모 의미를 완료로 확정하지 않는다.

## 날씨·관측성

키 미설정은 네트워크 없이 날씨 정보 없음이다. WEATHER_API_KEY만 읽고 고정 HTTPS 제공 경로를 사용한다. 일수 1~7, 타임아웃 기본 3초. 날짜·숫자 범위·최저/최고를 검증한다. 정상은 available/summary/days/source, 오류·지연·비정상 형식은 available=false로 반환한다. 원본 예외·키·URL은 로그에 남기지 않는다.

날씨가 없을 때 날씨에 근거한 답변·작업·일정은 보수적으로 차단한다. 예보는 별도 검증 필드로 표시하며 현장 측정과 구분한다. 패턴 방어의 의미적 한계와 실제 요금제·한글 지역 검증은 남아 있다.

APPLICATIONINSIGHTS_CONNECTION_STRING이 있을 때만 OpenTelemetry 공급자·전송기를 등록한다. 경로 템플릿·메서드·상태·시간만 추적하며 본문·질문·메모·세션 ID·헤더·쿼리·전체 URL·예외를 수집하지 않는다.

## 인프라와 실행

Bicep에 Cosmos serverless, Key Vault, 관리 ID, ACR 읽기·비밀 읽기·Cosmos 데이터 역할, Application Insights를 추가한다. 토큰·선택 날씨 키·추적 문자열은 Key Vault 참조다. ACR 관리자 및 배포 Cosmos 키 인증은 끈다.

두 저장 모드 모두 workers=1, replica=1이다. Cosmos 저장 원자성과 별개로 요청 제한·동시 생성 한도는 프로세스 내부이므로 공유화 전 확장하지 않는다.

기존 초기 이미지 포트 80→실제 앱 8000 전환에는 실제 containerImage로 재프로비저닝이 필요하다. Bicep 컴파일·RBAC 전파·관리 ID·새 패키지 조합·실제 클라우드 호출은 미검증이다. 외부 접근 금지로 공식 문서 확인을 했다고 주장하지 않는다.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend e2e/server.py
node --check frontend/app.js
```

향후 배포 검증: az bicep build --file infra/main.bicep, azd up. 이번 작업에서 실행하지 않았다.

## 채팅 이미지 입력

POST /api/farms/{id}/chat의 JSON에 선택 image={mimeType,data}를 추가한다. JPEG·PNG·WebP만 허용하며 엄격한 base64 디코딩, 최대 5MB, 매직 바이트를 검증하고 위반은 422로 처리한다. 채팅 JSON 본문만 base64 크기와 기존 본문 여유만큼 확장한다. 다른 엔드포인트 제한은 유지한다. 이미지 입력은 선택 인자로 전달하여 세션 send의 blob attachment(data, mimeType, displayName)에 넣는다. 첨부를 대화 저장소·로그·오류 응답에 남기지 않는다. 기존 권한 허용 목록·세션 격리·승인 전 일정 저장 금지를 유지한다. CSP 변경 없이 파일명과 크기를 표시한다. 실제 연결 검증은 별도로 필요하다.
