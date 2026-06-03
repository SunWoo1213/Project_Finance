# NVDA 리포트 404 + 로그 시크릿 노출 통합 해결 계획

Date: 2026-06-04
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`

## Objective

서로 맞물린 두 문제를 한 번에 해결한다.

1. **문제 A — `/api/reports/NVDA` 영구 404**: 리포트 생성이 fact_checker 품질 게이트에서 반복 탈락(`Unsupported numbers: 3.62%, 21`)해 `ReportQualityError`로 끝나고 DB에 저장되지 않아, 조회 API가 계속 404를 낸다. Render 로그상 NVDA 실데이터(Finnhub)는 정상 수신되므로 데이터 부족(blocked)이 아니라 **writer 환각 숫자 → fact_checker 거부 루프**가 원인이다.

2. **문제 B — 런타임 로그에 외부 API 키 평문 노출**: 배포 로그의 외부 호출 URL에 Finnhub token, FRED `api_key`, ECOS key, Stooq `apikey`가 쿼리스트링으로 그대로 찍힌다. 추가로 `sqlalchemy.engine` SQL echo가 production에서 켜져 있어 로그가 과도하게 길고 민감 쿼리가 노출될 수 있다. AGENTS.md 섹션 8에 따라 노출 키는 손상으로 간주하고 로테이션하며, 재노출을 막도록 로깅을 보강한다.

## 문제 A — 현재 동작 / 목표 동작

### 현재 동작
- `writer_node` 프롬프트에는 "넘겨받지 않은 숫자를 만들지 말라"는 부정형 한 줄만 있고 ([nodes.py:818](../../backend/app/services/graph/nodes.py#L818)), 허용 숫자 목록은 주지 않는다.
- `fact_checker_node`는 `_collect_supported_numbers()`(=`report_facts`/`structured_facts`/`financial_facts`/`news_facts`/`macro_facts`의 숫자 + 0~10 + 연도) 외의 숫자를 전부 거부한다 ([nodes.py:178](../../backend/app/services/graph/nodes.py#L178), [nodes.py:889](../../backend/app/services/graph/nodes.py#L889)).
- 실패 피드백은 위반 숫자만 알려주고 허용 목록은 writer에 전달되지 않는다. 데이터가 적은 자산일수록 writer가 학습지식 숫자로 빈틈을 메워 `revision_count >= 3`까지 실패 → 미저장 → 404.

### 목표 동작
- fact_checker 판정·허용 집합 정의는 **그대로 유지(엄격성 불변)** 한다.
- writer 프롬프트에 **허용 숫자 화이트리스트(allowed_numbers)** 를 원문 토큰 형태(예: `200`, `1.25%`)로 주입하고, "이 목록과 0~10·연도 외의 숫자는 절대 쓰지 말 것. 추가 수치가 필요하면 정성 서술 또는 '데이터 한계'로 바꿀 것" 규율을 강화한다.
- writer가 보는 허용 목록은 fact_checker가 쓰는 동일 fact 소스에서 파생해 둘이 어긋나지 않게 한다.
- 결과적으로 첫 초안부터 미지원 숫자가 줄어 통과율↑, 재작성 루프↓ → NVDA 리포트가 저장되어 404 해소.

## 문제 B — 현재 동작 / 목표 동작

### 현재 동작
- `logging.basicConfig(level=logging.INFO)` ([main.py:38](../../backend/app/main.py#L38))로 root가 INFO라, `httpx` 로거가 모든 외부 요청 URL(쿼리스트링의 키 포함)을 INFO로 출력한다.
- production 로그에 `sqlalchemy.engine.Engine` SQL echo가 켜져 있다(긴 카탈로그 쿼리까지 노출). `SQLALCHEMY_ECHO` 기본값은 `False`이므로 ([config.py:80](../../backend/app/core/config.py#L80)), Render 환경변수에 `SQLALCHEMY_ECHO=true`가 설정돼 있을 가능성이 높다.

### 목표 동작
- 외부 호출 URL이 로그에 평문으로 남지 않게 `httpx`(및 `httpcore`) 로거 레벨을 `WARNING` 이상으로 올린다.
- production에서 `sqlalchemy.engine` 로거가 과도한 SQL을 찍지 않게 `SQLALCHEMY_ECHO=false`를 확정하고, 로거 레벨도 `WARNING`으로 낮춘다.
- 노출된 키 4종은 사용자가 발급처에서 로테이션하고 Render 환경변수를 갱신한다(코드 변경과 독립적인 운영 작업).

## 변경 대상 파일

### Backend (문제 A)
- `backend/app/services/graph/nodes.py`
  - `_collect_supported_numbers`와 동일 fact 소스를 순회하되 **정규화 이전 원문 숫자 토큰**을 모으는 헬퍼 추가(예: `_describe_supported_numbers(state) -> list[str]`), 상한 개수 제한.
  - `writer_node`: 프롬프트에 `{allowed_numbers}` 블록 + 강화된 숫자 규율 추가, `chain.invoke(...)`에 `allowed_numbers` 주입. 기존 부정형 문장을 허용 목록 참조형으로 구체화.

### Backend (문제 B)
- `backend/app/main.py`
  - `logging.basicConfig` 직후 노이즈/민감 로거 레벨 조정: `logging.getLogger("httpx").setLevel(WARNING)`, `logging.getLogger("httpcore").setLevel(WARNING)`, `logging.getLogger("sqlalchemy.engine").setLevel(WARNING)`. (root 레벨은 환경변수로 조정 가능하게 두되, 최소 변경으로 위 3개만 명시적으로 낮춘다.)
- (선택) `backend/app/core/config.py`
  - 로그 레벨을 환경변수로 제어할 필요가 있으면 `LOG_LEVEL`/`HTTPX_LOG_LEVEL` 설정 추가 검토. 1차 구현에서는 하드코딩 레벨 조정으로 충분하면 생략.

### Tests
- `backend/tests/test_ai_report_quality_gate.py`
  - 신규 헬퍼가 `report_facts`/`structured_facts`의 원문 숫자 토큰을 수집하는지 결정적 단위 테스트.
  - 신규 헬퍼 토큰이 `_collect_supported_numbers` 허용 집합에 포함되는지(정합성) 테스트.
- 로깅 변경은 부작용 검증이 어렵고 LLM/네트워크와 무관하므로, import/기동 확인으로 갈음(별도 단위 테스트는 만들지 않음).

### Docs
- `docs/harness/report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md` (구현 단계)
- `docs/harness/features/asset-detail-ai-community.md` (writer 단계 설명·Change Records)
- `docs/harness/features/deployment-runtime.md` (로깅/시크릿 처리 메모·Change Records)
- `docs/harness/feature-index.md` (본 계획/구현 기록 링크)
- `docs/harness/error-casebook-2026-06-03.md` (① fact_checker 루프 404 ② 로그 키 노출 두 사례 추가)

### 설정 / DB / 운영
- DB 스키마·마이그레이션 변경 없음.
- Render 환경변수: `SQLALCHEMY_ECHO=false` 확인/설정(운영). 노출 키 4종 로테이션 후 갱신(운영).

## 단계별 구현 계획

1. (문제 A) `nodes.py`에 `_describe_supported_numbers(state)` 추가 — `_find_unsupported_numbers`가 쓰는 동일 payload를 순회해 `NUMERIC_TOKEN_PATTERN` 원문 토큰을 중복 제거·상한(예: 40개)으로 수집.
2. (문제 A) `writer_node` 프롬프트에 숫자 규율 강화 문구 + `{allowed_numbers}` 블록 추가, `invoke`에 값 주입. 빈 목록이면 "확정 숫자가 없으니 가격/기준 숫자 외 수치를 쓰지 말라" 안전 문구.
3. (문제 B) `main.py`에서 `httpx`/`httpcore`/`sqlalchemy.engine` 로거 레벨을 `WARNING`으로 낮춤.
4. (테스트) `test_ai_report_quality_gate.py`에 헬퍼 단위 테스트 2건 추가.
5. 검증 명령 실행(아래).
6. 구현 기록 작성 + feature 문서 2종·feature-index·error-casebook 갱신.
7. (운영, 사용자) 키 4종 로테이션 → Render 환경변수 갱신 → `SQLALCHEMY_ECHO=false` 확인 → 재배포.

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **Risky Change 해당 없음**: DB 스키마/마이그레이션·인증/해시 변경 없음, **스케줄러 주기·리포트 생성 빈도·트리거 확장 없음**(섹션 14 정책 불변 — 여전히 스케줄러만 생성, 조회는 DB 읽기), 유료 API 추가 없음, 프레임워크 교체 없음.
- **비용**: 재작성 루프 실패 감소로 LLM 호출은 유지 또는 감소.
- **품질 게이트 약화 아님**: fact_checker 로직 불변, writer 입력만 친절해짐.
- **로깅 변경 위험**: `httpx`/`sqlalchemy.engine` 레벨을 낮추면 디버깅용 요청 로그가 줄어든다. WARNING 이상은 유지되므로 오류 추적에는 영향 적음. 필요 시 환경변수로 다시 올릴 수 있게 설계 검토.
- **시크릿 로테이션**: 키 교체 시 잠깐 외부 데이터 호출이 실패할 수 있으니, Render 환경변수 갱신과 재배포를 같은 시점에 진행한다(운영 주의).

→ 사용자 추가 승인이 필요한 Risky Change는 아니다. 단, 키 로테이션은 사용자만 수행 가능한 운영 작업이다.

## 검증 계획 (AGENTS.md 섹션 6 최소 집합)

```powershell
cd backend
py -m compileall app
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; import app.main; print('import ok')"
```

- 실제 LLM 생성/네트워크 호출은 하지 않는다(비용·키 회피).
- 로깅 변경은 기동 import로 확인하고, 배포 후 Render 로그에 외부 URL/SQL이 더 이상 INFO로 남지 않는지 사후 점검한다.
- NVDA 실제 생성 성공은 다음 스케줄러 run 로그(`NVDA 리포트 생성 완료`)와 `/api/reports/NVDA` 200으로 사후 확인한다.

## 갱신할 문서

- `docs/harness/features/asset-detail-ai-community.md`: Data Flow writer 단계에 "허용 숫자 화이트리스트를 writer 입력으로 전달" 추가, Change Records 링크.
- `docs/harness/features/deployment-runtime.md`: 로깅 레벨/시크릿 비노출 정책 메모, Change Records 링크.
- `docs/harness/feature-index.md`: 본 계획·구현 기록 링크 추가.
- `docs/harness/error-casebook-2026-06-03.md`: 두 사례(404 루프, 로그 키 노출) 및 해결책 추가.
