# 정기요약 알림 링크 localhost → 실제 주소 전환 계획

Date: 2026-06-10

## Objective

정기요약(scheduled digest) 메일·Telegram 메시지에 포함되는 자산 상세 페이지 링크가 `http://localhost:5173/detail/...` 로컬 개발 주소로 발송되는 문제를 해결한다. 운영 환경에서 이용자가 실제로 접속 가능한 프론트엔드 공개 주소(Vercel origin)를 링크로 받도록 한다. 메일과 Telegram 두 채널 모두 동일하게 적용한다. 이 문서는 계획서이며 코드는 아직 수정하지 않는다.

관련 기능 문서: `docs/harness/features/favorite-asset-notifications.md`

## 코드 기준 현재 동작 (확인 결과)

코드를 직접 확인한 결과는 다음과 같다. **문서보다 코드를 기준으로 한다.**

- 모든 알림 본문의 상세 링크는 단일 helper [`_build_asset_detail_url(ticker)`](backend/app/services/notification_service.py#L161-L163)를 거친다.
  - 구현: `return f"{settings.FRONTEND_BASE_URL}/detail/{safe_ticker}"`
- 이 helper를 사용하는 경로:
  - 가격 변동 알림 ([notification_service.py:833](backend/app/services/notification_service.py#L833))
  - 뉴스 알림 ([notification_service.py:885](backend/app/services/notification_service.py#L885))
  - 정기요약(digest) — [`_digest_asset_payload`](backend/app/services/notification_service.py#L285) 에서 `detail_url`을 만들고 [`_build_digest_notification_body`](backend/app/services/notification_service.py#L314) 에서 본문에 `상세 페이지: {detail_url}` / `Detail page: {detail_url}` 로 삽입.
- [`FRONTEND_BASE_URL`](backend/app/core/config.py#L177) 기본값은 `"http://localhost:5173"` 이고, validator [`normalize_frontend_base_url`](backend/app/core/config.py#L302-L305)는 공백/trailing slash만 정리한다. 즉 환경변수로 덮어쓰지 않으면 항상 localhost가 들어간다.
- [`ENVIRONMENT`](backend/app/core/config.py#L75) 기본값은 `"development"`.

### 기존 remediation 문서와 코드 불일치 (중요)

스테이징된 두 문서:

- `docs/harness/notification-public-link-remediation-plan-2026-06-10.md`
- `docs/harness/notification-public-link-remediation-implementation-2026-06-10.md`

는 새 설정 `FRONTEND_PUBLIC_BASE_URL`과 helper `_frontend_base_url()` / `_normalize_message_links()` / `_append_asset_detail_link()` 등을 추가했다고 기록하지만, **현재 코드에는 해당 설정과 함수가 존재하지 않는다.** (`config.py`에 `FRONTEND_PUBLIC_BASE_URL` 없음, `notification_service.py`에 `_normalize_message_links` 등 없음.) 구현 기록이 실제 코드에 반영되지 않았으므로, 이번 작업은 **이미 코드에 배선되어 있는 `FRONTEND_BASE_URL`을 기준**으로 진행하고 위 두 문서를 정정/대체한다.

## 근본 원인

운영 backend 호스트(Render)에 환경변수 `FRONTEND_BASE_URL`이 실제 프론트엔드 공개 origin으로 설정되어 있지 않아, 코드 기본값 `http://localhost:5173`이 그대로 모든 알림 링크(정기요약 포함)에 들어간다. 코드 결함이라기보다 **배포 설정 누락**이 1차 원인이며, 운영에서 localhost가 새어나가지 않도록 막는 방어 계층이 없다는 점이 2차 원인이다.

## 목표 동작

- 운영/배포 환경의 모든 알림(특히 정기요약) 링크가 `https://<frontend-origin>/detail/<ticker>` 형태가 된다. 메일·Telegram 동일.
- 로컬 개발 환경에서는 기존처럼 `http://localhost:5173`를 그대로 사용해 개발 흐름을 깨지 않는다.
- 운영 환경에서 `FRONTEND_BASE_URL`이 여전히 localhost로 남아 있으면, 조용히 localhost 링크를 보내지 않고 경고 로그를 남긴다.
- 이미 DB에 저장되어 발송 대기 중인 pending 이벤트 본문에 localhost 링크가 있으면, 발송 직전에 실제 origin으로 보정한다.
- 외부 뉴스 링크(`https://news...`)와 backend API URL은 절대 치환하지 않는다.

## 변경 대상

### 1. 배포 설정 (1차, 코드 변경 아님 — 핵심)

- 운영 backend 호스트 환경변수에 `FRONTEND_BASE_URL=https://<vercel-frontend-origin>` 추가/수정.
- 이 값만 정확히 설정되면 코드 변경 없이도 신규 정기요약 링크는 즉시 실제 주소로 발송된다.
- `FRONTEND_BASE_URL`은 backend가 사용자에게 보여줄 **프론트엔드 origin**이고, `VITE_API_BASE_URL`은 frontend가 호출할 **backend origin**이다. 두 값을 혼동하지 않는다.
- 실제 origin 값은 문서/로그에 반복 노출하지 않는다(secret은 아니나 환경별 운영 정보).

### 2. 백엔드 코드 (2차, 방어 계층)

- `backend/app/services/notification_service.py`
  - 발송 직전 보정 helper 추가(예: `_normalize_app_links(body: str) -> str`): 본문 내 `http://localhost:5173` 및 `http://127.0.0.1:5173`로 시작하는 **앱 내부 링크만** `FRONTEND_BASE_URL`로 치환. 단, `FRONTEND_BASE_URL` 자체가 localhost가 아닐 때만 치환.
  - [`_send_telegram`](backend/app/services/notification_service.py#L970)와 [`_send_email`](backend/app/services/notification_service.py#L1020)의 공통 직전 단계(또는 [`send_pending_notifications`](backend/app/services/notification_service.py#L912) 루프 내 본문 사용 지점)에서 위 helper를 적용.
  - 선택: [`_build_asset_detail_url`](backend/app/services/notification_service.py#L161-L163)에 운영 환경 가드 추가 — `ENVIRONMENT != "development"`인데 `FRONTEND_BASE_URL`이 localhost면 `logger.warning`으로 한 번 경고.

### 3. 설정 파일 / 가이드 문서

- `.env.example`, `ENVIRONMENT_VARIABLE_SETUP.md`에 `FRONTEND_BASE_URL`의 운영 설정 의미를 명확히 보강(이미 정기요약 구현 때 추가됐는지 확인 후 정정).

### 4. 테스트

- `backend/tests/test_notification_service.py`
  - `FRONTEND_BASE_URL=https://app.example.com`일 때 정기요약 본문 링크가 `https://app.example.com/detail/NVDA`가 되는지.
  - 본문에 남은 `http://localhost:5173/detail/NVDA`가 발송 직전 보정으로 `https://app.example.com/detail/NVDA`로 치환되는지.
  - 외부 뉴스 링크는 치환되지 않는지.
  - `FRONTEND_BASE_URL`이 localhost일 때는 치환하지 않고(개발 환경 보존) 그대로 두는지.

## 단계별 구현 계획

1. (즉시) 운영 backend 호스트에 `FRONTEND_BASE_URL`을 실제 Vercel origin으로 설정하고 재배포 → 신규 정기요약부터 실제 링크 적용 확인.
2. `notification_service.py`에 발송 직전 링크 보정 helper를 추가하고 메일/Telegram 공통 경로에 연결.
3. 운영 환경 localhost 가드 경고 로그 추가(선택).
4. `test_notification_service.py`에 위 케이스 추가 후 backend 테스트 실행.
5. 기존 불일치 문서(`notification-public-link-remediation-*-2026-06-10.md`) 정정: `FRONTEND_PUBLIC_BASE_URL`이 아니라 `FRONTEND_BASE_URL`을 기준으로 한다는 점을 명시하거나, 이번 구현 기록으로 대체.
6. feature 문서·index 갱신.

## 위험과 Risky Change 여부

- DB 스키마 변경 없음, 인증 변경 없음, 스케줄러 주기/AI 리포트 비용 변경 없음, 파일 삭제 없음 → **AGENTS.md 섹션 9의 Risky Change에 해당하지 않음.**
- 1차 조치는 배포 환경변수 설정으로 코드 영향 없음.
- 발송 직전 치환은 앱 내부 localhost 링크로 대상을 한정하므로 외부 링크 오치환 위험이 낮다. 단, 치환 정규식은 host prefix 단위로만 제한한다.
- 이미 sent 처리된 과거 메시지는 수정 불가(되돌릴 수 없음).
- AI 리포트 생성 규칙(AGENTS.md 섹션 14) 영향 없음: 알림 발송/정기요약은 저장된 데이터만 읽고 새 리포트를 생성하지 않는다.

## 검증 계획 (AGENTS.md 섹션 6, 최소 집합)

```powershell
cd backend
python -m pytest tests/test_notification_service.py tests/test_notifications_api.py
```

- 프론트엔드 코드는 변경하지 않으므로 `npm run lint`/`npm run build`는 필수 아님(설정 가이드 문구만 손대면 생략).
- 실제 Gmail/Telegram 외부 발송 smoke는 provider credential·외부 네트워크가 필요하므로 자동 검증 범위에서 제외하고, 운영 환경변수 설정 후 수동으로 1회 확인 권장.

## 갱신할 문서

- `docs/harness/features/favorite-asset-notifications.md` — `FRONTEND_BASE_URL` 운영 의미와 발송 직전 링크 보정 동작, Change Records 링크 추가.
- `docs/harness/features/deployment-runtime.md` — `FRONTEND_BASE_URL` 운영 등록 항목 명시.
- `docs/harness/feature-index.md` — 이 계획서 및 후속 구현 기록 항목 추가.
- 기존 `docs/harness/notification-public-link-remediation-plan-2026-06-10.md` / `...-implementation-2026-06-10.md` — 코드와 불일치(`FRONTEND_PUBLIC_BASE_URL` 미존재) 정정 또는 대체 명시.

## AI Report Generation Rule

이 계획은 알림 메시지의 링크 생성·발송 직전 본문 보정과 배포 환경변수만 다룬다. 사용자 요청, 챗봇 요청, 알림 평가/발송, 정기요약 발송은 새 AI 리포트 생성을 트리거하지 않으며 저장된 scheduled report와 market/news cache만 읽는다.
