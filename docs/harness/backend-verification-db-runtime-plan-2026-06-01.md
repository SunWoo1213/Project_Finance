# 백엔드 검증 DB 런타임 해결 계획

작성일: 2026-06-01

## 목표

FastAPI 백엔드는 정상적으로 시작되지만, 설정된 PostgreSQL 엔드포인트에서 연결이 거부되어 데이터베이스 초기화가 건너뛰어지는 검증 경고를 해결한다.

## 읽은 검증 보고서

확인한 파일:

- `.codex-runtime/backend_verify.out.log`
- `.codex-runtime/backend_verify.err.log`

관찰된 결과:

- FastAPI 프로세스가 시작되었고 애플리케이션 startup 단계가 완료되었다.
- `GET /health`는 `200 OK`를 반환했다.
- lifespan 단계의 데이터베이스 초기화는 Windows 연결 거부 오류로 스킵되었다.
- market warm-up과 scheduler도 스킵되었다. 해당 런타임 플래그를 꺼 둔 가벼운 검증 실행이라면 이 부분은 예상 가능한 결과다.

## 진단

이 문제는 health endpoint 실패가 아니다. 백엔드는 기동되지만, 검증 실행 시점에 lifespan 데이터베이스 초기화에 사용할 수 있는 PostgreSQL 서비스가 연결 가능한 상태가 아니었다.

가능성이 높은 원인은 다음과 같다.

- Docker PostgreSQL 서비스가 실행 중이 아니었다.
- 설정된 `DATABASE_URL`이 PostgreSQL이 연결을 받지 않는 host 또는 port를 가리켰다.
- 검증 명령이 warm-up과 scheduler는 의도적으로 비활성화했지만, 데이터베이스 준비 상태를 먼저 확인하지 않았다.

## 해결 계획

1. 현재 작업트리 상태를 보존한다.
   - 수정 전 `git status --short`를 실행한다.
   - 관련 없는 사용자 변경사항은 수정하지 않는다.

2. 로컬 데이터베이스 런타임을 시작한다.
   - 저장소 루트에서 `docker compose up -d db`를 실행한다.
   - `docker compose ps db`로 데이터베이스 컨테이너가 실행 중인지 확인한다.

3. 애플리케이션 smoke 검증 전에 백엔드 DB 연결을 검증한다.
   - `backend/`에서 의도한 검증 데이터베이스를 대상으로 Alembic migration smoke를 실행한다:
     `python -c "from alembic.config import main; main(argv=['upgrade','head'])"`
   - 실패하면 연결 메타데이터와 예외 유형만 확인한다. secret이나 원본 환경 변수 값은 출력하지 않는다.

4. 비용이 큰 런타임 작업을 비활성화한 상태로 백엔드 smoke를 다시 실행한다.
   - 검증용으로 market warm-up과 scheduler를 비활성화한 상태에서 백엔드를 시작한다.
   - `GET /health`와 `GET /db-check`를 호출한다.
   - 기대 결과:
     - `/health`는 `{"status":"ok", ...}`를 반환한다.
     - `/db-check`는 `{"status":"db_connected"}`를 반환한다.
     - lifespan 로그에 `database initialization completed`가 기록된다.

5. 최근 변경된 billing 영역의 집중 백엔드 회귀 테스트를 실행한다.
   - `backend/`에서 다음을 실행한다:
     `python -m pytest tests/test_subscription_service.py tests/test_subscription_api.py tests/test_report_access_api.py tests/test_chat_api.py tests/test_payment_service.py tests/test_billing_webhook_api.py`
   - 기대 결과: 모든 테스트가 통과한다.

6. 검증 증거를 갱신한다.
   - 새 백엔드 smoke 출력은 `.codex-runtime/` 또는 기존 검증 채널에 저장한다.
   - DB 초기화 완료 여부, `/db-check` 통과 여부, 실행한 테스트 목록을 기록한다.

## 완료 기준

- DB가 활성화된 검증에서 백엔드 startup 로그에 더 이상 `database initialization skipped`가 나오지 않는다.
- `/health`는 계속 `200 OK`를 반환한다.
- `/db-check`가 데이터베이스 연결을 확인한다.
- billing/subscription 집중 테스트가 통과한다.
- 로그나 문서에 secret, 원본 DB 자격 증명, JWT secret, API key, webhook secret을 복사하지 않는다.

## 후속 위험

- `docker-compose.yml`에는 로컬 데이터베이스 설정이 포함되어 있으므로, 검증 보고서에는 credential 값을 복사하지 않아야 한다.
- lifespan은 로컬 bootstrap을 위해 아직 `Base.metadata.create_all`을 사용한다. production-like 변경은 계속 Alembic revision으로 표현해야 한다.
- PostgreSQL이 실행 중인데도 연결이 계속 거부된다면, 다음 조사는 credential을 노출하지 않고 설정된 DB host/port와 Docker published port를 비교하는 방향으로 진행한다.
