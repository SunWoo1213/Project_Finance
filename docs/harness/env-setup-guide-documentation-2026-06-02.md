# 환경변수 설정 절차 문서 추가 기록

Date: 2026-06-02

## Objective

루트 `.env_example`의 placeholder에 실제 환경변수 값을 채우기 위해 필요한 절차를 설명하는 루트 문서를 추가한다.

## Files Changed

- `.env_example`
- `ENVIRONMENT_VARIABLE_SETUP.md`
- `docs/harness/env-setup-guide-documentation-2026-06-02.md`

## Behavior Changes

- 애플리케이션 런타임 동작 변경 없음.
- 환경변수 설정 담당자가 `.env_example`을 `.env`와 필요 시 `frontend/.env`로 복사하고, DB, CORS, Google login, AI/provider key, scheduler, payment, notification 값을 어떤 순서로 채우고 검증할지 확인할 수 있는 문서를 추가했다.
- backend 실행 검증 명령은 PowerShell에서 `uvicorn` 실행 파일이 PATH에 없어도 동작하도록 `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload` 형식으로 안내한다.
- 설정 검증용 backend 실행은 외부 API와 LLM report scheduler가 시작되지 않도록 현재 PowerShell 세션에서 `ENABLE_MARKET_WARMUP=false`, `ENABLE_SCHEDULER=false`를 먼저 지정하도록 보강했다.
- 문서는 secret 값을 포함하지 않고 변수 이름, 용도, 공개 여부, 검증 절차만 기록한다.
- `.env_example` 상단에 `.env`로 옮겨 채워야 할 환경변수 이름을 주석 체크리스트로 먼저 나열했다. 이어지는 섹션별 설명과 예시 값은 그대로 유지해 중복 선언 없이 빠르게 변수 목록을 확인할 수 있게 했다.
- `ENVIRONMENT_VARIABLE_SETUP.md`에 `.env_example` 변수값을 얻기 위해 실제로 진행해야 하는 과정을 단계형으로 추가했다. 로컬 기본값, frontend/backend URL, Docker DB, hosted DB, JWT secret, Google OAuth, OpenAI, 시장 데이터 provider, 리포트 scheduler, 결제 provider, 알림 provider, 최종 검증 순서로 나누어 따라 할 수 있게 구성했다.
- 로컬 생성값, provider dashboard 발급값, frontend public 값, backend-only secret을 구분하고 OpenAI, Google OAuth, FRED, ECOS, Alpha Vantage, FMP, Finnhub, Telegram, payment webhook/plan, SMTP/Gmail 계열 변수의 확보 경로를 문서화했다.
- `docs/harness/features/deployment-runtime.md`에 환경변수 확보 절차 문서의 위치와 새 환경변수 추가 시 가이드 갱신 규칙을 연결했다.

## Verification Performed

- 문서 작성 전 `git status --short`로 기존 변경사항을 확인했다.
- `.env_example`, `ARCHITECTURE.md`, `PROJECT_STRUCTURE_ANALYSIS.md`, root `DEVELOPMENT_DIRECTION.md`, `docs/harness/feature-index.md`, `docs/harness/features/deployment-runtime.md`, `backend/app/core/config.py`, `frontend/src/utils/apiClient.js`를 참고했다.
- 외부 provider별 변수 확보 절차는 공식 문서 또는 공식 사이트 기준으로 확인했다. 확인 대상은 OpenAI API authentication, Google OAuth credentials, Vercel Vite/environment variables, Alpha Vantage, FRED, ECOS Open API, Financial Modeling Prep, Finnhub, Telegram BotFather, Stripe webhook/price 문서다.

## Commands Not Run

- `npm run build`: 문서 추가만 수행했으므로 frontend build는 실행하지 않았다.
- `pytest`: backend 동작 변경이 없으므로 테스트는 실행하지 않았다.
- backend/frontend dev server: 런타임 검증이 필요한 변경이 아니어서 실행하지 않았다.

## Follow-up Risks

- 실제 환경변수 값은 각 개발자 또는 배포 플랫폼에서 별도로 관리해야 한다.
- secret이 source, 로그, 채팅, 스크린샷에 노출되면 해당 값은 폐기하고 rotation해야 한다.
- 새 환경변수가 추가되면 `.env_example`, `backend/app/core/config.py`, 관련 feature document, 이 루트 가이드를 함께 갱신해야 한다.
