# 이메일/텔레그램 알림 PLUS 이상 구독 제한 계획

Date: 2026-06-10

## 1. 목적 (Objective)

이메일(Gmail)·텔레그램 **외부 발송 알림**을 PLUS 이상(PLUS, PRO) 구독자만 사용할 수 있도록 제한한다. 앱 내부(in_app) 알림과 즐겨찾기 기능은 Free 사용자에게도 그대로 유지한다. 백엔드 권한 게이트(authoritative)와 프론트 잠금 UI(표시용)를 함께 구현해, Free 사용자는 채널 연결/수신 동의 토글이 잠긴 상태와 업그레이드 안내를 보고, 백엔드 API·스케줄러는 권한 없는 사용자의 외부 발송을 차단한다.

> 사용자 결정 사항(2026-06-10):
> - 제한 범위: **외부 발송(email/telegram)만** 제한, in_app은 Free 유지.
> - UI 처리: Free에게 **잠금 + 업그레이드 안내**, 백엔드도 403으로 차단.

## 2. 현재 동작 / 목표 동작

### 현재 동작
- 알림 채널 on/off는 결제 구독(`Subscription`)과 무관하게 **사용자 단위**(`NotificationPreference`)로 관리된다. (분석: 이번 세션 선행 분석)
- `backend/app/api/notifications.py`의 모든 엔드포인트는 `get_current_user`만 의존하고 구독 등급을 확인하지 않는다. 즉 Free 사용자도 텔레그램/이메일 채널을 연결·검증하고 `telegram_enabled`/`email_enabled`를 켤 수 있다.
- 정시 digest 스케줄러(`create_scheduled_digest_notifications`)와 변화 감지 평가(`evaluate_notifications`)는 사용자별 `_active_channels()` 결과(검증·동의된 telegram/email + 기본 in_app)를 그대로 사용해 외부 발송 이벤트를 만든다. 구독 등급 필터링이 없다.
- 권한 게이트는 현재 리포트(`require_report_access`, PLUS+)·챗봇(`require_chatbot_access`, PRO)에만 존재한다(`backend/app/api/deps.py`).
- 엔타이틀먼트 모델(`SubscriptionEntitlements`)에는 `can_view_reports`, `can_use_chatbot`만 있다. PLUS·PRO는 `can_view_reports=True`, Free는 `False`이다.

### 목표 동작
- 엔타이틀먼트에 `can_use_notifications`(= tier ∈ {PLUS, PRO}) 개념을 추가하고, 외부 발송 알림 권한의 단일 판단 기준으로 삼는다.
- 백엔드 알림 API에서 **외부 발송 관련 작업**(채널 연결/검증, telegram/email 수신 동의 ON, 테스트 발송)은 PLUS 이상만 허용하고, 권한이 없으면 `403`을 반환한다. in_app 관련 토글(price_change/news/report/daily_digest 등 알림 타입 설정)과 채널 조회/이력 조회는 Free도 허용한다.
- 스케줄러의 발송 채널 산출 단일 지점(`_active_channels`)에서 PLUS 미만 사용자의 telegram/email 채널을 제거해, 권한 없는 사용자에게는 외부 발송 이벤트가 생성되지 않게 한다(in_app은 유지). 이는 digest·evaluate·test 경로 모두에 자동 적용된다.
- 프론트 `MyPage.jsx`의 "수신 동의" 섹션에서 Free 사용자는 telegram/email 토글과 채널 연결 인라인 UI가 잠긴 상태로 보이고, "PLUS 이상에서 사용 가능" 안내와 Pricing 링크가 표시된다. PLUS+는 기존과 동일하게 동작한다.
- 구독 만료/다운그레이드 시 채널 연결 레코드는 삭제하지 않고(되돌릴 수 있는 변경 회피), 발송 시점 권한 체크로 외부 발송만 자동 중단된다.

## 3. 변경 대상 파일

### Backend
- `backend/app/services/subscription_service.py` — `SubscriptionEntitlements`에 `can_use_notifications` 필드 추가, `build_entitlements`에서 tier ∈ {PLUS, PRO}일 때 True로 설정.
- `backend/app/schemas.py` — 엔타이틀먼트 응답 스키마(`/api/billing/me`에서 쓰는 entitlements)에 `can_use_notifications` 추가(프론트 노출용).
- `backend/app/api/deps.py` — `require_notification_access` 의존성 추가(엔타이틀먼트의 `can_use_notifications` 미충족 시 403).
- `backend/app/api/notifications.py` — 외부 발송 관련 엔드포인트에 `require_notification_access` 적용:
  - `POST /channels/telegram/connect`, `POST /channels/telegram/verify`
  - `POST /channels/email/verify`, `POST /channels/email/confirm`
  - `POST /test`
  - `PUT /preferences` — `telegram_enabled` 또는 `email_enabled`를 **True로 변경하는 경우**에만 권한 검사(다른 토글/끄기는 허용). 라우터 핸들러 내부에서 payload를 보고 조건부 검사.
- `backend/app/services/notification_service.py` — `_active_channels()`에서 user_id 기준 엔타이틀먼트를 조회해, `can_use_notifications`가 False면 telegram/email을 결과에서 제외(in_app 유지). `get_user_subscription`/`build_entitlements`를 user_id로 호출(별도 User 객체 없이 가능).

### Frontend
- `frontend/src/pages/MyPage.jsx` — "수신 동의" 섹션에서 `useSubscriptionStore`의 `entitlements.can_use_notifications`(또는 `tier`)를 읽어:
  - Free: telegram/email 토글·채널 연결/검증 인라인 UI를 비활성화(disabled)하고 "PLUS 이상에서 사용 가능" 배지 + Pricing(`/pricing`) 링크 표시.
  - PLUS+: 기존 동작 유지.
  - in_app 관련 알림 타입 토글(price_change/news/report/daily_digest)은 모든 등급에서 활성 유지.
- `frontend/src/store/subscriptionStore.js` — `defaultEntitlements`에 `can_use_notifications: false` 추가(백엔드 응답 미존재 시 안전 기본값).

### DB / 설정
- **DB 스키마 변경 없음.** 엔타이틀먼트는 기존 `Subscription` 행에서 파생되는 계산값이며 새 컬럼/마이그레이션이 필요하지 않다.
- 환경변수 추가/변경 없음.

## 4. 단계별 구현 계획

1. **엔타이틀먼트 확장**: `subscription_service.py`의 `SubscriptionEntitlements`에 `can_use_notifications: bool` 추가. `build_entitlements`에서 유료 접근(`has_active_paid_access`)이고 tier ∈ {PLUS, PRO}이면 True, 그 외 False. Free 분기에서도 False로 명시.
2. **스키마 노출**: `schemas.py`의 entitlements 응답 모델에 `can_use_notifications` 추가. `/api/billing/me` 응답 빌더가 새 필드를 채우는지 확인(엔타이틀먼트 dataclass → 스키마 매핑 지점 점검).
3. **권한 의존성**: `deps.py`에 `require_notification_access` 추가(`require_report_access` 패턴 복제, 메시지: "Email/Telegram notifications require an active Plus or Pro subscription.").
4. **API 게이트 적용**: `notifications.py`의 채널 연결/검증 4종과 `/test`에 의존성 추가. `PUT /preferences`는 핸들러 안에서 payload에 `telegram_enabled=True` 또는 `email_enabled=True`가 포함될 때만 엔타이틀먼트를 검사(미충족 시 403). 끄기/그 외 토글은 통과.
5. **발송 단일 지점 게이트**: `notification_service.py` `_active_channels()`에 엔타이틀먼트 조회 추가. `can_use_notifications`가 False면 반환 리스트에서 `telegram`,`email` 제외. (digest/evaluate/test가 모두 이 함수를 경유하므로 누락 없이 적용됨.)
6. **프론트 잠금 UI**: `MyPage.jsx` 수신 동의 섹션에 등급 분기 추가. `subscriptionStore.js` 기본값 보강.
7. **테스트 추가/갱신**: 아래 검증 계획 참조.

## 5. 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **DB 스키마 변경**: 없음 → Risky Change 아님.
- **인증/비밀번호 동작 변경**: 없음(권한 게이트만 추가, 인증 흐름 불변).
- **스케줄러 빈도/리포트 비용 변경**: 없음. 오히려 권한 없는 사용자 외부 발송을 줄이므로 provider quota 부담은 감소.
- **파일 삭제/DB 드롭**: 없음. 구독 만료 시에도 채널 연결 레코드는 보존(되돌릴 수 없는 변경 회피).
- **종합 판정**: AGENTS.md 섹션 9의 사용자 사전 승인 대상(스키마 마이그레이션·인증 변경·비용 증가·삭제)에 **해당하지 않음**. 권한 정책 추가는 동작 변화이므로 변경 기록·기능 문서로 문서화한다.
- **잔여 위험**:
  - 기존에 이미 telegram/email을 켜둔 Free 사용자가 존재하면, 본 변경 이후 외부 발송이 조용히 중단된다. `_active_channels`에서 차단되므로 데이터 정합성 문제는 없으나, 사용자 입장에서는 "알림이 안 온다"로 인지될 수 있다. → 프론트 잠금 UI의 업그레이드 안내로 의도를 명확히 전달.
  - `PUT /preferences`의 조건부 게이트 로직이 누락되면 Free가 토글만 켜고 발송은 막히는 불일치가 생길 수 있어, API와 발송 지점 양쪽을 함께 검증한다.

## 6. 검증 계획 (AGENTS.md 섹션 6 — 최소 검증 세트)

Cross-stack 변경이므로 백엔드 테스트와 프론트 빌드를 함께 수행한다.

### Backend (`cd backend`)
- 신규/갱신 테스트:
  - `tests/test_notifications_api.py` — Free 사용자가 채널 연결/검증·`/test`·telegram/email ON 시 403, in_app 토글은 200.
  - `tests/test_notification_service.py` — `_active_channels`가 Free에는 telegram/email을 제외하고 in_app만, PLUS+에는 검증된 채널을 포함하는지.
  - 엔타이틀먼트 테스트(기존 subscription 테스트 위치) — Free/PLUS/PRO/만료/취소 상태별 `can_use_notifications` 값.
- 실행: `python -m pytest tests/test_notifications_api.py tests/test_notification_service.py`
- 엔타이틀먼트 단위 테스트가 별도 파일이면 함께 실행.

### Frontend (`cd frontend`)
- `npm run lint`
- `npm run build`
- 수동 스모크(가능 시): Free 계정에서 수신 동의 섹션 잠금/안내 노출, PLUS+ 계정에서 기존 동작 유지.

### 미실행 예상 / 주의
- 실제 Gmail/Telegram 외부 발송은 테스트에서 호출하지 않는다(AGENTS.md 섹션 4, mock/격리 우선).
- DB가 필요한 테스트는 PostgreSQL 기동 후 실행(`docker compose up -d db`).

## 7. 갱신할 문서

- **기능 문서**:
  - `docs/harness/features/favorite-asset-notifications.md` — Change Rules/Current Behavior에 "외부 발송(email/telegram)은 PLUS 이상 전용, in_app은 Free 유지" 정책 추가, Change Records에 본 계획 및 후속 구현 기록 링크.
  - `docs/harness/features/subscription-billing.md` — 엔타이틀먼트 표/Contracts에 `can_use_notifications`(PLUS+ 외부 알림 발송) 추가, Change Records 링크.
- **색인**: `docs/harness/feature-index.md` — 본 계획 문서와 후속 구현 기록을 항목으로 추가하고, 두 기능(`favorite-asset-notifications`, `subscription-billing`)의 Change records 열에 연결.
- **구현 단계 산출물**: 구현 시 `docs/harness/notification-external-delivery-plus-tier-gate-implementation-2026-06-10.md` 변경 기록을 작성(`/harness-implement`).
- **코드 이해 문서**: 라우트/서비스 권한 경계가 바뀌므로 필요 시 루트 `CODE_UNDERSTANDING.md`의 알림/구독 절을 갱신(해당 문서 8절 규칙 준수).

## 8. 요약

엔타이틀먼트에 `can_use_notifications`(PLUS+)를 추가하고, ① 알림 API의 외부 발송 엔드포인트와 telegram/email ON 토글에 `require_notification_access` 게이트, ② 발송 채널 단일 지점 `_active_channels`에서 권한 없는 사용자 telegram/email 제외, ③ 프론트 `MyPage.jsx` 수신 동의 섹션 잠금+업그레이드 안내를 구현한다. DB 스키마·인증·스케줄러 비용 변경이 없어 AGENTS.md 섹션 9의 사전 승인 대상이 아니며, 백엔드 pytest + 프론트 lint/build로 검증한다.
