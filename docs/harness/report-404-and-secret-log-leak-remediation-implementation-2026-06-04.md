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

### Backend (문제 B)
- [backend/app/main.py](../../backend/app/main.py)
  - `logging.basicConfig` 직후 `httpx`, `httpcore`, `sqlalchemy.engine` 로거 레벨을 `WARNING`으로 낮추는 루프 추가. root 레벨은 INFO 유지(앱 로그는 그대로), 외부 URL/SQL echo만 INFO에서 빠진다. WARNING 이상은 유지되므로 오류 추적에는 영향이 적다.

### Tests
- [backend/tests/test_ai_report_quality_gate.py](../../backend/tests/test_ai_report_quality_gate.py)
  - `_describe_supported_numbers`/`_collect_supported_numbers`/`_normalize_numeric_token` import 추가.
  - `test_describe_supported_numbers_collects_raw_tokens_from_facts`: 헬퍼가 `report_facts`/`structured_facts`의 원문 토큰(`200.0`, `1.25`, `3.62%`, `21`)을 중복 없이 상한 이내로 수집하는지 검증.
  - `test_describe_supported_numbers_subset_of_collect_supported_numbers`: 헬퍼가 보여주는 모든 토큰이 `_normalize_numeric_token`을 거쳐 fact_checker 허용 집합(`_collect_supported_numbers`)에 존재하는지(정합성) 검증.

## 동작 변화

- writer는 이제 fact_checker가 허용하는 동일 소스의 원문 숫자 목록을 입력으로 받는다. fact_checker 판정 로직·허용 집합 정의는 **변경 없음(엄격성 불변)** 이며 writer 입력만 친절해졌다.
- 외부 호출 URL과 SQL echo가 더 이상 INFO 로그로 평문 출력되지 않는다(WARNING 이상만 남음).
- 사용자/챗봇 요청이 리포트를 실시간 생성하지 않는다는 정책(AGENTS.md 14절)은 그대로다. 스케줄러만 생성하고 조회는 DB 읽기.

## 검증

```powershell
cd backend
py -m compileall app
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; import app.main; print('import ok')"
```

- `py -m compileall app`: 성공(`app/main.py`, `app/services/graph/nodes.py` 포함 전체 컴파일).
- `pytest tests/test_ai_report_quality_gate.py`: **26 passed** (신규 2건 포함).
- import smoke: `import ok`.
- 실제 LLM 생성/네트워크 호출은 하지 않았다(비용·키 회피).

## 미실행 / 사후 확인

- 실제 NVDA 리포트 생성 성공은 다음 스케줄러 run 로그(`NVDA 리포트 생성 완료`)와 `/api/reports/NVDA` 200으로 사후 확인 필요.
- 로깅 변경 효과는 배포 후 Render 로그에 외부 URL/SQL이 더 이상 INFO로 남지 않는지 사후 점검.
- 프론트 lint/build는 이 변경(backend 전용)과 무관해 실행하지 않음.

## 후속 위험 / 운영 작업 (사용자)

- **노출 키 4종 로테이션(운영, 사용자만 가능)**: AGENTS.md 8절에 따라 로그에 노출된 Finnhub token, FRED `api_key`, ECOS key, Stooq `apikey`는 손상으로 간주. 발급처에서 재발급 후 Render 환경변수 갱신. 키 교체 시 잠깐 외부 데이터 호출이 실패할 수 있으니 갱신과 재배포를 같은 시점에 진행.
- **`SQLALCHEMY_ECHO=false` 확인(운영)**: 기본값은 `False`이나 Render에 `SQLALCHEMY_ECHO=true`가 설정돼 있을 가능성이 있어 확인/해제 필요. 코드 레벨에서도 `sqlalchemy.engine` 로거를 WARNING으로 낮춰 이중 방어.
- writer 화이트리스트는 상한 40개로 잘릴 수 있다. 자산에 따라 토큰이 많으면 일부가 누락될 수 있으나, fact_checker는 여전히 전체 소스 기준으로 판정하므로 안전(누락 토큰을 쓰면 거부되어 재작성 유도). 상한은 프롬프트 길이/비용 트레이드오프로 조정 가능.
- DB 스키마·마이그레이션 변경 없음. 스케줄러 주기·리포트 생성 빈도·트리거 확장 없음(AGENTS.md 14절 정책 불변).
