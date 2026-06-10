# Supabase RLS 미설정 보안 경고 조치 계획

Date: 2026-06-08 (경고 수신) / 2026-06-10 (문서 작성)

## Objective

Supabase가 발송한 보안 경고(`rls_disabled_in_public`, `sensitive_columns_exposed`)의 원인을 정리하고, 이 저장소의 실제 아키텍처에 맞는 안전한 조치 절차를 한국어로 남긴다. 이 문서는 실제 DB password, connection string, anon/service role key, JWT secret을 기록하지 않는다.

대상 Supabase project: `CapstoneProject1` (project ref는 운영 메모로만 관리, 본 문서에 전체 키/URL을 적지 않는다).

## 1. 경고가 의미하는 것

Supabase는 project 생성 시 **`public` 스키마의 모든 테이블을 자동으로 REST Data API(PostgREST)로 외부에 노출**한다. 이 자동 API는 project URL과 **anon key**만 있으면 외부에서 호출할 수 있고, 그 앞단에서 행(row) 단위 접근을 막는 유일한 장치가 **RLS(Row-Level Security)** 다.

| 경고 코드 | 의미 |
| --- | --- |
| `rls_disabled_in_public` | `public` 스키마 테이블에 RLS가 비활성 → 자동 REST API로 누구나 읽기/수정/삭제 가능한 상태 |
| `sensitive_columns_exposed` | 그 테이블 중 개인식별정보(PII)/민감 컬럼을 가진 테이블이 보호 없이 노출됨 |

즉 "DB 서버가 직접 뚫렸다"가 아니라, **Supabase 기본 공개 REST API + RLS 미설정** 조합 때문에 anon key를 아는 주체가 데이터에 접근할 수 있는 상태라는 경고다.

## 2. 이 프로젝트의 실제 위험도 (맥락)

현재 아키텍처에서는 위험이 즉시 악용되긴 어렵지만, 방어선이 한 겹뿐이라 Supabase가 Critical로 분류한다.

- 백엔드(FastAPI)는 `DATABASE_URL` 직결(asyncpg)로만 Postgres에 접속한다. 이 경로는 테이블 소유자/`postgres` 롤이라 **RLS의 영향을 받지 않고**, Supabase REST API도 거치지 않는다. → RLS를 켜도 백엔드 동작은 그대로다. ([config.py](backend/app/core/config.py) 참고)
- 프론트엔드는 Supabase client를 직접 쓰지 않는다. anon key를 브라우저 번들에 넣지 않는 것이 현재 운영 기준이다. ([VERCEL_SUPABASE_INTEGRATION_GUIDE.md](VERCEL_SUPABASE_INTEGRATION_GUIDE.md) 95번 줄, [supabase-console-tasks-2026-06-03.md](docs/harness/supabase-console-tasks-2026-06-03.md) 섹션 5)
- 따라서 anon key가 외부에 유출돼 있지 않다면 당장 악용 가능성은 낮다. 다만 anon key는 설계상 공개용 키라서 로그·과거 커밋·실수로 프론트 번들에 새는 순간 전체 데이터가 노출된다. 지금은 보안이 "anon key가 새지 않는다"는 가정에만 의존한다.

## 3. 노출 대상 테이블 인벤토리

[models.py](backend/app/models.py) 기준 `public` 스키마 테이블과 민감도.

| 테이블 | 민감 컬럼 / 비고 | PII 여부 |
| --- | --- | --- |
| `users` | `email`, `google_sub`, `nickname` | PII (높음) |
| `notification_channel_connections` | `destination`(이메일/텔레그램 대상), `verification_code` | PII (높음) |
| `subscriptions` | `provider_customer_id`, `provider_subscription_id`, `provider_plan_id` | 민감 (결제) |
| `billing_events` | `payload_hash`, `provider_event_id`, `normalized_summary` | 민감 (결제) |
| `notification_preferences` | 사용자 알림 설정 | PII (보통) |
| `notification_rules` | 사용자별 알림 규칙 | PII (보통) |
| `notification_events` | `title`, `body`(알림 내용), `dedupe_key` | PII (보통) |
| `user_favorite_assets` | 사용자별 관심 자산 | PII (보통) |
| `comments` | 사용자 작성 글, `user_id` | PII (보통) |
| `comment_likes`, `comment_reports` | 사용자 행동 데이터 | PII (낮음) |
| `assets`, `ai_reports`, `asset_notification_snapshots` | 공개 시장 메타/생성 리포트 | 비PII |
| `alembic_version` | Alembic이 관리하는 마이그레이션 버전 테이블 | 비PII (그래도 노출 불필요) |

참고: 이 앱에는 비밀번호 해시 컬럼이 없다(Google OAuth + 백엔드 JWT). `sensitive_columns_exposed` 경고는 비밀번호가 아니라 위 PII 컬럼(특히 `users.email`, `notification_channel_connections.destination`)을 가리킨다.

## 4. 권장 조치

이 앱은 Supabase 자동 REST API를 쓰지 않으므로, 다음 두 가지를 **함께** 적용하는 것을 권장한다.

### 4.1 (권장 1) 모든 public 테이블에 RLS 활성화

RLS를 켜고 policy를 만들지 않으면 anon/REST 경로로는 전부 거부되고, 백엔드 직결 연결(`postgres` 롤)은 영향이 없다. Supabase **SQL Editor**에서 실행한다.

```sql
-- public 스키마의 일반 테이블 전체에 RLS 활성화 (policy 미생성 = REST 경로 전면 차단)
do $$
declare
  r record;
begin
  for r in
    select tablename
    from pg_tables
    where schemaname = 'public'
  loop
    execute format('alter table public.%I enable row level security;', r.tablename);
  end loop;
end $$;
```

명시적으로 테이블을 나열하고 싶으면 아래를 쓴다.

```sql
alter table public.users enable row level security;
alter table public.assets enable row level security;
alter table public.ai_reports enable row level security;
alter table public.comments enable row level security;
alter table public.comment_likes enable row level security;
alter table public.comment_reports enable row level security;
alter table public.subscriptions enable row level security;
alter table public.billing_events enable row level security;
alter table public.user_favorite_assets enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.notification_channel_connections enable row level security;
alter table public.notification_rules enable row level security;
alter table public.asset_notification_snapshots enable row level security;
alter table public.notification_events enable row level security;
alter table public.alembic_version enable row level security;
```

주의:
- policy를 추가하지 않는다. 이 앱은 anon/REST 접근이 필요 없으므로 "RLS on + policy 없음 = 외부 차단"이 목표다.
- 백엔드는 `postgres`(테이블 소유자) 롤로 직결하므로 RLS를 우회한다. 따라서 로그인/댓글/알림 등 기존 API 동작은 바뀌지 않는다.
- 나중에 Supabase client를 브라우저에서 직접 쓰는 기능을 도입하면 그때 테이블별 RLS policy를 별도 설계·문서화한다.

### 4.2 (권장 2) public 스키마의 Data API 노출 제거

근본 차단책. 이 앱은 REST API 자체가 필요 없다. Supabase 대시보드에서:

- `Project Settings` → `API` → `Exposed schemas`에서 `public`을 제거하거나,
- Data API 자체를 비활성화한다.

이렇게 하면 PostgREST 경로로 `public` 테이블에 접근하는 길이 막힌다. RLS 활성화(4.1)와 함께 적용하면 방어가 이중화된다.

### 4.3 (권장 3) anon key 노출 이력 점검 및 로테이션

- 과거에 anon key가 프론트 번들/커밋/로그/스크린샷/채팅에 노출된 적 있는지 확인한다.
- 노출 정황이 있으면 Supabase 대시보드에서 API key를 로테이션한다.
- service role key/DB password는 노출 시 즉시 rotate한다([supabase-console-tasks-2026-06-03.md](docs/harness/supabase-console-tasks-2026-06-03.md) 섹션 8 기준).

## 5. 검증 절차

조치 후 다음을 순서대로 확인한다.

1. Supabase SQL Editor에서 RLS 적용 상태 확인(민감 값 미노출):
   ```sql
   select tablename, rowsecurity
   from pg_tables
   where schemaname = 'public'
   order by tablename;
   ```
   모든 행의 `rowsecurity`가 `true`인지 본다.
2. Supabase 대시보드 보안 경고(Security Advisor)에서 `rls_disabled_in_public`, `sensitive_columns_exposed`가 해소됐는지 확인한다.
3. 백엔드 직결 동작 회귀 확인:
   - `/health`, `/db-check`가 정상 응답하는지(자격증명 미노출).
   - 로그인, 댓글 작성/조회, 관심자산, 알림 설정 등 DB를 쓰는 주요 API가 정상 동작하는지 스모크 확인.
4. (Data API를 끈 경우) `https://<project>.supabase.co/rest/v1/users` 같은 호출이 더 이상 데이터를 반환하지 않는지 확인한다.

## 6. 안전 규칙 / 비실행 사항

- 이 문서 작성 시점에는 Supabase 콘솔/대시보드에 접속하지 않았고, SQL을 실행하지 않았다. 위 SQL은 운영자가 SQL Editor에서 실행할 절차다.
- `DATABASE_URL`, password, anon/service role key 등 secret은 본 문서에 기록하지 않았다.
- 운영 DB에 `alter table`을 적용하기 전 backup/PITR 상태를 확인하고, staging이 있으면 staging에서 먼저 검증한다(AGENTS.md 섹션 9 위험 변경 프로토콜).
- RLS는 비파괴적 변경이지만, 혹시 향후 anon key 기반 기능이 추가돼 있었다면 차단될 수 있으니 현재 anon key 사용처가 없다는 전제를 다시 확인한다(현재 코드 기준 사용처 없음).

## 7. Follow-up Risks

- Supabase 대시보드 메뉴명/위치는 변경될 수 있다. 실제 작업 전 공식 문서의 현재 표시명을 확인한다.
- 향후 Supabase Auth나 브라우저 Supabase client를 도입하면 "RLS on + policy 없음" 전제가 깨지므로, 그때는 `auth.uid()` 기반 등 테이블별 policy를 새로 설계·문서화해야 한다.
- anon key가 과거 어딘가 노출됐다면 RLS/Data API 차단과 별개로 로테이션이 필요하다.

## 공식 참고 자료

- Supabase RLS: `https://supabase.com/docs/guides/database/postgres/row-level-security`
- Supabase secure data: `https://supabase.com/docs/guides/database/secure-data`
- Supabase Data API / exposed schemas: `https://supabase.com/docs/guides/api`
- 연관 문서: [supabase-console-tasks-2026-06-03.md](docs/harness/supabase-console-tasks-2026-06-03.md) 섹션 5, [VERCEL_SUPABASE_INTEGRATION_GUIDE.md](VERCEL_SUPABASE_INTEGRATION_GUIDE.md)
