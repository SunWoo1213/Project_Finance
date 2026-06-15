# 방학 보완 로드맵 (2026.06.18 ~ 08.28)

작성일: 2026-06-15
작성 관점: PM(제품 책임자) 가정
대상 기간: 2026-06-18 ~ 2026-08-28 (약 10주 / 11주차)

## 0. 배경과 목표

방학 동안 다음 세 가지를 디버깅 중심으로 보완한다.

1. **모델 교체 디버깅** — 챗봇/리포트의 LLM 모델을 바꿔 보며 문제를 식별하고 품질을 끌어올린다.
2. **유료 API 결제로 리포트 퀄리티 향상** — 무료 할당량/저가 모델의 한계를 유료 데이터·모델로 보완한다.
3. **DB 마이그레이션 검토** — UX(응답 지연, 안정성) 개선을 위해 현재 호스팅(체감상 Supabase)에서 PostgreSQL 매니지드 또는 AWS(RDS 등)로 이전을 검토한다.

기본 작업 방식은 **"디버깅 → 문제 식별 → 보완"** 사이클이다. 즉, 추측으로 고치지 않고 로그·재현·관측 데이터를 근거로 문제를 먼저 드러낸 뒤 수정한다.

## 1. 현황 진단 (착수 전 사실)

방학 작업의 출발점이 되는 코드 현황. 출처는 파일:라인으로 명시.

### 1.1 리포트 생성(LangGraph)
- 리포트 LLM은 **`gpt-4o-mini`가 코드에 하드코딩** — [graph/llm.py:8](backend/app/services/graph/llm.py#L8), `temperature=0.2`도 하드코딩(라인 9). 모델을 바꾸려면 코드 수정+배포가 필요하다.
- 노드 흐름: financial/news/macro agent(병렬) → synthesizer → bull/bear/risk → research_packet → writer → 포맷/숫자/정성 게이트 → 조건부 재작성(최대 `REPORT_MAX_REVISIONS=7`). [graph/graph.py](backend/app/services/graph/graph.py), [graph/nodes.py](backend/app/services/graph/nodes.py)
- 프롬프트가 노드별 `ChatPromptTemplate`로 코드에 박혀 있음 → 버전 관리/A·B 테스트가 어렵다.

### 1.2 챗봇
- 챗봇 모델은 **설정으로 분리**됨: `CHATBOT_LLM_MODEL="gpt-4o-mini"` — [config.py:143](backend/app/core/config.py#L143). 단 `temperature=0.3`와 시스템 프롬프트는 코드에 하드코딩([chat_llm.py](backend/app/services/chat_llm.py)).
- 기본값 `ENABLE_LLM_CHATBOT=false` — 기본은 규칙 기반 폴백([chat_tools.py](backend/app/services/chat_tools.py)), LLM 경로는 옵트인.
- 챗봇은 **리포트를 생성하지 않고 저장된 리포트 요약만 사용**(grounding). AGENTS.md 섹션 14 규칙과 일치 — 이 원칙은 방학 중에도 유지한다.

### 1.3 스케줄러/비용
- APScheduler가 `REPORT_SCHEDULER_INTERVAL_HOURS=6`로 6시간마다 실행 — [main.py:223-232](backend/app/main.py#L223-L232).
- 대상 5종목 고정(`DGS10,XAU,BTC-USD,NVDA,005930.KS`), 실행당 최대 5건, 종목 쿨다운 6h, 재작성 최대 7회 → **모델/API를 올리면 비용이 급증**할 수 있는 구조.

### 1.4 데이터베이스
- 표준 PostgreSQL을 `DATABASE_URL`로만 연결 — [config.py:60-62](backend/app/core/config.py#L60-L62), [session.py](backend/app/db/session.py). `postgres://`→`postgresql+asyncpg://` 자동 변환 validator 존재(config.py:192-209).
- **Supabase 고유 기능(Auth/Storage/Realtime/PostREST) 의존 0건.** 인증은 자체 Google OAuth + JWT([api/auth.py](backend/app/api/auth.py)).
- 테이블 14개, Alembic 마이그레이션 3개 존재([backend/alembic/versions/](backend/alembic/versions/)).
- docker-compose의 postgres는 **로컬 개발용**([docker-compose.yml](docker-compose.yml)).
- **함의:** 마이그레이션은 "스키마 이전(Alembic) + 데이터 덤프/복원 + `DATABASE_URL` 교체" 수준. SDK 잠금이 없어 난이도가 낮다.

## 2. 단계별 로드맵

> 원칙: 각 단계는 **디버깅으로 문제를 먼저 드러낸 뒤** 보완한다. 모든 코드 변경은 `docs/harness/`에 변경 기록을 남기고 feature 문서/색인을 갱신한다(AGENTS.md 12·13). 모델/유료 API/스케줄러 변경은 비용 영향이 있으므로 착수 전 명시적으로 위험을 적고 진행한다(AGENTS.md 9·14).

### 단계 0 — 디버깅 기반 마련 (1주차: 06.18~06.24)
"모델을 바꾸려면 먼저 바꿀 수 있게 만들고, 비교할 수 있게 만든다."

- [ ] **리포트 모델/온도 설정화**: [graph/llm.py:8-9](backend/app/services/graph/llm.py#L8-L9)의 하드코딩을 `config.py`로 분리(`REPORT_LLM_MODEL`, `REPORT_LLM_TEMPERATURE`). 챗봇과 동일한 패턴.
- [ ] **관측성(로깅) 강화**: 각 LLM 호출의 모델명, 토큰 사용량, 지연시간, 재작성 횟수, 게이트 실패 사유를 구조화 로그로 남긴다. → 이후 모든 단계의 "문제 식별" 근거.
- [ ] **평가 하네스 초안**: 고정 종목 셋에 대해 리포트/챗봇 응답을 저장하고 모델 간 비교(품질·비용·지연)를 표로 뽑는 스크립트. 실LLM 호출은 비용이 있으므로 소수 케이스로 한정.
- 산출물: 설정 분리 변경 기록, 로깅 가이드, 평가 스크립트.
- 검증: `cd backend; pytest` 관련 테스트, 로컬 1회 리포트 생성 로그 확인.

### 단계 1 — 챗봇 디버깅 & 모델 실험 (2~3주차: 06.25~07.08)
- [ ] `ENABLE_LLM_CHATBOT=true`로 켜고 **재현 가능한 문제 케이스 수집**(엉뚱한 종목 매칭, grounding 무시, 환각, 응답 지연/타임아웃 `CHATBOT_LLM_TIMEOUT_SECONDS=20`).
- [ ] 모델 후보 비교: 현행 `gpt-4o-mini` vs 상위 모델. **품질↑ 대비 지연/비용** 트레이드오프 표로 기록.
- [ ] 시스템 프롬프트/온도 외부화 검토([chat_llm.py](backend/app/services/chat_llm.py))로 프롬프트 튜닝을 코드 수정 없이.
- [ ] 규칙 기반 폴백 경로의 오분류도 함께 디버깅(정규식/키워드 intent).
- 산출물: 챗봇 디버깅 기록 + 모델 비교 표 + 챗봇 feature 문서 갱신.
- 검증: 케이스 셋 회귀 통과, 폴백 동작 확인.

### 단계 2 — 리포트 파이프라인 디버깅 (4~5주차: 07.09~07.22)
- [ ] **게이트 실패 패턴 분석**: 포맷/숫자(fact_checker)/정성(qualitative) 게이트가 어디서 자주 실패하고 재작성을 유발하는지 로그로 식별 → 프롬프트/검증 로직 보완.
- [ ] **재작성 루프 비용 진단**: `REPORT_MAX_REVISIONS=7`이 실제로 품질을 올리는지, 아니면 비용만 늘리는지 데이터로 판단 후 적정값 조정.
- [ ] 모델 교체 실험(단계 0의 설정화 활용): writer/evaluator 등 노드별로 모델을 다르게 쓰는 것이 효과적인지 검토(예: 합성·검증은 상위 모델, 단순 추출은 경량 모델).
- 산출물: 리포트 디버깅 기록, 게이트 개선 변경 기록, AI 리포트 feature 문서 갱신.
- 검증: 고정 종목 셋 리포트 재생성 후 품질/비용/재작성 횟수 비교.

### 단계 3 — 유료 API로 퀄리티 향상 (6~7주차: 07.23~08.05)
> 비용 발생 구간. 착수 전 예산 한도와 비용 가드를 먼저 정한다(AGENTS.md 9).

- [ ] **두 축 구분**: (a) LLM 모델 업그레이드(유료/상위 모델), (b) 데이터 소스 유료화(FMP/Finnhub/CoinGecko 등 무료 할당량 → 유료 플랜)로 데이터 신선도·범위 향상.
- [ ] 비용 가드 설정: 스케줄러 주기(`REPORT_SCHEDULER_INTERVAL_HOURS`), 실행당 최대(`MAX_REPORTS_PER_RUN`), 재작성 한도를 비용 상한에 맞춰 조정. 일일 호출/비용 추정 대시보드.
- [ ] **사용자/챗봇이 리포트를 실시간 생성하지 않는다는 원칙은 유지**(AGENTS.md 14). 유료화는 스케줄 생성 품질을 올리는 데만 쓴다.
- [ ] A/B: 무료 구성 vs 유료 구성 리포트를 같은 종목으로 비교해 "유료로 무엇이 좋아지는지" 근거 확보.
- 산출물: 유료 API 도입 결정 기록(비용/효과), 비용 가드 변경 기록.
- 검증: 비용 추정치 vs 실제, 품질 비교 표.

### 단계 4 — DB 마이그레이션 (8~9주차: 08.06~08.19)
> 위험 변경(데이터 이전). 백업 후 진행, 롤백 경로 확보(AGENTS.md 9).

- [ ] 대상 선정: 관리형 PostgreSQL(Neon/Render 등) vs **AWS RDS(PostgreSQL)**. UX 관점 기준 = 지연시간(지역/리전), 커넥션 풀, 가용성, 비용.
- [ ] **SDK 잠금이 없어 코드 변경 최소** — 핵심은 `DATABASE_URL` 교체. asyncpg connect args/풀 설정 점검([config.py:45-52](backend/app/core/config.py#L45-L52)).
- [ ] 마이그레이션 절차: Alembic으로 신규 DB 스키마 생성 → 기존 데이터 덤프/복원 → 스테이징에서 검증 → 컷오버.
- [ ] UX 지표 측정: 마이그레이션 전후 주요 API 응답시간(p50/p95) 비교.
- 산출물: 마이그레이션 계획·실행 기록, 전후 성능 비교, 롤백 절차 문서.
- 검증: 스테이징 회귀(`pytest`), 주요 화면 수동 점검, 성능 비교.

### 단계 5 — 안정화 · 회귀 · 최종 산출물 (10~11주차: 08.20~08.28)
- [ ] 전체 회귀(backend `pytest`, frontend `npm run lint`/`npm run build`).
- [ ] 방학 변경분 feature 문서/`feature-index.md`/`CODE_UNDERSTANDING.md` 최신화 점검.
- [ ] 최종 산출물(화면 캡처/리포트 샘플/비용·품질 비교표) 정리 — `최종산출물/`, [final-deliverables-plan-2026-06-15.md](docs/harness/final-deliverables-plan-2026-06-15.md) 연계.
- 산출물: 방학 회고 + 다음 학기 백로그.

## 3. 위험과 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| 모델 업그레이드/유료 API로 **비용 급증** | 예산 초과 | 단계 0 비용 로깅 → 단계 3 비용 가드(주기·건수·재작성 한도), 일일 상한 알림 |
| 모델 교체 후 **품질 회귀**(환각, 포맷 깨짐) | 신뢰도 저하 | 평가 하네스로 교체 전후 비교, 게이트 유지, 롤백 가능한 설정화 |
| **DB 마이그레이션 중 데이터 손실/다운타임** | 운영 중단 | 백업·스테이징 검증·컷오버 리허설·롤백 절차 선확보 |
| 챗봇 LLM 활성화 후 **grounding 이탈/환각** | 잘못된 투자정보 | grounding-only 원칙·게이트 유지, 케이스 회귀 |
| 사용자 요청이 리포트 실시간 생성을 유발 | 비용/원칙 위반 | AGENTS.md 14 준수, 저장 리포트 읽기만 유지 |

## 4. 측정 지표(KPI)

- 리포트: 평균 토큰/비용, 재작성 횟수, 게이트 통과율, 생성 지연.
- 챗봇: 의도 정확도(케이스 셋), 환각/grounding 이탈률, p95 응답시간, 타임아웃율.
- DB/UX: 주요 API p50/p95 응답시간(마이그레이션 전후), 에러율, 가용성.
- 비용: 일일/주간 OpenAI·외부 API 비용 추정 vs 실제.

## 5. 작업 규율(필수)

- 모든 구현/계획은 `docs/harness/`에 한국어 기록을 남긴다(AGENTS.md 12).
- 변경 시 해당 `docs/harness/features/*.md`와 `feature-index.md`를 갱신한다(AGENTS.md 13).
- 모델·유료 API·스케줄러·DB 변경은 위험 변경 프로토콜을 따른다(AGENTS.md 9): 위험·대상 파일·검증 계획을 먼저 적고 진행.
- 시크릿(`.env`, API 키, DB 비밀번호, JWT secret)은 출력·커밋하지 않는다(AGENTS.md 8).
