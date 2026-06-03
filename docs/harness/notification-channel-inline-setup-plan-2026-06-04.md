# 수신 동의 옆 Telegram chat_id·수신 이메일 설정 추가 계획

Date: 2026-06-04

## 목적 (Objective)

MyPage의 "수신 동의" 섹션에서 Telegram / Google Mail 수신 토글 **옆에** 각 채널의 연결 정보(Telegram chat_id, 수신 이메일)를 직접 설정·검증할 수 있게 한다. 현재는 토글만 있고 실제 채널 연결 UI가 라우팅되는 화면에 없어, 사용자가 수신 동의를 켜도 발송 대상(`destination`)을 입력할 곳이 없는 상태다.

사용자 결정에 따라:
- **검증 방식**: 기존 검증 코드 흐름을 그대로 재사용한다(백엔드/DB 변경 없음).
- **Telegram 식별자**: 숫자 `chat_id`를 직접 입력받는다(별도 봇 webhook/polling 운영 흐름 신설하지 않음).

## 현재 동작 / 목표 동작

### 현재 동작
- [MyPage.jsx](../../frontend/src/pages/MyPage.jsx#L274-L308) "수신 동의" 섹션: `telegram_enabled` / `email_enabled` 토글만 노출. `PUT /api/notifications/preferences`로 토글만 저장한다.
- 채널 연결 UI(코드 발급 → chat_id/이메일 입력 → 검증)는 [NotificationsSettings.jsx](../../frontend/src/pages/NotificationsSettings.jsx)에 존재하지만, [App.jsx:84-85](../../frontend/src/App.jsx#L84-L85)에서 `/mypage`와 `/settings/notifications` 모두 `MyPage`로 렌더링되어 **NotificationsSettings.jsx는 라우팅되지 않는 사장된(dead) 화면**이다.
- 결과적으로 라이브 화면에는 `chat_id`/이메일을 입력·검증할 경로가 없다. 백엔드 검증 엔드포인트(`telegram/connect`+`verify`, `email/verify`+`confirm`)와 검증 코드 흐름은 이미 동작한다.

### 목표 동작
- MyPage "수신 동의" 섹션에서 각 토글 옆/아래에 채널 연결 카드가 보인다.
  - **Telegram**: 현재 연결 상태(연결됨/미연결, 마스킹된 chat_id) 표시 → "코드 발급" 버튼(`POST /channels/telegram/connect`) → chat_id 입력 → "확인" 버튼(`POST /channels/telegram/verify`)으로 검증.
  - **Email**: 수신 이메일 입력(기본값은 Google 계정 이메일) → "코드 발급"(`POST /channels/email/verify`, Gmail로 코드 발송) → 코드 입력 → "확인"(`POST /channels/email/confirm`)으로 검증.
- 검증이 완료되어야 `destination`이 저장되고, 해당 토글이 켜져 있을 때만 발송 후보가 된다(기존 `_active_channels` 로직 유지).
- 채널을 해제(`DELETE /channels/telegram`, `DELETE /channels/email`)할 수 있는 버튼을 함께 제공한다.
- 검증 코드 흐름·발송 로직·스키마·DB는 **변경하지 않는다**. 순수 프론트엔드 통합 작업이다.

## 변경 대상 파일

### Frontend (주 변경)
- [frontend/src/pages/MyPage.jsx](../../frontend/src/pages/MyPage.jsx)
  - 채널 목록 로딩: `loadProfile`의 `Promise.all`에 `GET /api/notifications/channels` 추가, `channels` 상태 추가.
  - 채널 연결/검증/해제 핸들러 추가: `requestTelegramCode`, `verifyTelegram`, `requestEmailCode`, `confirmEmail`, `disconnectTelegram`, `disconnectEmail`. (대부분 NotificationsSettings.jsx의 기존 핸들러를 옮겨 재사용)
  - "수신 동의" 섹션 UI 확장: 토글 옆에 연결 상태 배지 + 입력 필드(코드, chat_id, 이메일) + 버튼. `lucide-react`의 `Smartphone`/`Send` 아이콘 추가 사용 가능.
  - `telegramCode`, `telegramChatId`, `emailCode`, `emailAddress` 로컬 상태 추가.

### Frontend (정리, 선택)
- [frontend/src/pages/NotificationsSettings.jsx](../../frontend/src/pages/NotificationsSettings.jsx)
  - 라우팅되지 않는 사장 코드. 채널 UI를 MyPage로 옮긴 뒤 **삭제 여부는 사용자 확인 후 결정**(아래 위험 항목 참조). 기본 계획은 "남겨두되 색인/문서에 dead 표기"이며, 삭제는 별도 승인 시 진행.

### Backend / DB / 설정
- **변경 없음.** 기존 엔드포인트·스키마(`TelegramVerifyRequest`, `EmailVerifyRequest`, `EmailConfirmRequest`, `NotificationChannelResponse`)·모델(`NotificationChannelConnection`)·검증 코드 서비스 로직을 그대로 사용한다.
- 단, 동작 검증을 위해 Telegram 발송에는 `TELEGRAM_BOT_TOKEN`, 이메일 코드 발송에는 `EMAIL_PROVIDER=gmail` + `GMAIL_*` 환경변수가 설정돼 있어야 한다(코드/문서에서 이름만 참조, 값은 다루지 않음).

## 단계별 구현 계획

1. **현황 재확인**: MyPage가 이미 `preferences`를 로드/저장하는 구조 확인 완료. 채널 상태는 아직 로드하지 않음 → `channels` 로딩 추가.
2. **상태/로더 추가**: `MyPage.jsx`에 `channels`, `telegramCode`, `telegramChatId`, `emailCode`, `emailAddress` 상태 추가. `loadProfile`에서 `GET /api/notifications/channels`를 병렬 호출해 `channels` 세팅. 채널 조회 실패가 프로필 로딩 전체를 막지 않도록 처리(개별 try/catch 또는 결과 기본값).
3. **핸들러 이식**: NotificationsSettings.jsx의 `requestTelegramCode`/`verifyTelegram`/`requestEmailCode`/`confirmEmail`을 MyPage로 옮기고, 각 성공 시 `loadProfile`(또는 채널만 재조회)로 상태 갱신. 채널 해제 핸들러 2개 추가.
4. **UI 구성**: "수신 동의" 섹션에서 각 토글 아래에 접이식/인라인 연결 카드 배치.
   - 연결됨이면 마스킹된 destination + "해제" 버튼.
   - 미연결이면 입력 필드 + "코드 발급"/"확인" 버튼.
   - Telegram chat_id 입력에는 "봇과 대화 후 받은 숫자 chat_id" 안내 문구 추가.
5. **상태 메시지 일원화**: 기존 `statusMessage`를 그대로 사용해 성공/실패 피드백 표시.
6. **검증 실행**: 아래 검증 계획대로 lint/build 수행.
7. **문서 동기화**: 변경 기록·기능 문서·색인 갱신(아래 "갱신할 문서").

## 위험과 Risky Change 여부 (AGENTS.md 섹션 9)

- **DB 스키마 변경 없음** → 마이그레이션 불필요.
- **인증/결제/스케줄러·리포트 비용 변경 없음** → 해당 Risky 항목 비해당.
- **AI 리포트 생성과 무관** → 사용자/챗봇 요청이 리포트를 생성하지 않는다는 규칙에 영향 없음.
- **개인정보 취급**: `chat_id`, 수신 이메일은 개인정보다(기능 문서 Change Rules). UI에 원문 노출을 최소화하고(마스킹 표시), 응답·로그에 그대로 찍지 않는다. 이메일 검증 코드는 기존대로 API 응답으로 노출하지 않고 Gmail로만 발송한다.
- **파일 삭제 = 사용자 확인 필요**: `NotificationsSettings.jsx` 삭제는 Risky(파일 삭제). 기본 계획은 **삭제하지 않고 보존**하며, 삭제를 원하면 별도 승인 후 진행한다.
- 종합적으로 이 작업의 **기본 범위(프론트엔드 인라인 통합)는 Risky Change가 아니다.** dead 파일 삭제만 승인 대상이다.

## 검증 계획 (AGENTS.md 섹션 6 — 최소 집합)

프론트엔드만 변경하므로:

```powershell
cd frontend
npm run lint
npm run build
```

- 백엔드 무변경이므로 백엔드 pytest는 원칙적으로 불필요. 다만 기존 알림 API 회귀가 걱정되면 확인용으로:
  ```powershell
  cd backend
  python -m pytest tests/test_notifications_api.py
  ```
- 수동 확인(서버 기동 시): `/mypage`에서 Telegram chat_id 입력→확인, 이메일 코드 발급→확인 흐름이 채널 상태를 "연결됨"으로 갱신하는지. (실제 발송은 `TELEGRAM_BOT_TOKEN`/`GMAIL_*` 설정 필요)

## 갱신할 문서

- **변경 기록**: 구현 완료 시 `docs/harness/notification-channel-inline-setup-implementation-2026-06-04.md` 작성(목적·변경 파일·동작 변화·검증·미실행 명령·후속 위험).
- **기능 문서**: [docs/harness/features/favorite-asset-notifications.md](features/favorite-asset-notifications.md)
  - "MyPage Integration Note"를 갱신: 수신 동의 토글뿐 아니라 chat_id/이메일 연결·검증 UI가 MyPage에 통합되었고, `/settings/notifications`는 동일 화면을 렌더링한다는 점, NotificationsSettings.jsx는 사장 코드라는 점 명시.
  - "Change Records"에 위 구현 기록 링크 추가.
  - 필요 시 Ownership Map에 `frontend/src/pages/MyPage.jsx`가 채널 연결 UI 소유라는 점 보강.
- **색인**: [docs/harness/feature-index.md](feature-index.md)
  - "Favorite asset notifications" 행의 Change records에 본 계획서와 구현 기록 링크 추가.
  - 본 계획서를 상단 목록(변경 기록 리스트)에 한 줄 추가.
- 폴더 소유권 변화는 없으므로 `DEVELOPMENT_DIRECTION.md`는 갱신 불필요.

## 후속/오픈 이슈

- Telegram `chat_id`를 사용자가 직접 알아내야 하는 UX 부담(봇과 1회 대화 필요). 추후 username→chat_id 자동 해석(webhook/polling)을 원하면 별도 작업으로 분리.
- 사장된 NotificationsSettings.jsx 삭제 여부는 사용자 승인 대기.
