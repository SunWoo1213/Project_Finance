# 리포트 writer 허용 숫자 화이트리스트 주입 계획

Date: 2026-06-04
Feature:
- `docs/harness/features/asset-detail-ai-community.md`

## Objective

`/api/reports/{ticker}`가 NVDA에서 404를 반환하는 근본 원인을 제거한다. Render 로그상 실제 원인은 데이터 부족(blocked)이 아니라 **fact_checker 품질 게이트 반복 탈락**이다.

```
NVDA 리포트 실패: Report generation rejected by evaluator for NVDA:
Fact checker failed: final draft contains numeric claims not found in structured facts.
Unsupported numbers: 3.62%, 21. ...
app.services.ai_service.ReportQualityError
```

writer_node가 structured_facts에 없는 숫자(`3.62%`, `21` 등 LLM 환각/학습지식 유래 수치)를 계속 초안에 넣고, fact_checker가 이를 거부해 writer로 되돌리는 재작성 루프가 `revision_count >= 3`까지 반복된다. 끝내 통과하지 못하면 `is_pass=False`로 그래프가 종료되고, `generate_report_for_ticker()`가 `ReportQualityError`를 던져 **리포트를 DB에 저장하지 않는다**. 그 결과 조회 API가 영구적으로 404를 낸다.

목표는 **fact_checker의 엄격성은 그대로 유지**하면서, writer가 처음부터 "사용 가능한 숫자"만 쓰도록 프롬프트에 허용 숫자 목록을 명시적으로 주입하고 재작성 피드백을 강화해 환각 숫자 유입을 근본에서 줄이는 것이다.

## 현재 동작 / 목표 동작

### 현재 동작
- `writer_node` 프롬프트에는 "넘겨받지 않은 숫자를 만들지 말라"는 **부정형 한 줄 지시만** 있다 ([nodes.py:818](../../backend/app/services/graph/nodes.py#L818)). 어떤 숫자가 허용되는지 명시적 목록은 주지 않는다.
- `fact_checker_node`는 `_collect_supported_numbers()`로 `report_facts`/`structured_facts`/`financial_facts`/`news_facts`/`macro_facts`에 등장하는 숫자 + 0~10 + (작년/올해/내년)을 허용 집합으로 만들고, 초안의 그 외 숫자를 전부 거부한다 ([nodes.py:178](../../backend/app/services/graph/nodes.py#L178), [nodes.py:889](../../backend/app/services/graph/nodes.py#L889)).
- fact_checker 실패 피드백은 "Unsupported numbers: 3.62%, 21" 처럼 **위반 숫자만** 알려주고, 허용 숫자 목록은 writer에게 전달되지 않는다.
- 데이터가 적은 자산(NVDA: FMP/Finnhub 재무 키 없으면 가격·뉴스 외 수치가 희소)일수록 writer가 빈틈을 학습지식 숫자로 메우려 해서 루프가 거의 항상 실패 → 리포트 미저장 → 404.

### 목표 동작
- writer_node 프롬프트에 **사용 가능한 숫자 목록(allowed_numbers)** 을 원문 토큰 형태(예: `200`, `1.25%`)로 함께 전달한다.
- writer 프롬프트의 숫자 규율을 강화한다: "아래 allowed_numbers와 0~10, 연도 외의 어떤 숫자도 쓰지 말 것. 추가 수치가 필요하면 숫자 대신 정성 서술로 바꾸거나 '데이터 한계'로 명시할 것."
- 재작성 시 fact_checker가 지적한 위반 숫자 + 허용 목록을 함께 강조해, 같은 숫자를 다시 넣지 않도록 한다.
- fact_checker의 판정 로직과 허용 집합 정의는 **변경하지 않는다**(엄격성 유지). writer가 보는 허용 목록은 fact_checker가 쓰는 `_collect_supported_numbers`와 **동일한 소스**에서 파생해 둘이 어긋나지 않게 한다.
- 결과적으로 첫 초안부터 미지원 숫자가 줄어 통과율이 오르고, NVDA 등에서 리포트가 저장되어 404가 해소된다. (재작성 횟수 감소로 오히려 LLM 호출 비용은 줄거나 동일하다.)

## 변경 대상 파일

### Backend
- `backend/app/services/graph/nodes.py`
  - `_collect_supported_numbers`와 동일한 fact 소스를 순회하되, **정규화 이전의 원문 숫자 토큰**(단위 `%`, 부호 포함)을 사람이 읽을 수 있게 모으는 헬퍼 추가 (예: `_describe_supported_numbers(state) -> list[str]`). fact_checker의 허용 집합과 같은 payload를 사용해 양쪽이 일치하도록 한다.
  - `writer_node`:
    - 프롬프트에 `allowed_numbers` 입력 변수와 강화된 숫자 규율 문구 추가.
    - `chain.invoke(...)`에 `allowed_numbers` 값을 주입.
  - 기존 "넘겨받지 않은 숫자를 만들지 말라" 문장은 허용 목록 참조 형태로 구체화.

### Tests
- `backend/tests/test_ai_report_quality_gate.py`
  - 신규 헬퍼가 `report_facts`/`structured_facts`의 원문 숫자 토큰을 수집하는지에 대한 결정적 단위 테스트 추가.
  - 신규 헬퍼가 모은 토큰이 `_collect_supported_numbers` 허용 집합 안에 들어가는지(둘의 정합성) 확인하는 테스트 추가.
  - (LLM 호출 없는 범위) writer 프롬프트 정합성은 헬퍼 단위로만 검증하고, 실제 LLM 생성 테스트는 만들지 않는다(AGENTS.md 섹션 4·10).

### Docs
- `docs/harness/report-writer-supported-number-whitelist-implementation-2026-06-04.md` (구현 단계에서 작성)
- `docs/harness/features/asset-detail-ai-community.md` (Data Flow의 writer 단계 설명·Change Records 갱신)
- `docs/harness/feature-index.md` (본 계획/구현 기록 링크 추가)
- `docs/harness/error-casebook-2026-06-03.md` (NVDA fact-checker 루프 404 사례 추가 검토)

### 설정 / DB
- 없음. 환경변수, DB 스키마, 마이그레이션 변경 없음.

## 단계별 구현 계획

1. `nodes.py`에 `_describe_supported_numbers(state)` 추가. `_find_unsupported_numbers`가 쓰는 동일한 fact payload(`report_facts`, `structured_facts`, `financial_facts`, `news_facts`, `macro_facts`)를 순회해 `NUMERIC_TOKEN_PATTERN`으로 원문 토큰을 모으고, 중복 제거 후 상한 개수(예: 40개)로 제한한 리스트를 반환한다.
2. `writer_node` 프롬프트에 숫자 규율 강화 문구와 `{allowed_numbers}` 블록을 추가하고, `chain.invoke`에 `"allowed_numbers"`를 주입한다. 빈 목록일 때는 "제공된 확정 숫자가 없으니 가격/기준 숫자 외에는 수치를 쓰지 말라"는 안전 문구를 넣는다.
3. fact_checker 실패 후 재작성에서 writer가 받는 `feedback`에는 이미 위반 숫자가 들어오므로, 프롬프트에서 allowed_numbers와 feedback을 함께 강조하도록 문구를 정리한다.
4. `test_ai_report_quality_gate.py`에 헬퍼 단위 테스트 2건 추가(토큰 수집·허용 집합 정합성).
5. 검증 명령 실행(아래).
6. 구현 기록 작성 및 feature 문서·index·error-casebook 갱신.

## 위험과 Risky Change 여부

- **AGENTS.md 섹션 9 Risky Change 해당 없음**: DB 스키마/마이그레이션 변경 없음, 인증·해시 변경 없음, **스케줄러 주기·리포트 생성 빈도·트리거 확장 없음**, 유료 API 추가 없음, 프레임워크 교체 없음. 프롬프트 문구와 그래프 상태 입력만 보강한다.
- **비용 영향**: 재작성 루프 실패가 줄어 LLM 호출 횟수는 유지되거나 감소한다. 비용 증가 위험 없음(섹션 14 관점에서도 사용자/챗봇 트리거 변화 없음 — 여전히 스케줄러만 생성, 조회는 DB 읽기).
- **품질 게이트 약화 아님**: fact_checker 판정·허용 집합 정의는 그대로 둔다. writer 입력만 친절해진다. 게이트 엄격성은 유지된다.
- 잔여 위험: writer 프롬프트가 길어져 토큰이 소폭 증가할 수 있다(허용 숫자 목록 상한으로 제한). 또한 데이터가 극히 적은 자산은 여전히 정성 서술로 채워야 하므로 통과를 보장하지는 않으나, 환각 숫자로 인한 영구 실패는 크게 줄어든다.

→ 사용자 추가 승인이 필요한 Risky Change는 아니므로 구현 단계로 진행 가능하다.

## 검증 계획 (AGENTS.md 섹션 6 최소 집합)

```powershell
cd backend
py -m compileall app
.\.venv\Scripts\python.exe -m pytest tests\test_ai_report_quality_gate.py
```

- 그래프 import 정상 확인:
```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.services.graph.graph import app; print('graph import ok')"
```
- 실제 LLM 생성/네트워크 호출은 하지 않는다(비용·키 회피). NVDA 실제 생성 성공 여부는 다음 스케줄러 run의 Render 로그(`NVDA 리포트 생성 완료`)로 사후 확인한다.

## 갱신할 문서

- `docs/harness/features/asset-detail-ai-community.md`: Data Flow 14번(writer) 설명에 "허용 숫자 화이트리스트를 writer 입력으로 전달" 추가, Change Records에 구현 기록 링크 추가.
- `docs/harness/feature-index.md`: 본 계획 문서와 구현 기록 링크를 Asset detail/AI report 행과 상단 목록에 추가.
- `docs/harness/error-casebook-2026-06-03.md`: "fact_checker 미지원 숫자 루프 → ReportQualityError → 리포트 미저장 → /api/reports/{ticker} 404" 사례와 해결책 추가 검토.
