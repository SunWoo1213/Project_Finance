# Project Finance 환경변수 권장값과 이유

Date: 2026-06-08

이 문서는 [ENVIRONMENT_VARIABLE_SETUP.md](ENVIRONMENT_VARIABLE_SETUP.md), [AGENTS.md](AGENTS.md), [backend/app/core/config.py](backend/app/core/config.py)에 흩어져 있는 환경변수 **권장값**과 **그 값을 권장하는 이유**를 한곳에 모은 참고 문서다. 설정 절차 자체는 [ENVIRONMENT_VARIABLE_SETUP.md](ENVIRONMENT_VARIABLE_SETUP.md)를 따른다.

원칙상 이 문서에는 변수 이름, placeholder, 권장값, 이유만 적는다. 실제 secret 값(API key, DB password, JWT secret, OAuth/webhook secret)은 적지 않는다.

## 0. 가장 중요한 한 가지 이유

이 프로젝트의 권장값 대부분은 **"처음 실행할 때 외부 API 비용·LLM 비용·실제 발송(알림/결제)이 일어나지 않게 막는다"**는 하나의 원칙에서 나온다. 그래서 background 작업 스위치(`ENABLE_*`)는 기본적으로 끄고, API·DB·인증부터 좁게 검증한 뒤 기능별로 하나씩 켜는 것을 권장한다.

값의 성격은 세 가지로 나뉜다.

- **직접 정하는 값**: 앱 이름, 환경 구분, 주소, scheduler 정책 등.
- **외부 dashboard에서 발급받는 값**: provider API key, OAuth client, webhook secret 등. 실제 쓰는 기능만 발급.
- **운영 스위치**: 켜는 순간 비용·부하·발송이 생기므로 단계적으로 활성화.

## 1. 시나리오별 스위치 권장값 (가장 자주 바뀌는 값)

| 변수 | 로컬 개발 | 첫 hosted smoke | 운영 | 이유 |
| --- | --- | --- | --- | --- |
| `ENVIRONMENT` | `development` | `staging` | `production` | 런타임 구분값. `production`으로 바꾼다고 자동 배포가 되는 건 아니며 CORS·DB·migration·scheduler 정책이 함께 맞아야 한다. |
| `ENABLE_MARKET_WARMUP` | `false`(초기) | `false` | 정책에 따라 | 시작 시 시장 cache warm-up이 외부 API를 대량 호출한다. 검증 전에는 끈다. |
| `ENABLE_SCHEDULER` | `false`(초기) | `false` | `true`(승인 후) | APScheduler가 가격·뉴스·알림·리포트 job을 주기 실행하는 운영 스위치. 단순 UI 토글이 아니라 외부 API를 반복 호출한다. |
| `ENABLE_AI_REPORT_GENERATION` | `false` | `false` | `true`(비용 승인 후) | LLM 리포트 생성 비용이 직접 발생한다. `false`면 scheduler가 켜져 있어도 리포트 생성 job과 서비스 진입부를 건너뛴다(저장 리포트 조회에는 영향 없음). |
| `ENABLE_LLM_REPORT_CRITICS` | `false` | `false` | `true`(비용 승인 후) | 추가 LLM critic agent는 리포트당 LLM 호출을 더 늘려 비용을 키운다. |
| `ENABLE_LLM_CHATBOT` | `false` | `false` | 정책에 따라 | 기본 rule-based 챗봇이 안전한 baseline. LLM 경로는 OpenAI 비용이 들고, 켜더라도 저장된 리포트만 읽어야 한다(fresh 리포트 생성 금지). |
| `ENABLE_NOTIFICATION_SCHEDULER` | `false` | `false` | `true`(정책 확정 후) | 실제 사용자에게 Telegram/이메일을 발송할 수 있다. 발송 정책 확정 전에는 끈다. |
| `ENABLE_BILLING_SCHEDULER` | `false` | `false` | `true`(계약 확정 후) | Toss 정기 결제 scheduler는 실제 돈을 청구할 수 있어 기본 비활성. |
| `ENABLE_STOOQ_FALLBACK` | `false` | `false` | `false`(권장) | Render에서 Stooq `ConnectTimeout('')`가 반복된 이력 때문에 기본 비활성. opt-in fallback으로만 쓴다. |
| `ENABLE_DB_SCHEMA_BOOTSTRAP` | `true` | `false` | `false` | 로컬에서는 startup 자동 schema 생성이 편하지만, 운영에서는 Alembic migration을 쓰고 startup 자동 생성을 끈다. |

> 가격·뉴스 scheduler만 먼저 검증하려면 `ENABLE_SCHEDULER=true` + `ENABLE_AI_REPORT_GENERATION=false` 조합을 쓴다. 이 조합에서는 리포트 생성 job과 startup 리포트 job이 등록되지 않는다.

## 2. 앱 메타데이터

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `PROJECT_NAME` | `Project Finance` | FastAPI 앱 이름. 기본 유지. 필수값(기본값 없음). |
| `API_V1_STR` | `/api/v1` | v1 API prefix 기본값. 현재 앱은 `/api/...` 라우트도 함께 사용한다. 필수값. |

## 3. 인증 (JWT · Google)

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `SECRET_KEY` | 새 랜덤 문자열(직접 생성) | JWT 서명용 backend-only secret. [config.py:85](backend/app/core/config.py#L85)의 기본값은 placeholder이므로 **반드시 교체**한다. 이미 노출된 값은 재사용하지 않는다. |
| `ALGORITHM` | `HS256` | backend 코드와 일치해야 한다. 바꾸지 않는다. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7일) | 로그인 유지 정책값. 기본 7일. 보안을 강화하려면 줄인다. |
| `GOOGLE_CLIENT_ID` | Google OAuth Web client ID | backend가 Google ID token audience를 검증하는 값. backend-only로 저장. |
| `VITE_GOOGLE_CLIENT_ID` | `GOOGLE_CLIENT_ID`와 **같은 값** | frontend Google 로그인 버튼 초기화용 public identifier. 같은 client ID를 쓰되 저장 위치만 다르다. Google client secret은 현재 흐름에 넣지 않는다. |

`SECRET_KEY` 생성(PowerShell):

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

## 4. Frontend 공개 주소

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | 로컬: `http://localhost:8000` / 배포: backend HTTPS origin | 브라우저가 호출할 backend origin. **public 값**이라 secret을 넣으면 안 된다. path(`/api`)는 붙이지 않는다. |

`VITE_`로 시작하는 값은 브라우저 번들에 노출되므로 API key·password·secret을 절대 넣지 않는다.

## 5. 데이터베이스

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `POSTGRES_USER` | 직접 지정(예: `finance_user`) | 로컬 Docker DB 계정. `docker-compose.yml`이 `.env`에서 읽으며 없으면 기동 실패(`:?`). |
| `POSTGRES_DB` | 직접 지정(예: `finance_db`) | 로컬 DB 이름. |
| `POSTGRES_PORT` | `5432` | 다른 PostgreSQL과 충돌하지 않으면 기본값 유지. |
| `POSTGRES_PASSWORD` | 새 랜덤 문자열 | 운영 DB 비밀번호와 재사용 금지. |
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<pw>@localhost:<port>/<db>` | async SQLAlchemy가 쓰는 URL. **반드시 async driver scheme**(`postgresql+asyncpg://`). sync `postgresql://`를 넣으면 설정 로드 시 정규화되긴 하나, 처음부터 async scheme으로 맞추는 것이 안전하다. URL 전체가 secret. |
| `DB_PREPARED_STATEMENT_CACHE_SIZE` | 비워둠 | Supabase pooler 등에서 prepared statement 오류가 날 때만 조정. 오류가 없으면 비운다. |
| `SQLALCHEMY_ECHO` | `false` | SQL 로그는 디버깅 시에만 켠다. |
| `DB_POOL_PRE_PING` | `true` | 끊긴 커넥션 자동 감지. 기본 유지 권장. |

`POSTGRES_*`를 바꿔도 이미 만들어진 `postgres_data` volume은 최초 값을 유지한다. `.env`만 바꾸면 접속이 안 맞을 수 있다(volume 재초기화는 데이터 손실 작업).

Hosted DB에서 `DATABASE_URL`을 비우면 backend가 `POSTGRES_URL_NON_POOLING` → `POSTGRES_URL` 순으로 fallback한다. 다만 운영에서는 명시적 `DATABASE_URL`을 두는 것을 권장한다.

## 6. CORS

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `LOCAL_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 로컬 Vite origin 기본값. 보통 유지. |
| `BACKEND_CORS_ORIGINS` | 배포 frontend origin(쉼표 구분) | origin은 scheme+host만, path는 넣지 않는다. credentialed 요청 앱이라 운영에서 wildcard 금지. |
| `BACKEND_CORS_ORIGIN_REGEX` | 비워둠(기본) | Vercel preview처럼 URL이 매번 바뀔 때만 사용. 운영은 정확한 origin 목록이 안전. |

## 7. 외부 provider API key (모두 backend-only)

권장값은 "실제 쓰는 기능만 발급, 나머지는 비움". 비어 있으면 앱은 뜨지만 해당 데이터의 품질·coverage가 제한된다.

| 변수 | 권장 발급 시점 | 이유 |
| --- | --- | --- |
| `OPENAI_API_KEY` | AI 리포트/챗봇 LLM을 실제 호출할 때 | LLM 비용 발생. 비용 검증 전에는 관련 스위치를 끈 상태로 둔다. |
| `ALPHA_VANTAGE_API_KEY` | 거시 데이터 품질 개선 시 | free key rate limit 확인 후 사용. ([macro_service.py](backend/app/services/macro_service.py)가 `os.getenv` → settings 순으로 읽음) |
| `FRED_API_KEY` | 거시 데이터 사용 시 | 앱별 별도 key 권장. |
| `ECOS_API_KEY` | 한국은행 거시 데이터 사용 시 | 한국은행 ECOS Open API 인증키. |
| `FMP_API_KEY` | 미국 지수/원자재/미국 주식 history 사용 시 | 미국 history의 1차 경로. 없으면 빈 history 또는 stale cache로 degrade. |
| `FINNHUB_API_KEY` | 뉴스/호가 사용 시 | free tier endpoint 제한 확인. |
| `COINGECKO_DEMO_API_KEY` | 암호화폐 시세/히스토리 사용 시 | CoinGecko Demo key. |
| `DATA_GO_KR_API_KEY` | KR 주식/지수 사용 시 | 공공데이터포털 금융위원회 serviceKey. |
| `STOOQ_API_KEY` | `ENABLE_STOOQ_FALLBACK=true`일 때만 | 기본 경로에서는 미사용(opt-in fallback). |

## 8. 시장 데이터 주기·타임아웃 (기본값 유지 권장)

이 값들은 provider quota 보호와 직렬화된 수집 큐가 한 사이클 안에 끝나도록 튜닝된 값이라, **기본값 유지를 권장**한다. 줄이면 외부 API 호출 빈도·부하가 늘어난다.

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `MARKET_PRICES_REFRESH_MINUTES` | `5` | 사용자 화면 시세 cache 갱신 간격. 최소 1로 강제. |
| `MARKET_NEWS_REFRESH_MINUTES` | `60` | 뉴스 cache 갱신 간격(1시간). |
| `MARKET_LATEST_CONTEXT_TTL_MINUTES` | `10` | 종목 상세 latest-context cache 유효시간. |
| `MARKET_PRICE_FETCH_TIMEOUT_SECONDS` | `55` | KR snapshot은 data.go.kr 2회 호출(~20s씩)이라 `2 * DATA_GO_KR_FETCH_TIMEOUT_SECONDS`보다 충분히 커야 한다. |
| `MARKET_NEWS_FETCH_TIMEOUT_SECONDS` | `20` | 뉴스 수집 per-asset timeout. 최소 5로 강제. |
| `DATA_GO_KR_FETCH_TIMEOUT_SECONDS` | `25` | data.go.kr 호출이 ~20s까지 튀어 여유 필요. |
| `DATA_GO_KR_MAX_CONCURRENCY` | `2` | data.go.kr가 부하 시 차단 페이지("허용되지 않는 요청")를 주므로 보수적으로 2. 최소 1 강제. |
| `FMP_FETCH_TIMEOUT_SECONDS` | `10` | FMP 단일 호출 timeout. 최소 5. |
| `FMP_DAILY_CALL_BUDGET` | `180` | FMP 무료 250 calls/day 초과 방지용 process-local 일일 budget. `0`이면 FMP 호출 skip. 재시작 시 counter 초기화. |
| `STOOQ_FETCH_TIMEOUT_SECONDS` | `12` | opt-in Stooq CSV timeout. 최소 5. |

## 9. AI 리포트 scheduler 정책

provider 발급값이 아니라 비용·운영 정책으로 정하는 값이다.

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `REPORT_SCHEDULER_COVERAGE` | `conservative` | 보수적 coverage로 비용·부하 최소화. |
| `REPORT_SCHEDULER_INTERVAL_HOURS` | `6` | 리포트 생성 주기. 짧을수록 LLM 비용 증가. |
| `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` | `60` | 리포트 잡 첫 발화까지 지연(초). interval 잡 `next_run_time`으로 쓰여 기동 직후 1회 발화시킨다(최초 발화가 +1주기로 밀리는 것 방지). sleep/재시작형 런타임 대비 짧게. 0/음수는 0으로 보정. |
| `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN` | `5` | 1회 실행당 최대 리포트 수 제한으로 비용 상한. |
| `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS` | `6` | 같은 자산을 너무 자주 생성하지 않도록. |
| `REPORT_SCHEDULER_TARGET_TICKERS` | `DGS10,XAU,BTC-USD,NVDA,005930.KS` | backend가 지원하는 ticker만 쉼표로 나열. |
| `REPORT_CRITIC_MODE` | `deterministic` | LLM 호출 없는 결정적 critic. 추가 LLM critic은 `ENABLE_LLM_REPORT_CRITICS`로 별도 승인 후. |
| `REPORT_MAX_REVISIONS` | `7` | 품질 게이트 실패 시 재작성 최대 횟수. 클수록 통과율↑이지만 실패 리포트당 LLM 호출↑로 비용 증가. |

> 목표 규칙: 사용자 화면·챗봇 요청은 **저장된 scheduled report만 읽는다**. 일반 요청이 fresh 리포트 생성을 트리거하지 않게 유지한다.

## 10. 챗봇 LLM

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `CHATBOT_LLM_MODEL` | `gpt-4o-mini` | 비용 대비 합리적 기본 모델. |
| `CHATBOT_HISTORY_MAX_TURNS` | `6` | 컨텍스트 turn 수 제한으로 토큰·비용 관리. |
| `CHATBOT_LLM_TIMEOUT_SECONDS` | `20` | 응답 지연 상한. |

## 11. 결제 (Toss / mock)

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `PAYMENT_PROVIDER` | 검증: `mock` / 실제: `toss` | provider 미확정 시 mock 흐름만 사용 가능. |
| `PAYMENT_MOCK_CHECKOUT_BASE_URL` | `http://localhost:5173/billing` | mock checkout redirect base. mock에서는 plan ID가 비어도 기본값 사용. |
| `TOSS_API_BASE_URL` | `https://api.tosspayments.com` | Toss Core API base. 기본 유지. |
| `TOSS_CLIENT_KEY` | test key부터 | Toss JS SDK에 전달되는 public client key. source에 하드코딩하지 않는다. |
| `TOSS_SECRET_KEY` | test key부터 | Toss Core API용 **backend-only** secret. `VITE_`·frontend·문서·로그 금지. |
| `TOSS_PLUS_AMOUNT_KRW` | `1000` | Plus 월 결제 금액(기본). 음수는 0으로 보정. |
| `TOSS_PRO_AMOUNT_KRW` | `3000` | Pro 월 결제 금액(기본). |
| `PAYMENT_WEBHOOK_SECRET` | provider 발급값 | webhook 서명 검증 secret. backend-only. test/live 분리. |
| `PAYMENT_PLUS_PLAN_ID` / `PAYMENT_PRO_PLAN_ID` | provider 발급값 | Stripe라면 Product ID가 아닌 Price ID. |
| `BILLING_RENEWAL_INTERVAL_MINUTES` | `60` | 정기 결제 점검 간격. 최소 1. |
| `BILLING_RETRY_LIMIT` | `3` | 결제 실패 재시도 횟수. 최소 0. |
| `BILLING_RETRY_BACKOFF_HOURS` | `24` | 재시도 backoff. 최소 1. |

> 결제는 실제 돈과 연결되므로 test mode와 live mode의 key·plan ID·webhook secret을 섞지 않는다.

## 12. 알림 (Telegram / Gmail)

| 변수 | 권장값 | 이유 |
| --- | --- | --- |
| `NOTIFICATION_EVALUATION_INTERVAL_MINUTES` | `10` | 가격 변동 평가 주기. |
| `NOTIFICATION_DELIVERY_INTERVAL_MINUTES` | `1` | 발송 큐 처리 주기. |
| `NOTIFICATION_DEFAULT_PRICE_THRESHOLD_PERCENT` | `3` | 기본 가격 변동 알림 임계치(%). |
| `NOTIFICATION_DEFAULT_COOLDOWN_MINUTES` | `180` | 같은 알림 재발송 대기 시간. |
| `TELEGRAM_BOT_TOKEN` | BotFather 발급값 | backend-only. |
| `TELEGRAM_WEBHOOK_SECRET` | 직접 만든 랜덤 문자열 | webhook 검증용. |
| `EMAIL_PROVIDER` | `gmail` | 현재 발송 구현은 Gmail API 단일 provider. **SMTP 미지원**이므로 `EMAIL_SMTP_*`는 설정하지 않는다. |
| `EMAIL_FROM_ADDRESS` | Gmail 발신 계정 | 발신 주소. |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | Google Cloud 발급값 | `gmail.send` scope. 모두 backend-only secret. |

## 13. 처음 실행용 최소 묶음 (요약)

로컬에서 앱이 뜨는지만 확인할 때 채울 최소 값:

```dotenv
PROJECT_NAME=Project Finance
API_V1_STR=/api/v1
ENVIRONMENT=development

POSTGRES_USER=<직접 지정>
POSTGRES_PASSWORD=<랜덤>
POSTGRES_DB=<직접 지정>
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://<user>:<pw>@localhost:5432/<db>

SECRET_KEY=<랜덤 생성>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

VITE_API_BASE_URL=http://localhost:8000
LOCAL_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

ENABLE_MARKET_WARMUP=false
ENABLE_SCHEDULER=false
ENABLE_AI_REPORT_GENERATION=false
ENABLE_LLM_REPORT_CRITICS=false
ENABLE_NOTIFICATION_SCHEDULER=false
```

이후 기능을 켤 때마다 해당 provider key를 발급해 추가하고, 스위치는 비용·발송 정책을 확정한 뒤 하나씩 `true`로 바꾼다.

## 14. 출처 문서

- [ENVIRONMENT_VARIABLE_SETUP.md](ENVIRONMENT_VARIABLE_SETUP.md) — 단계별 설정 절차
- [AGENTS.md](AGENTS.md) §3~14 — 운영 규칙과 경계
- [backend/app/core/config.py](backend/app/core/config.py) — settings 기본값과 validator(최소/최대 보정)

환경변수를 추가하거나 의미를 바꾸면 [AGENTS.md](AGENTS.md) §18에 따라 `.env.example`, `config.py`, 관련 feature 문서, 변경 기록과 함께 이 문서도 갱신한다.
