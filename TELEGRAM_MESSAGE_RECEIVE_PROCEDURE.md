# Telegram 메시지 수신 절차

Date: 2026-06-09

이 문서는 Project Finance에서 Telegram 알림을 실제로 받기 위한 운영자/사용자 절차다. 현재 구현은 Telegram webhook 자동 연결이 아니라 **숫자 `chat_id`를 직접 입력하는 수동 연결 방식**이다.

## 현재 방식 요약

- 백엔드는 Telegram Bot API `sendMessage`로 메시지를 보낸다.
- 사용자는 Telegram bot과 먼저 대화해야 한다.
- 앱은 Telegram에서 들어오는 `/start <code>` 메시지를 자동으로 받지 않는다.
- 따라서 사용자는 bot과 대화한 뒤 자신의 숫자 `chat_id`를 확인하고, 앱 `/mypage`에서 연결 코드와 함께 직접 입력해야 한다.

## 1. 운영자 준비

1. Telegram에서 `@BotFather`를 연다.
2. `/newbot`으로 Project Finance 알림용 bot을 만든다.
3. BotFather가 발급한 bot token을 백엔드 환경변수 `TELEGRAM_BOT_TOKEN`에 저장한다.
4. 백엔드를 재시작한다.
5. 자동 알림 scheduler까지 켤 경우에만 `ENABLE_SCHEDULER=true`, `ENABLE_NOTIFICATION_SCHEDULER=true`를 설정한다.

주의:

- `TELEGRAM_BOT_TOKEN`은 backend-only secret이다.
- token 값을 프론트엔드, Git, 문서, 이슈, 채팅에 남기지 않는다.
- `TELEGRAM_WEBHOOK_SECRET`은 현재 수동 `chat_id` 방식의 발송 경로에서는 사용하지 않는다.

## 2. 사용자가 bot과 대화 시작

1. Telegram 앱에서 운영자가 만든 bot username을 검색한다.
2. bot 대화방을 연다.
3. `/start` 또는 아무 메시지 1개를 보낸다.
4. 이 단계를 끝내야 bot이 해당 사용자에게 메시지를 보낼 수 있다.

## 3. 숫자 chat_id 확인

bot token을 가진 운영자 또는 로컬 개발자가 확인한다. token과 `chat_id` 원문은 외부에 공유하지 않는다.

PowerShell 예시:

```powershell
$telegramToken = Read-Host "Telegram bot token"
$updates = Invoke-RestMethod -Uri "https://api.telegram.org/bot$telegramToken/getUpdates"
$updates.result | Select-Object -Last 5 | ConvertTo-Json -Depth 8
Remove-Variable telegramToken
```

출력에서 최근 메시지의 아래 값을 찾는다.

```text
message.chat.id
```

개인 대화는 보통 양수 숫자이고, 그룹/슈퍼그룹은 음수일 수 있다. 앱은 양수와 음수 숫자 `chat_id`를 모두 허용한다.

문제가 있으면:

- `result`가 비어 있으면 사용자가 bot에게 메시지를 보냈는지 다시 확인한다.
- 같은 bot token을 사용했는지 확인한다.
- token 또는 `chat_id`를 문서/로그/채팅에 붙여넣지 않는다.

## 4. 앱에서 Telegram 채널 연결

1. Project Finance에 로그인한다.
2. `/mypage`로 이동한다.
3. "수신 동의" 영역의 Telegram 섹션에서 `코드 발급`을 누른다.
4. 화면의 연결 코드가 자동 입력되지 않으면 연결 코드 칸에 입력한다.
5. `숫자 chat_id` 칸에 3단계에서 확인한 값을 입력한다.
6. `확인`을 누른다.
7. "Telegram 채널을 연결했습니다." 상태를 확인한다.
8. Telegram 수신 토글을 켠다.

연결이 완료되어도 수신 토글이 꺼져 있으면 Telegram 외부 발송 이벤트가 생성되지 않는다.

## 5. 테스트 메시지 받기

테스트 메시지는 "채널 연결이 실제로 끝났는지"와 "Telegram Bot API 발송이 성공하는지"를 한 번에 확인하는 절차다. 운영 알림 scheduler가 꺼져 있어도 `POST /api/notifications/test`는 즉시 pending 이벤트를 만들고 발송 처리를 시도한다.

### 5.1 테스트 전 체크리스트

테스트를 보내기 전에 아래 5개가 모두 맞아야 한다.

1. 백엔드가 재시작된 뒤 `TELEGRAM_BOT_TOKEN`을 읽고 있다.
2. 사용자가 Telegram bot과 먼저 대화했다.
3. `/mypage`에서 Telegram 채널이 "연결됨" 상태다.
4. `/mypage`에서 Telegram 수신 토글이 켜져 있다.
5. 테스트 API를 호출하는 사용자가 4번의 채널을 연결한 동일 로그인 사용자다.

`chat_id`를 잘못 입력했거나 다른 사용자 계정으로 테스트 API를 호출하면 이벤트가 생성되지 않거나, 발송 대상이 없어 실패할 수 있다.

### 5.2 앱 화면에서 보내는 방법

현재 라이브 화면은 `/mypage`의 Telegram 연결/수신 동의 흐름이다. 테스트 발송 버튼이 화면에 노출된 환경에서는 다음 순서로 확인한다.

1. Project Finance에 로그인한다.
2. `/mypage`에서 Telegram 채널이 연결됨으로 보이는지 확인한다.
3. Telegram 수신 토글을 켠다.
4. 테스트 알림 버튼 또는 테스트 발송 UI가 있으면 누른다.
5. Telegram 앱에서 `TEST 테스트 알림` 제목의 메시지가 도착하는지 확인한다.

테스트 발송 UI가 보이지 않으면 5.3의 API 호출 방식으로 확인한다.

### 5.3 API로 직접 보내는 방법

인증된 사용자 세션으로 아래 API를 호출한다. 실제 호출에는 로그인 사용자의 `Authorization: Bearer <access_token>` 헤더가 필요하다. `<backend-url>`과 `<access_token>`은 로컬/운영 환경에 맞게 바꾸되, token 원문을 문서나 이슈에 남기지 않는다.

이 프로젝트의 `<access_token>`은 Google ID token이 아니다. 프론트엔드가 `POST /api/auth/google` 응답으로 받은 Project Finance 앱 JWT이며, 로그인 후 브라우저 `localStorage`의 `token` 키에 저장된다.

브라우저에서 토큰을 가져오는 방법:

1. Project Finance 웹앱에 Google로 로그인한다.
2. 개발자도구를 연다.
3. Console에서 아래 명령을 실행한다.

```javascript
localStorage.getItem("token")
```

4. 출력된 문자열을 PowerShell의 `$accessToken`에 넣는다.

PowerShell에서 직접 붙여넣을 때는 아래처럼 입력한다. 입력한 token은 화면에 남을 수 있으므로 공유하지 않는다.

```powershell
$accessToken = Read-Host "Project Finance access token"
```

```http
POST <backend-url>/api/notifications/test
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "ticker": "TEST",
  "message": "Telegram 알림 수신 테스트입니다."
}
```

PowerShell 예시:

```powershell
$backendUrl = "http://127.0.0.1:8000"
$accessToken = Read-Host "Project Finance access token"
$body = @{
  ticker = "TEST"
  message = "Telegram 알림 수신 테스트입니다."
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$backendUrl/api/notifications/test" `
  -Headers @{ Authorization = "Bearer $accessToken" } `
  -ContentType "application/json" `
  -Body $body

Remove-Variable accessToken
```

정상 응답 예시는 아래 형태다. 숫자는 사용자 상태에 따라 달라질 수 있다.

```json
{
  "created_events": 2,
  "sent_events": 1,
  "failed_events": 0,
  "message": "Test notification processing completed.",
  "delivery_status": {
    "telegram": {
      "configured": true,
      "missing_keys": [],
      "verification_mode": "manual_chat_id"
    }
  }
}
```

응답 해석:

- `delivery_status.telegram.configured=true`: 백엔드가 `TELEGRAM_BOT_TOKEN`을 읽고 있다.
- `delivery_status.telegram.missing_keys=[]`: Telegram 발송에 필요한 env 누락이 없다.
- `created_events`가 0: 현재 사용자에게 활성 채널이 없거나 동일 dedupe 조건으로 이벤트가 이미 생성됐을 수 있다. Telegram 연결/토글 상태를 먼저 확인한다.
- `sent_events`가 1 이상: 이번 호출에서 Telegram 또는 email 같은 외부 채널 발송이 성공했다.
- `failed_events`가 1 이상: `/api/notifications/history`에서 실패 이벤트의 `error_message`를 확인한다.

`401 Unauthorized`가 나오면:

- `$accessToken`이 비어 있거나 잘못된 값이다.
- Google ID token을 넣은 경우다. 반드시 `localStorage.getItem("token")`의 Project Finance 앱 JWT를 사용한다.
- 다른 백엔드 인스턴스에서 발급한 token을 현재 `$backendUrl`에 보낸 경우다. 로컬 백엔드로 테스트하면 로컬 프론트에서 다시 로그인해 새 token을 받는다.
- token이 만료됐을 수 있다. 로그아웃 후 다시 로그인하고 `localStorage.getItem("token")`을 다시 복사한다.
- `Bearer`와 token 사이에 공백이 있어야 한다. 문서의 PowerShell 예시는 `Authorization = "Bearer $accessToken"` 형태다.

PowerShell에서 token이 비어 있는지 확인할 때는 원문을 출력하지 말고 길이만 확인한다.

```powershell
$accessToken.Length
```

0이거나 오류가 나면 `$accessToken`이 설정되지 않은 상태다.

### 5.4 Telegram 앱에서 확인할 메시지

Telegram에는 아래처럼 제목과 본문이 줄바꿈되어 도착한다.

```text
TEST 테스트 알림

Telegram 알림 수신 테스트입니다.
```

메시지가 몇 초 안에 오지 않으면 Telegram 앱에서 bot 대화방을 직접 열어 새 메시지가 있는지 확인한다. 모바일 push 알림은 기기 알림 설정 때문에 늦거나 숨겨질 수 있으므로, 최종 성공 기준은 push 배너가 아니라 bot 대화방에 메시지가 도착했는지 여부다.

### 5.5 History로 재확인

테스트 후에는 알림 이력 API로 서버가 기록한 상태를 확인할 수 있다.

```http
GET <backend-url>/api/notifications/history?limit=10
Authorization: Bearer <access_token>
```

확인할 값:

- `channel`: `telegram`
- `event_type`: `test`
- `ticker`: `TEST`
- `status`: 성공 시 `sent`, 실패 시 `pending` 또는 `failed`
- `error_message`: 실패 원인. token 값이나 secret 값은 노출하지 않고 provider 오류 요약만 남아야 한다.

### 5.6 성공 기준

- Telegram 앱에서 테스트 메시지를 받는다.
- API 응답의 `delivery_status.telegram.configured`가 `true`이다.
- `sent_events`가 1 이상이거나, `/api/notifications/history`에서 Telegram 이벤트 상태가 `sent`이다.

위 세 조건 중 Telegram 앱 수신이 최종 기준이다. API는 `sent`인데 앱에서 보이지 않으면 다른 Telegram 계정의 `chat_id`를 연결했거나, 그룹/개인 채팅을 혼동했을 가능성이 높다.

## 6. 실패 시 확인 순서

1. `401 Unauthorized`이면 Telegram 문제가 아니라 앱 JWT 인증 문제다. 5.3의 `localStorage.getItem("token")` 절차로 token을 다시 가져온다.
2. `Unable to connect to the remote server`이면 `$backendUrl`이 틀렸거나 백엔드가 실행 중이 아니다. 기본 로컬 URL은 `http://localhost:8000`이다.
3. `POST /api/notifications/test` 응답의 `delivery_status.telegram.missing_keys`에 `TELEGRAM_BOT_TOKEN`이 있는지 확인한다.
4. `/mypage`에서 Telegram 채널이 "연결됨"인지 확인한다.
5. Telegram 수신 토글이 켜져 있는지 확인한다.
6. 사용자가 bot과 먼저 대화했는지 확인한다.
7. `chat_id`가 숫자만 포함하는지 확인한다. 그룹 `chat_id`는 `-`로 시작할 수 있다.
8. `/api/notifications/history`에서 Telegram 이벤트의 `status`와 `error_message`를 확인한다.

## 7. 현재 한계

- 사용자가 bot에게 `/start <code>`를 보내도 백엔드가 그 메시지를 자동 수신하지 않는다.
- webhook 방식으로 바꾸려면 `POST /api/notifications/telegram/webhook` 같은 inbound endpoint, Telegram `setWebhook`, secret 검증, 코드와 `chat_id` 매칭 로직을 별도 구현해야 한다.
- 현재 수신 절차의 기준 문서는 이 파일이며, 하네스 검증 기록은 `docs/harness/telegram-message-delivery-verification-2026-06-09.md`를 참고한다.
