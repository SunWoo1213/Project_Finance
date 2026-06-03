# NVDA 리포트 생성 실패 정밀 원인 분석 (fact_checker 루프)

Date: 2026-06-04
Type: 분석/감사 (코드 변경 없음)
Feature:
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/deployment-runtime.md`
관련 문서:
- `docs/harness/report-404-and-secret-log-leak-remediation-plan-2026-06-04.md`

## 0. 질문

사용자가 제시한 두 가설 중 무엇이 원인인지(또는 제3의 원인인지) 정밀 분석한다.

1. **가설 A** — 평가 노드가 작성 노드와 다른 데이터를 보고 있다.
2. **가설 B** — 배포 툴이 무료라 리포트 작성 도중 프로세스가 끊긴다.

## 1. 결론 요약

- **가설 B(배포 끊김)는 거짓이다.** 로그가 명확히 반증한다. 프로세스는 끊긴 게 아니라 **정상적으로 끝까지 실행된 뒤 애플리케이션 레벨 예외(`ReportQualityError`)를 던졌고**, 이후 스케줄러가 정상 종료 로그(`AI 리포트 생성 종료`)를 두 줄 남겼다. 강제 종료/타임아웃이면 Python 트레이스백과 그 뒤의 질서 있는 종료 로그가 함께 남을 수 없다.
- **가설 A는 "정신"은 맞지만 대상이 틀렸다.** 실패시킨 노드는 `evaluator_node`가 **아니라** `fact_checker_node`다. evaluator는 이번 실행에서 **한 번도 도달하지 못했다**(fact_checker에서 3회 탈락 후 그래프가 END로 빠짐). 다만 "검증 노드가 작성 노드와 다른 숫자 기준을 본다"는 발상 자체는 일부 사실이다.
- **실제 root cause는 두 겹이다.**
  1. **writer LLM의 숫자 환각** — 어떤 fact 소스에도 없는 `22`를 매 재작성마다 반복 생성한다(프롬프트 규율을 LLM이 지키지 못함).
  2. **fact_checker 정규화의 부호/형식 비대칭** — `3.62%`(양수)와 `-3.62%`(음수)가 서로 다른 토큰으로 정규화되어, 데이터에 사실상 존재하는 등락률을 writer가 다른 부호/표현으로 쓰면 "미지원 숫자"로 오탐(false positive)된다.

즉 **데이터 부족(blocked)도, 배포 끊김도 아니고**, writer 환각 + fact_checker 매칭 규칙의 부호 비대칭이 맞물려 **재작성 루프가 3회 한도까지 탈락 → 미저장 → `/api/reports/NVDA` 404**로 이어진다.

## 2. 로그 정밀 판독

제공된 로그(시각 22:04:44 ~ 22:04:57):

```
22:04:44 writer_node done
22:04:44 report_format_validator_node pass
22:04:44 fact_checker_node fail (unsupported=22, revision_count->2)
22:04:44 writer_node start
22:04:57 writer_node done                         # 1회 재작성 ≈ 13초
22:04:57 report_format_validator_node pass
22:04:57 fact_checker_node fail (unsupported=3.62%, 22, revision_count->3)
22:04:57 ERROR ... ReportQualityError ... Unsupported numbers: -3.62%, 22 / 22 / 3.62%, 22
22:04:57 AI 리포트 생성 종료   (app.services.ai_service)
22:04:57 AI 리포트 생성 종료   (app.main)
```

판독 포인트:

- **포맷 검증은 항상 통과**한다(`report_format_validator_node pass`). 즉 10개 고정 섹션·자산군 분석 구조는 문제가 아니다. 오직 **fact_checker(숫자 검증)**만 탈락한다.
- 탈락 사유 숫자가 패스마다 진동한다: `22` → `3.62%, 22` → `-3.62%, 22` / `3.62%, 22`. **`22`는 모든 패스에서 고정**으로 나타나고, **`3.62%`는 부호(`+`/`-`)만 바뀌며 등장**한다. 이 진동 패턴이 두 root cause를 정확히 가리킨다(아래 4절).
- 마지막 `ReportQualityError` 메시지는 누적 `feedback`이라 3개 패스의 피드백이 합쳐져 출력된다. 새 결함이 아니라 같은 루프의 누적이다.

### 가설 B 반증 (배포 끊김 아님)

- 로그가 **정상 트레이스백 → `raise ReportQualityError` → 스케줄러 except에서 catch → `AI 리포트 생성 종료` 2줄**로 질서 있게 끝났다. 무료 배포 OOM/타임아웃 강제 종료라면 이런 정상 종료 로그가 남지 않는다.
- 종료 코드는 [ai_service.py:919-921](../../backend/app/services/ai_service.py#L919-L921)의 `except Exception ... logger.error("%s 리포트 실패", ...)`에서 찍힌 것이다. 이는 **코드가 의도적으로 던진 품질 예외**이지 외부 프로세스 킬이 아니다.
- 시간상으로도 마지막 두 패스가 13초이고 전체 실행이 짧다. 자원/시간 한계로 잘린 정황이 없다.

## 3. 데이터 흐름 — 누가 어떤 숫자를 보는가

### writer_node 입력 ([nodes.py:843](../../backend/app/services/graph/nodes.py#L843))
- 본문 작성 근거: `structured_facts`, `research_packet`, `analysis_framework`, `bull_thesis`, `bear_thesis`, `risk_review`, `feedback`.
- **허용 숫자 화이트리스트** `allowed_numbers` = `_describe_supported_numbers(state)` ([nodes.py:228](../../backend/app/services/graph/nodes.py#L228)). 소스는 `{report_facts, structured_facts, financial_facts, news_facts, macro_facts}`, **상한 40토큰**.
- 주의: writer는 `report_facts`/`financial_facts`/`news_facts`/`macro_facts` 원본을 **본문 근거로 받지 않는다**(`analysis_framework` 슬라이스만 받음). 즉 writer가 실제로 읽는 콘텐츠와, 허용 숫자 출처가 일치하지 않는다.

### fact_checker_node 허용 집합 ([nodes.py:946](../../backend/app/services/graph/nodes.py#L946), [nodes.py:178](../../backend/app/services/graph/nodes.py#L178))
- `_collect_supported_numbers({report_facts, structured_facts, financial_facts, news_facts, macro_facts})` + `0~10 정수` + `연도(올해±1)`.
- **상한 없음**(writer 화이트리스트는 40개 cap, 여기는 무제한).

### 두 노드 비교 (가설 A 검증)
- 출처 5종은 동일하나 **상한이 다르다**: writer는 40토큰만 안내받고, fact_checker는 전체를 허용. 방향상 writer가 더 좁게 안내받으므로 이 cap 자체가 직접 탈락 원인은 아니다(부차적 위험).
- **핵심 비대칭**: writer가 신뢰하는 본문 근거는 `structured_facts`(LLM 합성 결과)인데, fact_checker는 그보다 넓은 5종 원본을 본다. 게다가 writer는 자연스러운 애널리스트 어투로 숫자를 만들어낸다. 결국 "작성 노드와 검증 노드가 다른 숫자 세계를 본다"는 가설 A의 직관은 **fact_checker(평가 노드 아님) 기준에서 부분적으로 성립**한다.
- 그러나 `evaluator_node`([nodes.py:1013](../../backend/app/services/graph/nodes.py#L1013))는 이번 실패와 **무관**하다. fact_checker → (3회 실패) → `route_fact_check`가 `END` 반환 ([graph.py:22-29](../../backend/app/services/graph/graph.py#L22-L29))이라 evaluator까지 못 간다.

## 4. 실제 Root Cause 2종

### (1) writer의 숫자 환각 — `22`
- `22`는 `report_facts.price`(value/change_pct), 뉴스, structured_facts 어디에도 없는 값이다(0~10·연도 화이트리스트에도 없음). writer LLM이 P/E·일수·RSI 같은 "그럴듯한 분석 수치"를 본문에 끼워 넣는 전형적 환각이다.
- 누적 `feedback`에 "Unsupported numbers: 22"가 명시돼도 다음 패스에서 다시 `22`를 생성한다 → **피드백 루프가 환각 억제에 무력**하다. 프롬프트의 숫자 규율([nodes.py:865-869](../../backend/app/services/graph/nodes.py#L865-L869))은 텍스트 지시일 뿐 강제력이 없다.

### (2) fact_checker 정규화의 부호/형식 비대칭 — `3.62%` vs `-3.62%`
- 등락률은 `report_facts.price.change_pct`에 그대로 들어간다 ([ai_service.py:564-571](../../backend/app/services/ai_service.py#L564-L571)). 즉 등락률 숫자는 **사실상 데이터에 존재**한다.
- 그런데 `_normalize_numeric_token`([nodes.py:164](../../backend/app/services/graph/nodes.py#L164))은 `,`, `%`, `+`만 제거하고 **`-`(음수 부호)는 보존**한다.
  - 데이터 `change_pct = -3.62` → 정규화 `"-3.62"`
  - writer가 `"3.62% 하락"`처럼 **부호 없이 단어로** 방향을 표현 → `"3.62%"` → 정규화 `"3.62"`
  - `"3.62" ≠ "-3.62"` → **미지원으로 오탐**.
- 로그에서 `3.62%`의 부호가 패스마다 뒤집히며 등장하는 진동이 바로 이 부호 불일치의 증거다. writer가 같은 등락률을 어떤 패스엔 `-3.62%`(매칭됨), 어떤 패스엔 `3.62% 하락`(불일치)으로 쓰는 것이다.

### 두 원인의 합성
- 매 패스에서 `22`(항상 불일치) + `3.62%`(부호에 따라 가끔 불일치)가 동시에 탈락 → fact_checker는 절대 통과하지 못함 → `revision_count`가 3에 도달 → `route_fact_check`가 `END` → `result["is_pass"]=False` → [ai_service.py:825-831](../../backend/app/services/ai_service.py#L825-L831)에서 `ReportQualityError` → DB 미저장 → 조회 시 404.

## 5. 부차적 관찰 (직접 원인은 아니나 위험)

- **`revision_count` 한도 공유**: 포맷/fact/정성/evaluator 모든 검증이 같은 `revision_count`를 증가시킨다([nodes.py:929](../../backend/app/services/graph/nodes.py#L929) 등). 따라서 3회는 "fact_checker 3회"가 아니라 "전 검증 합산 3회"다. 이번엔 셋 다 fact_checker였다.
- **`allowed_numbers` 40토큰 cap**: 데이터가 풍부한 자산은 정작 필요한 토큰이 cap에 밀려 writer 안내에서 빠질 수 있다(writer는 더 좁게 안내받음). 환각과 직결되진 않지만 통과율을 떨어뜨린다.
- **writer 본문 근거와 검증 출처 불일치**: writer는 `structured_facts`(합성본) 위주로 쓰는데 fact_checker는 원본 5종을 본다. synthesizer가 숫자를 재서술/반올림하면 양쪽 토큰이 어긋날 수 있다.

## 6. 권장 해결 방향 (구현은 별도 — 본 문서는 분석만)

> 코드 변경은 본 문서 범위 밖이며, 적용 시 별도 plan/implement/verify와 변경 기록이 필요하다(AGENTS.md 섹션 12·14).

1. **부호 비대칭 제거 (가장 결정적·저위험)**: fact_checker 비교 시 등락률 등 방향성 수치를 **부호 무시(절댓값) 또는 양쪽 부호 모두 허용**으로 매칭하거나, 정규화에서 선행 `-`도 제거한 절댓값 키로 비교. → `3.62%`/`-3.62%` 오탐 제거. 단 의미상 부호가 중요한 맥락(증감 방향 오기)은 별도 정성 점검에 위임.
2. **환각 억제**: 기존 계획([report-404 plan](report-404-and-secret-log-leak-remediation-plan-2026-06-04.md))의 `allowed_numbers` 화이트리스트 주입을 적용하되, **cap(40) 상향 또는 제거**로 writer 안내 = fact_checker 허용을 일치시켜 `22` 같은 환각의 여지를 줄인다.
3. **루프 소진 시 폴백(404 즉시 해소)**: `revision_count>=3`로 빠질 때 무저장 대신, 마지막 초안에서 **미지원 숫자만 제거/정성 치환**한 안전본을 저장하거나 `quality_status` 표시 후 저장하는 폴백을 검토. → 사용자 화면 404 방지(품질 게이트 약화 여부는 사용자 승인 필요, AGENTS.md 섹션 9).
4. (확인) **배포 끊김 대응은 불필요** — 본 분석상 원인이 아니다.

## 7. 검증 메모

- 본 작업은 분석 전용으로 코드 변경·명령 실행이 없다. 따라서 빌드/테스트 미실행.
- 결론은 제공된 Render 로그와 현재 코드 정적 분석에 근거한다. NVDA의 실제 `change_pct` 원본값(부호)은 런타임 캐시 값이라 본 문서에서 단정하지 않되, 로그의 부호 진동 패턴이 (2) 원인을 강하게 뒷받침한다.
