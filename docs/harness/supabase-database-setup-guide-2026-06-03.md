# Supabase 데이터베이스 구축 가이드 (처음부터)

Date: 2026-06-03

## Objective

`Project_Finance` 백엔드가 사용할 PostgreSQL 데이터베이스를 **Supabase로 처음부터 구축**하는 절차를 정리한다. 프로젝트 생성 → 비밀번호 설정 → 연결 문자열 확보 → 로컬에서 마이그레이션 → 연결 확인까지 다룬다. 이 문서는 가이드이며 코드를 변경하지 않는다. 실제 작업은 사용자가 Supabase 대시보드와 로컬 셸에서 수행한다.

대상 독자: DB를 아직 만들지 않은 상태에서 시작하는 사용자. 환경은 Windows + PowerShell.

함께 참고:
- `docs/harness/render-backend-deployment-guide-2026-06-03.md` (배포 단계에서의 DB 사용)
- `docs/harness/features/deployment-runtime.md`
- `ENVIRONMENT_VARIABLE_SETUP.md` (환경변수 획득 가이드)

## 0. 가장 먼저 — 헷갈리기 쉬운 두 값

Supabase에는 비슷해 보이지만 **완전히 다른** 두 값이 있다. 이걸 섞으면 연결이 안 된다.

| 값 | 예시 | 용도 | 이 프로젝트에서 |
|---|---|---|---|
| 프로젝트 API URL | `https://<ref>.supabase.co` | REST/Auth API 호출용 | **DB 연결에 쓰지 않음** |
| **DB 연결 문자열** | `postgresql://postgres:비번@호스트:5432/postgres` | PostgreSQL 직접 연결 | ← `DATABASE_URL`에 넣는 값 |

백엔드([config.py](../../backend/app/core/config.py))와 Alembic이 필요한 것은 **DB 연결 문자열**이다. `https://...supabase.co`를 비밀번호나 호스트 자리에 넣으면 안 된다.

## 1. (선택) 로컬 Docker vs Supabase

- **로컬 개발만** 하려면 Supabase 없이 `docker-compose.yml`의 PostgreSQL로도 된다(`docker compose up -d db`). 이때 `DATABASE_URL`은 로컬 DB를 가리킨다.
- **배포(Render 등)까지** 갈 거라면 클라우드 DB가 필요하므로 **Supabase**를 구축한다. 이 문서는 Supabase 기준이다.

두 경우 모두 백엔드는 `DATABASE_URL` 하나로 연결되며, PostgreSQL URL은 `postgresql+asyncpg://`로 자동 정규화된다([config.py:13-37](../../backend/app/core/config.py#L13-L37)).

## 2. Supabase 프로젝트 생성

1. https://supabase.com 가입/로그인.
2. **New project** 생성.
   - Organization 선택(없으면 생성).
   - **Project name** 입력.
   - **Database Password**: 여기서 정하는 값이 곧 DB 비밀번호다. **영문+숫자 위주로, 특수문자(`@ : / ? # [ ] & %`)는 피한다.** (URL 인코딩 문제를 원천 차단)
   - **Region**: 주 사용자/백엔드와 가까운 곳(예: 한국이면 Northeast Asia(Seoul/Tokyo) 계열).
3. 생성 완료까지 1~2분 대기.

> 비밀번호를 잊었거나 특수문자로 만들어 문제가 생기면: **Project Settings → Database → Reset database password**에서 영숫자로 재설정한다.

## 3. DB 연결 문자열 가져오기 (Connect)

1. 대시보드 상단 **Connect** 버튼 클릭.
2. **Connection string → URI** 선택. 탭이 여러 개 보인다:

| 탭 | 호스트 형태 | 포트 | 특징 | 추천 용도 |
|---|---|---|---|---|
| Direct connection | `db.<ref>.supabase.co` | 5432 | IPv6 필요할 수 있음 | IPv6 가능한 서버 |
| Session pooler | `...pooler.supabase.com` | 5432 | IPv4 OK, 연결 유지형 | **로컬 마이그레이션/Windows** |
| Transaction pooler | `...pooler.supabase.com` | 6543 | IPv4 OK, 요청 단위 | 서버리스/단발성 |

3. 로컬 Windows에서 마이그레이션할 때는 **Session pooler** 가 가장 무난하다(IPv4 환경에서 잘 됨).
4. 표시된 URI를 복사하고, `[YOUR-PASSWORD]` 부분만 2단계의 실제 DB 비밀번호로 바꾼다.
   - Session pooler 예시 형태: `postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres`
   - Direct 예시 형태: `postgresql://postgres:[YOUR-PASSWORD]@db.<ref>.supabase.co:5432/postgres`

## 4. 로컬에 DATABASE_URL 설정

마이그레이션을 로컬에서 실행하려면 `DATABASE_URL`을 알려줘야 한다. 두 방법 중 하나.

### 방법 A — 현재 PowerShell 세션에만 설정 (가장 안전, 커밋 위험 없음)

```powershell
cd backend
# 작은따옴표 사용! 비밀번호의 특수문자/$ 보호
$env:DATABASE_URL = 'postgresql://postgres.<ref>:실제비번@aws-0-<region>.pooler.supabase.com:5432/postgres'

# 호스트 부분만 확인 (비밀번호 노출 없음) - 끝에 숫자 포트가 보여야 정상
$env:DATABASE_URL.Substring($env:DATABASE_URL.LastIndexOf('@'))
```

- 창을 닫으면 사라진다. `.env`나 커밋에 들어가지 않아 안전하다.

### 방법 B — 루트 `.env`에 기록 (재사용 편함, 단 커밋 금지)

- 백엔드 설정은 저장소 루트의 `.env`를 읽는다([config.py:7](../../backend/app/core/config.py#L7)).
- `.env`에 `DATABASE_URL=...`을 적되, **`.env`는 절대 커밋하지 않는다**(이미 `.claude/settings.json`에서 읽기 차단됨).
- 값에 따옴표를 붙이지 않는 형식이 일반적이다: `DATABASE_URL=postgresql://postgres.<ref>:실제비번@...:5432/postgres`

> 참고: `DATABASE_URL`을 명시하지 않고 Vercel/Supabase가 주입하는 `POSTGRES_URL_NON_POOLING` 또는 `POSTGRES_URL`만 있을 때는 백엔드가 그 순서로 fallback한다([config.py:119-138](../../backend/app/core/config.py#L119-L138)). 로컬 수동 설정에서는 `DATABASE_URL`을 직접 쓰는 게 명확하다.

### 특수문자가 든 비밀번호라면 (방법 A에서 인코딩)

```powershell
Add-Type -AssemblyName System.Web
$pw = Read-Host 'DB password' -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw))
$enc = [System.Web.HttpUtility]::UrlEncode($plain)
$env:DATABASE_URL = "postgresql://postgres.<ref>:$enc@aws-0-<region>.pooler.supabase.com:5432/postgres"
$env:DATABASE_URL.Substring($env:DATABASE_URL.LastIndexOf('@'))
```

가장 간단한 길은 **비밀번호를 영숫자로 재설정**(2단계)해서 인코딩 자체를 피하는 것이다.

## 5. 스키마 마이그레이션 실행

백엔드는 프로덕션에서 스키마를 자동 생성하지 않으므로([main.py:132-152](../../backend/app/main.py#L132-L152), `ENABLE_DB_SCHEMA_BOOTSTRAP=false`), **Alembic로 테이블을 만든다.**

```powershell
cd backend
# (가상환경 활성화 상태에서)
python -m alembic upgrade head
```

- baseline migration: `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`
- Alembic도 같은 `settings.DATABASE_URL`을 사용한다([alembic/env.py](../../backend/alembic/env.py)).

### Transaction pooler(포트 6543)를 쓸 때만

asyncpg의 prepared statement가 pgbouncer transaction 모드와 충돌할 수 있다. 이 경우에만:

```powershell
$env:DB_PREPARED_STATEMENT_CACHE_SIZE = '0'
```

Session pooler(5432)나 Direct에서는 보통 불필요하다([config.py:158-179](../../backend/app/core/config.py#L158-L179)).

## 6. 연결·테이블 확인

### 테이블이 생성됐는지 (Supabase 대시보드)

- **Table Editor** 또는 **Database → Tables**에서 다음이 보이면 성공: `users`, `assets`, `ai_reports`, `comments`, `subscriptions`, `billing_events`, `user_favorite_assets`, `notification_*` 등([main.py:45-60](../../backend/app/main.py#L45-L60)에 필수 목록).

### 백엔드로 확인

```powershell
cd backend
uvicorn app.main:app --reload
```

- 브라우저/`curl`로 `GET http://localhost:8000/health` → `status: ok`
- `GET http://localhost:8000/db-check` → `db_connected` 이면 연결 성공. 실패 시 503 + sanitized 진단(source/scheme/host/port만, 비밀번호 비노출 [main.py:315-345](../../backend/app/main.py#L315-L345)).

## 7. 자주 막히는 지점

- **`DATABASE_URL must use an async ... scheme`**: URL이 `postgresql://`/`postgres://`로 시작하지 않음. 플레이스홀더(`<staging Supabase URL>`)를 그대로 넣었거나 잘못된 값.
- **`DATABASE_URL contains an invalid port`**: 비밀번호 특수문자가 파싱을 깨뜨림, 또는 비밀번호 자리에 API URL(`https://...`)을 넣음. → 4단계 인코딩 또는 비밀번호 재설정.
- **연결 타임아웃**: Direct(IPv6) 호스트를 IPv4 환경에서 사용. → Session pooler로 변경.
- **`password authentication failed`**: DB 비밀번호 불일치. → Reset database password 후 URL 갱신.
- **마이그레이션은 됐는데 `/db-check` 실패**: pooler 모드/포트 확인, `DB_PREPARED_STATEMENT_CACHE_SIZE` 검토.

## 8. 보안 주의 (반드시)

- DB 비밀번호·연결 문자열을 채팅·로그·스크린샷·커밋에 넣지 않는다. 노출되면 즉시 Reset database password로 rotate.
- `.env`는 커밋하지 않는다.
- 프로젝트 ref(`<ref>`, subdomain)는 공개값이지만 비밀번호는 시크릿이다.
- 배포 시 실제 값은 Render Environment 등 호스트 secret에만 둔다(로컬 `.env` 복사 금지).

## 검증 계획 (AGENTS.md 섹션 6)

- `git status --short`
- 로컬: `python -m alembic upgrade head` (Supabase 대상)
- 로컬: `uvicorn app.main:app --reload` 후 `/health`, `/db-check`
- 코드 변경은 없으므로 별도 `pytest`는 생략(사유 기록)

## 갱신할 문서

DB 구축은 코드 변경이 아니라 환경 구성이므로 기본적으로 문서 갱신은 가벼우나, 실제 배포로 이어지면:

- `docs/harness/features/deployment-runtime.md`의 DB 연결/Connection mode 서술에 실제 채택한 모드(Session/Transaction/Direct)를 반영.
- `docs/harness/feature-index.md` Deployment/runtime plans 목록에 이 가이드 링크 추가.
- 최종 채택한 connection mode와 `DB_PREPARED_STATEMENT_CACHE_SIZE` 결정은 별도 구현/검증 기록으로 남긴다.

## References Checked

- 코드: `backend/app/core/config.py`, `backend/app/db/session.py`, `backend/app/main.py`, `backend/alembic/env.py`, `backend/alembic/versions/20260601_0001_add_subscription_billing_tables.py`
- 문서: `docs/harness/render-backend-deployment-guide-2026-06-03.md`, `docs/harness/features/deployment-runtime.md`, `ENVIRONMENT_VARIABLE_SETUP.md`
- 외부(배포 직전 현재 화면 기준 재확인): Supabase 프로젝트 생성, Connect 화면의 connection string 탭(Direct/Session/Transaction), Reset database password
