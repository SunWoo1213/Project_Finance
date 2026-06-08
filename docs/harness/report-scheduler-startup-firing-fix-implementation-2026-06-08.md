# 리포트 스케줄러 기동 직후 발화 보정 구현 (interval 최초 발화 +1주기 → 기동 직후)

Date: 2026-06-08
Status: 구현 완료 (코드 변경 + 테스트). 운영/배포 설정 변경 없음.
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

분석 출처: `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md` (1차 로그, 1순위 원인) / 에러 케이스북 사례 15.

## Objective

1차 로그(2026-06-08 01:03~05)에서 확정된 1순위 차단 지점을 코드로 해소한다: 리포트 생성 잡이 **인스턴스 수명보다 늦게 발화**해 한 번도 실행되지 못하는 문제.

- `generate_daily_reports`는 `interval`(기본 6~12h) 트리거라 **최초 발화가 기동 +1주기 후**다.
- 실질 발화 경로였던 별도 `generate_daily_reports_startup`(date, +180초) 잡은, sleep/재시작형 런타임(Render free 등)이 180초 전에 종료·재기동하면서 타이머가 0부터 다시 시작돼 끝내 발화하지 못했다.

목표 동작(사용자/챗봇이 리포트를 실시간 생성하지 않음, 저장 리포트만 조회)과 **생성 주기·회당 최대·쿨다운은 모두 불변**이다. 이번 변경은 "첫 발화 시점"만 앞당긴다.

## Changes

### 1. interval 잡에 `next_run_time` 부여 + 중복 startup 잡 제거 — `backend/app/main.py` (lifespan)

- 기존: `generate_daily_reports`(interval) + `generate_daily_reports_startup`(date, +STARTUP_DELAY) 두 개 등록.
- 변경: `generate_daily_reports`(interval) **하나**로 통합하고 `next_run_time=datetime.now() + timedelta(seconds=REPORT_SCHEDULER_STARTUP_DELAY_SECONDS)`를 지정. interval 트리거의 최초 발화가 기동 직후(startup delay 후)로 당겨지고 이후 주기는 그대로 유지된다. 별도 startup date 잡은 제거(이 한 줄로 대체).
- 상태 로그도 `reports: in {delay}s then every {N} hours`로 변경해 첫 발화 시점이 보이게 했다.
- 주기(`REPORT_SCHEDULER_INTERVAL_HOURS`), 회당 최대(`REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`), 쿨다운(`REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`)은 변경 없음 → 비용/빈도 증가 아님.

### 2. startup delay 기본값 180 → 60초 — `backend/app/core/config.py`

- `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 기본값을 180 → 60으로 낮춰, 짧은 수명 인스턴스가 첫 발화 전에 죽을 확률을 줄였다.
- warm-up은 비차단이고 `generate_report_for_ticker`가 per-ticker 캐시 fill로 보강하므로(또한 2026-06-08 스냅샷 stale 유지 구현으로 가격 0 고착도 완화), 60초에 발화해도 데이터 준비는 견딘다.
- 0/음수는 기존 validator(`enforce_non_negative_startup_delay`)가 0으로 보정 — 불변.

### 3. 테스트 — `backend/tests/test_ai_report_generation_switch.py`

- 추가: `test_lifespan_registers_single_report_job_with_startup_next_run_time` — ENABLE_AI_REPORT_GENERATION=True일 때 `generate_daily_reports`가 1개만 등록되고 `trigger=="interval"`, `next_run_time`이 `datetime`으로 설정되며 `generate_daily_reports_startup`은 등록되지 않음을 검증.
- 기존 `test_lifespan_skips_report_jobs_when_ai_report_generation_disabled`(두 잡 모두 미등록)는 그대로 통과.

## Verification

```powershell
cd backend
py -m compileall app/main.py app/core/config.py            # EXIT=0
# 식별용 더미 env 주입(시크릿 아님) 후:
py -m pytest tests/test_ai_report_generation_switch.py tests/test_price_providers.py -q
```

결과: **35 passed** (스케줄러 신규 1건 + 직전 provider 폴백/stale 4건 포함). 컴파일 통과. (env 주입 사유는 provider 구현 기록과 동일 — `PROJECT_NAME`/`API_V1_STR`/`DATABASE_URL` 부재 시 Settings 검증으로 collection 실패.)

## 실행하지 않은 것 / 사유

- 실배포 기동 로그 확인: 로컬 검증 범위 밖. 배포 후 `[lifespan] scheduler started (... reports: in 60s then every N hours)` → `AI 리포트 생성 시작` → `{ticker} 리포트 생성 완료` 순으로 확인 필요.
- DB 컨테이너/실 LLM 호출: 미실행(테스트는 FakeScheduler/monkeypatch 기반).
- 프론트엔드 lint/build: 프론트 변경 없음 → 생략.

## 한계 / 후속 위험

- 이 변경은 in-process scheduler의 **첫 발화 시점**만 앞당긴다. 인스턴스가 startup delay(기본 60초)보다 먼저 죽으면 여전히 발화하지 못한다. 근본적으로 안정적인 cadence가 필요하면 분석 문서의 **Option A(상시 가동 런타임)** 또는 **Option B(token-protected task endpoint + 외부 cron)** 가 필요하다(인프라/운영 결정, 별도 승인).
- 첫 발화가 60초로 당겨지면 warm-up 미완료 시점에 캐시 miss가 날 수 있으나, per-ticker 캐시 fill + 스냅샷 stale 유지로 완화된다. 그래도 콜드 스타트에 모든 provider가 실패하면 readiness blocked가 가능(provider 키/플랜 점검 필요).
- ENABLE_SCHEDULER / ENABLE_AI_REPORT_GENERATION이 배포에서 false면 이 변경과 무관하게 리포트는 생성되지 않는다(운영 스위치 확인 필요).

## Documentation

- feature: `docs/harness/features/asset-detail-ai-community.md`, `docs/harness/features/deployment-runtime.md` (Change Records).
- index: `docs/harness/feature-index.md` 항목 추가.
- 분석/케이스북: `docs/harness/report-generation-scheduler-not-firing-log-audit-2026-06-08.md`(1순위 구현 상태 갱신), 에러 케이스북 사례 15(해결 표시).
- 환경변수 문서: `ENVIRONMENT_VARIABLE_SETUP.md`, `ENVIRONMENT_VARIABLE_RECOMMENDATIONS.md`의 `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` 설명을 새 기본값(60)·동작(interval next_run_time)으로 갱신.
