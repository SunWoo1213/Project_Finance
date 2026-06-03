# Render DATABASE_URL 따옴표/공백 정규화 및 진단 메시지 보강

Date: 2026-06-03

## 배경 (관측된 장애)

Render 백엔드 배포가 기동 단계에서 다음으로 실패했다.

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, DATABASE_URL must use an async SQLAlchemy driver scheme.
  Allowed schemes after normalization: postgresql+asyncpg, sqlite+aiosqlite.
```

빌드는 성공했고, 실패 지점은 `app.main` import 시 `Settings()` 생성([config.py:195](../../backend/app/core/config.py#L195)) 단계다. 즉 코드 버그가 아니라 **Render Environment에 설정된 `DATABASE_URL` 값**이 정규화 후에도 허용 스킴(`postgresql+asyncpg`, `sqlite+aiosqlite`)이 아니었다는 뜻이다.

`normalize_database_url`은 이미 `postgres://`·`postgresql://`를 `postgresql+asyncpg://`로 변환한다([config.py:13-37](../../backend/app/core/config.py#L13-L37)). 따라서 변환 후에도 실패하려면 값이 그 접두어로 **시작하지 않아야** 한다. 자주 발생하는 원인:

1. 대시보드에 값을 **따옴표로 감싸서**(`"postgresql://..."`) 입력 → 따옴표가 리터럴로 저장되어 스킴이 비게 됨.
2. 앞뒤 **공백/개행** 혼입.
3. 플레이스홀더(`<staging Supabase URL>`)를 그대로 둠.
4. Supabase **API URL**(`https://<ref>.supabase.co`)을 DB 연결 문자열 대신 붙여넣음.

기존 에러 메시지는 실제 감지된 스킴을 출력하지 않아 위 4가지 중 무엇인지 진단하기 어려웠다.

## 목적

- 흔한 따옴표/공백 입력 실수를 코드 레벨에서 자가 교정한다.
- 실패 시 감지된 스킴을 에러에 노출해 진단을 쉽게 한다(자격증명은 노출하지 않음 — 스킴만).

## 변경 파일

- [backend/app/core/config.py](../../backend/app/core/config.py)
  - `normalize_database_url`: 입력값을 `strip()`하고, 앞뒤가 같은 한 쌍의 따옴표(`'`/`"`)로 감싸진 경우 제거한 뒤 기존 스킴 변환을 수행([config.py:13-43](../../backend/app/core/config.py#L13-L43)).
  - `resolve_database_url`: 스킴 거부 시 에러 메시지에 `Detected scheme: <scheme>` 및 교정 안내(따옴표 제거, https:// API URL이 아닌 DB 연결 문자열 사용)를 추가([config.py:146-160](../../backend/app/core/config.py#L146-L160)).
- [backend/tests/test_database_config.py](../../backend/tests/test_database_config.py)
  - `test_database_url_strips_surrounding_quotes_and_whitespace`: 따옴표+공백으로 감싼 값이 정상 정규화되는지 검증.
  - `test_database_url_error_reports_detected_scheme`: 잘못된 스킴일 때 에러에 감지 스킴이 포함되는지 검증.

## 동작 변화

- `  "postgresql://user:pw@host:5432/db"  ` 형태 입력도 `postgresql+asyncpg://user:pw@host:5432/db`로 정규화된다.
- 허용되지 않은 스킴(예: `mysql://`, API URL의 `https://`, 빈 스킴)일 때 에러가 실제 감지 스킴과 교정 방법을 함께 보고한다.
- 기존 정상 동작(이미 async 스킴, sslmode→ssl 변환, fallback env, 포트 검증)은 그대로 유지된다.

## 검증

- `backend/.venv/Scripts/python.exe -m pytest tests/test_database_config.py -q` → **13 passed** (기존 11 + 신규 2).
- 미실행: 전체 `pytest`(이 변경은 config 검증 범위에 한정), 프론트엔드 lint/build(무관), 실제 Render 재배포(사용자 환경 권한 필요).

## 운영자 후속 조치 (Render)

코드 변경이 따옴표/공백은 자가 교정하지만, **값 자체가 DB 연결 문자열이 아니면** 여전히 실패한다. Render Environment에서 `DATABASE_URL`이 다음을 만족하는지 확인한다.

- `postgresql://` 또는 `postgres://`로 시작(또는 이미 `postgresql+asyncpg://`).
- Supabase **API URL**(`https://<ref>.supabase.co`)이 아니라 **DB 연결 문자열**(Session/Transaction pooler 또는 Direct).
- 비밀번호 특수문자는 URL 인코딩 또는 영숫자 재설정(참고: [supabase-database-setup-guide-2026-06-03.md](supabase-database-setup-guide-2026-06-03.md) 4·7절).

> 별도 잠재 이슈(이번 변경 범위 아님): 배포 로그에 `main.py:236/247 SyntaxWarning: 'break' in a 'finally' block` 경고가 있다. 현재 치명적이지 않으나 Python의 향후 버전에서 오류가 될 수 있어 추후 정리 권장.

## 관련 문서

- [docs/harness/features/deployment-runtime.md](features/deployment-runtime.md)
- [docs/harness/supabase-asyncpg-url-normalization-2026-06-03.md](supabase-asyncpg-url-normalization-2026-06-03.md)
- [docs/harness/render-backend-deployment-guide-2026-06-03.md](render-backend-deployment-guide-2026-06-03.md)
- [docs/harness/supabase-database-setup-guide-2026-06-03.md](supabase-database-setup-guide-2026-06-03.md)

## References Checked

- 코드: `backend/app/core/config.py`, `backend/tests/test_database_config.py`
- 문서: `docs/harness/feature-index.md`, `docs/harness/features/deployment-runtime.md`, `docs/harness/supabase-database-setup-guide-2026-06-03.md`
- 외부: Render 배포 로그(2026-06-03 6:41-6:45 GMT+9)
