# 수동 구독 부여 스크립트 (manual subscription grant)

Date: 2026-06-03

## 목적

결제 웹훅 흐름을 거치지 않고, 운영자가 **특정 계정에 직접 Plus/Pro 등급을 부여(또는 회수)** 할 수 있는 관리용 일회성 스크립트를 추가했다. 베타 테스터, 내부 계정, 환불/보상 대응 등 결제 없이 권한을 즉시 부여해야 하는 경우에 사용한다.

기존에는 구독 행을 만드는 경로가 결제 웹훅(`POST /api/billing/webhook` → `process_webhook_event`)뿐이라, 결제 없이 특정 계정에 권한을 줄 방법이 없었다.

## 변경 파일

- `backend/scripts/grant_subscription.py` (신규)

## 동작 변화

- `subscriptions` 테이블에 `provider="manual"`, `provider_subscription_id="manual_<user_id>"` 인 구독 행을 생성하거나 갱신한다.
  - `(provider, provider_subscription_id)` 유니크 제약을 활용해 사용자당 manual 구독 행은 1개로 유지된다.
- 부여 시: `tier=PLUS|PRO`, `status=ACTIVE`, `current_period_start=now`, `current_period_end=now+days`(또는 `--days` 미지정 시 `NULL`=만료 없음), `cancel_at_period_end=False`, `canceled_at/ended_at=None`.
- 회수(`--revoke`) 시: 해당 manual 구독을 `status=EXPIRED`, `ended_at=now` 로 만료 처리한다.
- 권한 판정 로직(`app/services/subscription_service.py`의 `has_active_paid_access`/`build_entitlements`)은 그대로이며, 이 스크립트가 만든 행도 동일하게 평가된다. 결제 provider 코드(`payment_service.py`)는 건드리지 않았다.
- 사용자/챗봇 요청이 AI 리포트를 생성하는 동작과는 무관하다(AGENTS.md 섹션 14 위반 없음). 단지 저장된 리포트/챗봇 접근 권한만 부여한다.

## 사용법

`backend/` 디렉터리에서 가상환경 파이썬으로 실행한다.

```powershell
# Pro 부여 (만료 없음)
.\.venv\Scripts\python.exe -m scripts.grant_subscription --email user@example.com --tier PRO

# Plus 부여 (30일 한정)
.\.venv\Scripts\python.exe -m scripts.grant_subscription --email user@example.com --tier PLUS --days 30

# 권한 회수
.\.venv\Scripts\python.exe -m scripts.grant_subscription --email user@example.com --revoke
```

## 검증

- `python -m scripts.grant_subscription --help` 실행으로 import 및 CLI 파싱 정상 동작 확인.
- DB에 직접 행을 쓰는 실제 부여/회수 실행은 미수행(운영 DB 보호 및 명시적 사용자 승인 필요). 실제 계정 대상 실행 시 PostgreSQL이 기동 중이어야 한다.

## 후속 위험 / 참고

- 이 스크립트는 인증·권한 검증이 없는 운영자 직접 실행 도구다. DB 접근 권한이 있는 사람만 사용해야 한다.
- manual 구독은 결제 provider와 무관하므로, `POST /api/billing/cancel`(provider-backed 구독 대상)로는 취소되지 않는다. 회수는 `--revoke`로 한다.
- `--days` 기반 만료는 자동 갱신되지 않는다. 기간이 지나면 자동으로 Free로 떨어진다(`normalize_subscription_snapshot` 동작).
- 반복적·정식 운영이 필요해지면 admin 권한 + 보호된 grant 엔드포인트로 승격하는 것을 검토한다.
