# NVDA 리포트 404 + 로그 시크릿 노출 통합 해결 구현 기록

Date: 2026-06-04
Plan: [report-404-and-secret-log-leak-remediation-plan-2026-06-04.md](report-404-and-secret-log-leak-remediation-plan-2026-06-04.md)
Feature:
- [asset-detail-ai-community.md](features/asset-detail-ai-community.md)
- [deployment-runtime.md](features/deployment-runtime.md)

## 목적

서로 맞물린 두 문제를 한 번에 해결했다.

1. **문제 A — `/api/reports/NVDA` 영구 404**: writer가 넘겨받지 않은 환각 숫자를 만들고 fact_checker가 이를 반복 거부(`Unsupported numbers: ...`)해 `revision_count >= 3`에서 `ReportQualityError`로 끝나며 DB 미저장 → 조회 API 404. writer에게 허용 숫자 화이트리스트를 주입해 첫 초안부터 미지원 숫자를 줄였다.
2. **문제 B — 런타임 로그 외부 API 키 평문 노출**: root INFO 레벨 때문에 `httpx` 로거가 외부 호출 URL(쿼리스트링의 Finnhub token, FRED/ECOS/Stooq key)을 평문으로 찍고, `sqlalchemy.engine` SQL echo도 과도하게 출력됐다. 민감/노이즈 로거 레벨을 `WARNING`으로 낮췄다.

## 변경 파일

### Backend (문제 A)
- [backend/app/services/graph/nodes.py](../../backend/app/services/graph/nodes.py)
  - `_describe_supported_numbers(state, limit=40)` 헬퍼 추가. `_find_unsupported_numbers`와 동일한 payload(`report_facts`/`structured_facts`/`financial_facts`/`news_facts`/`macro_facts`)를 재귀 순회하되, **정규화 이전 원문 토큰**(예: `200.0`, `1.25`, `3.62%`)을 중복 제거하고 상한 40개까지 수집한다. `_normalize_numeric_token`으로 유효성만 거른다.
  - `writer_node`: 프롬프트의 부정형 한 줄(`넘겨받지 않은 숫자를 만들지 말라`)을 강화된 숫자 규율로 교체하고 `{allowed_numbers}` 블록을 추가. 허용 범위는 화이트리스트 + 0~10 정수 + 연도이며, 그 외 수치는 정성 서술 또는 '데이터 한계'로 바꾸라고 명시. `chain.invoke(...)`에 `allowed_numbers` 값을 주입(빈 목록이면 안전 문구).

### Backend (문제 B — 1차: httpx/SQL 로거 레벨)
- [backend/app/main.py](../../backend/app/main.py)
  - `logging.basicConfig` 직후 `httpx`, `httpcore`, `sqlalchemy.engine` 로거 레벨을 `WARNING`으로 낮추는 루프 추가. root 레벨은 INFO 유지(앱 로그는 그대로), 외부 URL/SQL echo만 INFO에서 빠진다. WARNING 이상은 유지되므로 오류 추적에는 영향이 적다.

### Backend (문제 B — 2차: 배포 로그 분석으로 발견한 추가 누수)

2026-06-03 배포 런타임 로그 분석 결과, 계획이 예상한 `httpx` INFO 누수 외에 **애플리케이션 로거가 WARNING/ERROR 레벨에서 예외를 그대로 출력하며 URL 안의 키가 노출**되는 더 직접적인 경로를 확인했다. 1차 로거 레벨 조정으로는 막히지 않으므로(앱 자체 로거가 출력) 마스킹 유틸을 추가했다.

- [backend/app/core/log_sanitizer.py](../../backend/app/core/log_sanitizer.py) (신규)
  - `redact_secrets(value, extra_secrets=None)`: 문자열의 민감 쿼리 파라미터(`serviceKey`/`api_key`/`apikey`/`token`/`key`/`auth`/`secret` 등) 값을 `***`로 치환. `extra_secrets`로 넘긴 리터럴(URL **경로**에 박히는 ECOS 키 등)도 치환. 빈/짧은(4자 미만) 값은 무시.
- [backend/app/services/price_providers.py](../../backend/app/services/price_providers.py)
  - 4개 `logger.warning(... %r, exc)`(snapshot/history/news/events provider 실패)를 `redact_secrets(repr(exc))`로 감쌈. 로그에 찍히던 data.go.kr `serviceKey`(평문 노출 확인됨), Stooq `apikey`, Finnhub `token` 쿼리 파라미터가 가려진다.
- [backend/app/services/macro_service.py](../../backend/app/services/macro_service.py)
  - commodity/KR bond/KR bond history 실패 로그 3곳을 `redact_secrets(repr(exc), [ECOS_API_KEY])`로 감쌈. ECOS는 키를 URL **경로**에 넣으므로 리터럴 마스킹 사용. FRED `api_key`는 쿼리 파라미터라 정규식으로 처리.
- [backend/app/main.py](../../backend/app/main.py)
  - `/api/market/history/{ticker}`의 500 핸들러 `detail=str(e)`를 `redact_secrets(str(e))`로 변경. FRED `HTTPStatusError`가 전파되면 api_key가 **HTTP 응답 본문**으로 새던 경로를 차단(로그보다 심각한 클라이언트 노출).

### Tests
- [backend/tests/test_ai_report_quality_gate.py](../../backend/tests/test_ai_report_quality_gate.py)
  - `_describe_supported_numbers`/`_collect_supported_numbers`/`_normalize_numeric_token` import 추가.
  - `test_describe_supported_numbers_collects_raw_tokens_from_facts`: 헬퍼가 `report_facts`/`structured_facts`의 원문 토큰(`200.0`, `1.25`, `3.62%`, `21`)을 중복 없이 상한 이내로 수집하는지 검증.
  - `test_describe_supported_numbers_subset_of_collect_supported_numbers`: 헬퍼가 보여주는 모든 토큰이 `_normalize_numeric_token`을 거쳐 fact_checker 허용 집합(`_collect_supported_numbers`)에 존재하는지(정합성) 검증.
- [backend/tests/test_log_sanitizer.py](../../backend/tests/test_log_sanitizer.py) (신규)
  - data.go.kr `serviceKey`, Finnhub `token`, FRED `api_key` 쿼리 파라미터가 `***`로 가려지고 비민감 파라미터는 보존되는지 검증.
  - ECOS 경로 리터럴 키가 `extra_secrets`로 가려지는지, 빈/짧은 값은 무시되는지 검증.

## 동작 변화

- writer는 이제 fact_checker가 허용하는 동일 소스의 원문 숫자 목록을 입력으로 받는다. fact_checker 판정 로직·허용 집합 정의는 **변경 없음(엄격성 불변)** 이며 writer 입력만 친절해졌다.
- 외부 호출 URL과 SQL echo가 더 이상 INFO 로그로 평문 출력되지 않는다(WARNING 이상만 남음).
- 사용자/챗봇 요청이 리포트를 실시간 생성하지 않는다는 정책(AGENTS.md 14절)은 그대로다. 스케줄러만 생성하고 조회는 DB 읽기.

## 검증

```powershell
cd backend
py -m compileall app
.\.venv\Scripts\python.exe -m pytest tests\test_log_sanitizer.py tests\test_ai_report_quality_gate.py
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; import app.main; from app.services import macro_service, price_providers; print('import ok')"
```

- `py -m compileall app`: 성공(`main.py`, `nodes.py`, `price_providers.py`, `macro_service.py`, `core/log_sanitizer.py` 포함 전체 컴파일).
- `pytest test_log_sanitizer.py test_ai_report_quality_gate.py`: **30 passed** (sanitizer 4건 + quality gate 신규 2건 포함).
- import smoke: `import ok`.
- 실제 LLM 생성/네트워크 호출은 하지 않았다(비용·키 회피).

## 미실행 / 사후 확인

- 실제 NVDA 리포트 생성 성공은 다음 스케줄러 run 로그(`NVDA 리포트 생성 완료`)와 `/api/reports/NVDA` 200으로 사후 확인 필요.
- 로깅 변경 효과는 배포 후 Render 로그에 외부 URL/SQL이 더 이상 INFO로 남지 않는지 사후 점검.
- 프론트 lint/build는 이 변경(backend 전용)과 무관해 실행하지 않음.

## 배포 로그 분석 메모 (2026-06-03 런타임)

- **문제 A 진행 상태**: NVDA 리포트 생성은 research agent(news/financial/macro, DDG 웹검색) 단계까지 진행되다가 서버 `Shutting down`(배포/재시작)으로 한 번 중단됐고, 이후 다시 research 단계를 도는 중에 로그가 끊겼다. writer/fact_checker 단계까지 도달한 로그가 없어 화이트리스트 효과는 이번 로그로는 확인 불가. `/api/reports/NVDA` 404는 아직 저장 전이라 정상(미완료). 다음 완주 run에서 `NVDA 리포트 생성 완료` + 200으로 확인 필요. research agent의 DDG 검색이 느리고 429/timeout이 잦아 완주 시간이 길다(별도 기존 이슈).
- **문제 B 확인/확장**: 로그에서 data.go.kr `serviceKey`가 `app.services.price_providers` **WARNING** 라인에 평문으로 찍히는 것을 직접 확인했다. 이는 1차 httpx 로거 조정으로 막히지 않아 위 2차 마스킹(`redact_secrets`)을 추가했다.

## 후속 위험 / 운영 작업 (사용자)

- **노출 키 로테이션(운영, 사용자만 가능, 우선순위 높음)**: 2026-06-03 배포 로그에 data.go.kr `serviceKey`가 평문 노출됐고 해당 로그가 채팅에도 공유됐다. AGENTS.md 8절에 따라 **이 공공데이터포털 serviceKey는 손상으로 간주하고 즉시 재발급**해야 한다. 함께 노출 위험이 있는 Finnhub token, FRED `api_key`, ECOS key, Stooq `apikey`도 점검·로테이션 권장. 발급처 재발급 후 Render 환경변수 갱신. 키 교체 시 잠깐 외부 데이터 호출이 실패할 수 있으니 갱신과 재배포를 같은 시점에 진행.
- **`SQLALCHEMY_ECHO=false` 확인(운영)**: 기본값은 `False`이나 Render에 `SQLALCHEMY_ECHO=true`가 설정돼 있을 가능성이 있어 확인/해제 필요. 코드 레벨에서도 `sqlalchemy.engine` 로거를 WARNING으로 낮춰 이중 방어.
- writer 화이트리스트는 상한 40개로 잘릴 수 있다. 자산에 따라 토큰이 많으면 일부가 누락될 수 있으나, fact_checker는 여전히 전체 소스 기준으로 판정하므로 안전(누락 토큰을 쓰면 거부되어 재작성 유도). 상한은 프롬프트 길이/비용 트레이드오프로 조정 가능.
- DB 스키마·마이그레이션 변경 없음. 스케줄러 주기·리포트 생성 빈도·트리거 확장 없음(AGENTS.md 14절 정책 불변).
