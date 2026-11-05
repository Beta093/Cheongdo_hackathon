# TDD — 감잡아 검증 계획

상태: P1 테스트 작성 완료 (2026-11-05). 기존 P0 41개 유지. Python·린트 실행 파일 접근 거부로 pytest를 실행하지 못했으며 통과 개수는 보고하지 않는다.

## 전략

먼저 등록·기록·날씨·캐시 테스트를 작성한 후 구현했다. 실행 환경이 막혀 Red/Green 결과는 확보하지 못했다. 외부 실행·날씨·DB를 가짜로 대체하고 실제 연동과 배포 검증은 분리한다.

| 범위 | 검사 |
| --- | --- |
| P0 | 정책·출처·SSE·승인 멱등/경쟁·세션·길이/속도 제한·실패/지연 |
| 등록 | 201/422, 필수 필드·연도·면적·문자열, 타 세션 거부 |
| 기록 | 세 종류 생성·목록·교체·삭제, 날짜·메모·수확량, 과원·세션 격리 |
| 조회 | 기록 반영, 복사본, 다른 과원 거부, 읽기 전용 권한 |
| 캐시 | 기록·승인 무효화, 이전 버전 거부, 완료 제목 재제안 제외 |
| 날씨 | 정상/실패/지연/미설정, 일수, 비밀 비노출, 근거 없는 단정 차단 |
| 저장소 | 인메모리·가짜 Cosmos 동일 계약, TTL·대화 격리·승인 |
| Cosmos 추가 | 재시작, ETag 충돌 재시도, 독립 어댑터 동시 승인, 상태/일정 단일 쓰기 |
| 관측성 | 연결 문자열 없을 때 초기화·전송 없음 |
| E2E | 데모→할 일→질문→승인→기록, 작성만 함 |

## 파일

- backend/tests/test_p1.py: 입력·API·날씨 가짜 클라이언트.
- backend/tests/test_p1_boundaries.py: 읽기 경계, 메모 지시문을 데이터로 취급, 출력 차단, CRUD API, 관측성 비활성.
- backend/tests/test_repository_contract.py: 같은 테스트를 두 저장소에 적용. 가짜 컨테이너에서 파티션·ETag를 강제.
- e2e/flow.spec.js: 모바일 크기의 사용자 흐름 1개.
- e2e/server.py 및 fixtures/: 운영 농업 데이터와 분리한 합성 자료.

저장소 계약은 타 세션 접근, 복사본, 과원별 대화, 기록 CRUD, 캐시 버전, 멱등 승인/거절, 승인 경쟁, 제안 TTL, 유휴 갱신, 만료 후 과거 상태 부활 금지를 검사한다. 실제 Cosmos SDK·RBAC·물리 TTL 정리 서비스는 별도 검증 대상이다.

## 명령·결과

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend e2e/server.py
node --check frontend/app.js
node --check e2e/flow.spec.js
node --check e2e/playwright.config.js
git diff --check
```

이번 작업은 JS 구문·공백 검사만 통과했다. pytest·린트는 접근 거부로 실행 불가였으며 패키지를 설치하지 않았다.

E2E는 실행하지 않는다. 이후 준비된 환경에서 e2e 디렉터리의 npm test를 사용한다. E2E_SERVER_COMMAND로 루트 기준 서버 명령을 지정할 수 있으며 e2e.server:app을 8011에서 실행한다. 전용 서버는 날씨·관측성·영속 연결을 끄고 합성 자료만 사용한다.

## 검증 대기

1. 접근 가능한 Python 환경에서 기존 41개와 P1 전체 pytest·린트 실행.
2. 기존 화면의 넓고 좁은 뷰포트, 키보드·초점·aria·reduced-motion·AI/근거 표시.
3. 실제 날씨 지역 처리·계정·실패·지연.
4. Bicep 컴파일, 비밀 참조·관리 ID, 실제 DB 재시작·승인·TTL.
5. 추적 데이터에 본문·메모·키·세션 ID가 없는지 확인.
6. 실제 농업 근거를 검토한 뒤 배포 URL에서 사용자 흐름 확인.

구현 파일·테스트·문서 작성은 완료다. 테스트 통과·실제 연동·배포 스모크는 완료가 아니다.
