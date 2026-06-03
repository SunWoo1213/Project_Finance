# 시장 데이터 갱신 주기 환경변수 분리 (2026-06-03)

## 목적

리포트를 제외한, 사용자에게 노출되는 일반 시장 데이터의 갱신 주기를 코드 하드코딩에서 환경변수로 분리한다. 운영자가 코드 수정 없이 `.env`(또는 배포 환경변수)만으로 원하는 시간 간격마다 갱신되도록 한다.

대상 주기 세 가지는 모두 **분 단위**로 통일했다.

| 데이터 | 환경변수 | 기본값(분) | 기존 동작 |
| --- | --- | --- | --- |
| 시세(prices) cache 갱신 간격 | `MARKET_PRICES_REFRESH_MINUTES` | `5` | scheduler `minutes=5` 하드코딩 |
| 뉴스(news) cache 갱신 간격 | `MARKET_NEWS_REFRESH_MINUTES` | `60` | scheduler `hours=1` 하드코딩 |
| 종목 latest-context cache TTL | `MARKET_LATEST_CONTEXT_TTL_MINUTES` | `10` | `LATEST_CONTEXT_TTL_SECONDS = 10 * 60` 상수 |

기본값은 기존 동작과 동일하므로, 환경변수를 지정하지 않으면 행동 변화가 없다.

## 변경 파일

- `backend/app/core/config.py`
  - `Settings`에 `MARKET_PRICES_REFRESH_MINUTES`, `MARKET_NEWS_REFRESH_MINUTES`, `MARKET_LATEST_CONTEXT_TTL_MINUTES` 추가(기본 5/60/10).
  - `enforce_minimum_minutes` field validator 추가: 세 값이 0 또는 음수면 `1`로 보정한다. APScheduler interval job과 freshness 윈도우가 0으로 깨지는 것을 방지한다.
- `backend/app/main.py`
  - scheduler 가격 job `minutes=settings.MARKET_PRICES_REFRESH_MINUTES`로 변경.
  - scheduler 뉴스 job `hours=1` → `minutes=settings.MARKET_NEWS_REFRESH_MINUTES`로 변경.
  - 시작 로그 문자열을 고정값 `prices:5m, news:1h` → 실제 설정값 반영으로 변경.
- `backend/app/services/market_service.py`
  - `from ..core.config import settings` import 추가.
  - 모듈 상수 `LATEST_CONTEXT_TTL_SECONDS = 10 * 60` 제거, 호출 시점에 설정을 읽는 `_latest_context_ttl_seconds()` 함수로 대체.
  - `_is_latest_context_fresh()`의 freshness 비교와 payload `ttl_seconds`가 새 함수를 사용하도록 변경.
- `ENVIRONMENT_VARIABLE_SETUP.md`
  - background 작업 섹션에 세 환경변수 설명과 분 단위/최소값 보정/호출 빈도 비용 영향을 추가.
- `.env.example` (신규, 기존 오타 파일명 `.env. example`을 정상 이름으로 교체)
  - 빠른 변수 목록과 신규 "Market data refresh cadence" 섹션에 `MARKET_PRICES_REFRESH_MINUTES=5`, `MARKET_NEWS_REFRESH_MINUTES=60`, `MARKET_LATEST_CONTEXT_TTL_MINUTES=10` 추가(주석으로 분 단위/최소값/재시작 필요/비용 영향 명시).
  - git 상에서는 `.env. example` → `.env.example` rename으로 인식된다. 템플릿은 placeholder만 포함하며 실제 secret은 없다.

## 동작 변화

- `ENABLE_SCHEDULER=true`일 때 가격/뉴스 갱신 간격이 환경변수로 조정된다.
- 종목 상세 `latest-context` cache의 유효시간이 환경변수로 조정된다. 만료 전에는 cache 재사용, 만료 후 첫 요청에서 재조회한다(`force_refresh=true`는 기존대로 즉시 재조회).
- 환경변수 미지정 시 기존과 동일(5분/60분/10분).
- AI 리포트 생성 주기(`REPORT_SCHEDULER_*`)는 이 변경과 무관하며 그대로 유지된다. 사용자/챗봇 요청이 리포트를 실시간 생성하지 않는 규칙도 변함이 없다.

## 검증

- `.venv` python으로 `app.core.config.settings` import → 기본값 `prices=5 news=60 ctx=10` 확인.
- 환경변수 오버라이드 확인: `MARKET_PRICES_REFRESH_MINUTES=2` → `2`, `MARKET_NEWS_REFRESH_MINUTES=0` → 보정되어 `1`, `MARKET_LATEST_CONTEXT_TTL_MINUTES=30` → `_latest_context_ttl_seconds()=1800`.
- `pytest -q` (backend): 98 passed, 2 failed.
  - 실패 2건은 `tests/test_subscription_api.py`의 결제 provider checkout URL 테스트로, 결제 provider 환경값 부재로 인한 **기존 실패**이며 이번 변경(시장 데이터 주기)과 무관하다. 본 변경은 billing/payment 코드를 건드리지 않는다.
- `tests/test_macro_service.py`, `tests/test_database_config.py` 단독 실행: 19 passed.

## 미실행 / 후속 위험

- 프론트엔드 빌드는 이 변경이 백엔드 전용이라 실행하지 않았다.
- scheduler 간격을 크게 줄이면 yfinance 등 무료 provider 호출 빈도와 부하/rate limit 위험이 증가한다(AGENTS.md 섹션 9). 운영 시 보수적으로 설정한다.
- `_latest_context_ttl_seconds()`는 호출 시점에 `settings`를 읽으므로, 프로세스 재시작 없이 동적 변경되지는 않는다(환경변수는 프로세스 시작 시 로드). 값 변경 후에는 backend 재시작이 필요하다.
