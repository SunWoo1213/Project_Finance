# Gmail OAuth Refresh Token 발급 절차

이 문서는 `EMAIL_FROM_ADDRESS`와 `GMAIL_REFRESH_TOKEN`을 준비해 Project Finance의 Gmail 알림 발송을 활성화하는 절차를 정리한다. 실제 토큰, client secret, 이메일 비밀번호는 이 문서나 Git에 기록하지 않는다.

## 필요한 환경변수

```text
EMAIL_PROVIDER=gmail
EMAIL_FROM_ADDRESS=<Gmail API로 메일을 보낼 Gmail 주소>
GMAIL_CLIENT_ID=<Google Cloud OAuth client ID>
GMAIL_CLIENT_SECRET=<Google Cloud OAuth client secret>
GMAIL_REFRESH_TOKEN=<OAuth offline access로 발급받은 refresh token>
```

`EMAIL_FROM_ADDRESS`는 별도로 발급되는 값이 아니라 Gmail API 발송 권한을 허용할 Google 계정의 이메일 주소다. 예: `alerts@example.com` 또는 `project-alerts@gmail.com`

`GMAIL_REFRESH_TOKEN`은 위 Gmail 계정으로 OAuth 동의를 완료했을 때 발급되는 장기 토큰이다. 백엔드는 이 refresh token으로 access token을 갱신한 뒤 Gmail API `users.messages.send`를 호출한다.

## 1. Google Cloud 프로젝트 준비

1. Google Cloud Console에 접속한다.
   - https://console.cloud.google.com
2. 기존 프로젝트를 선택하거나 새 프로젝트를 만든다.
3. `APIs & Services` -> `Library`로 이동한다.
4. `Gmail API`를 검색한 뒤 활성화한다.

공식 Gmail 발송 문서:

- https://developers.google.com/gmail/api/guides/sending

## 2. OAuth 동의 화면 설정

1. `APIs & Services` -> `OAuth consent screen`으로 이동한다.
2. 개인 Gmail 또는 외부 사용자 계정으로 테스트한다면 보통 `External`을 선택한다.
3. App name, support email, developer contact email을 입력한다.
4. Scope에 다음 권한을 추가한다.

```text
https://www.googleapis.com/auth/gmail.send
```

5. Publishing status가 `Testing`이면 `Test users`에 발송용 Gmail 계정을 추가한다.

주의: Google 문서에 따르면 `External + Testing` 상태의 OAuth 앱은 일부 refresh token 수명이 7일로 제한될 수 있다. 운영에서 장기 사용하려면 OAuth 앱 게시 상태, 민감 scope 검토, Google 정책 요구사항을 별도로 확인한다.

공식 OAuth 문서:

- https://developers.google.com/identity/protocols/oauth2
- https://developers.google.com/identity/protocols/oauth2/web-server

## 3. OAuth Client 생성

1. `APIs & Services` -> `Credentials`로 이동한다.
2. `Create credentials` -> `OAuth client ID`를 선택한다.
3. Application type은 `Web application`을 선택한다.
4. Authorized redirect URIs에 다음 값을 추가한다.

```text
https://developers.google.com/oauthplayground
```

5. 생성된 `Client ID`와 `Client Secret`을 안전한 곳에 임시로 보관한다.

## 4. OAuth Playground에서 refresh token 발급

1. OAuth Playground에 접속한다.
   - https://developers.google.com/oauthplayground
2. 오른쪽 위 톱니바퀴를 연다.
3. `Use your own OAuth credentials`를 체크한다.
4. 위에서 만든 `Client ID`, `Client Secret`을 입력한다.
5. Step 1의 scope 입력란에 다음 scope를 넣는다.

```text
https://www.googleapis.com/auth/gmail.send
```

6. `Authorize APIs`를 클릭한다.
7. `EMAIL_FROM_ADDRESS`로 사용할 Gmail 계정으로 로그인하고 권한을 허용한다.
8. Step 2에서 `Exchange authorization code for tokens`를 클릭한다.
9. 응답에 포함된 `refresh_token` 값을 복사한다.

refresh token이 응답에 보이지 않으면 다음을 확인한다.

- OAuth Playground 설정에서 `Use your own OAuth credentials`가 체크되어 있는지 확인한다.
- 같은 계정/클라이언트로 이미 동의한 적이 있다면 Google 계정의 앱 액세스를 철회한 뒤 다시 승인한다.
- authorization 요청이 offline access를 포함해야 한다. OAuth Playground는 이 흐름을 처리하지만, 직접 구현할 때는 `access_type=offline`이 필요하다.

## 5. Render 환경변수 설정

Render Dashboard의 backend service 환경변수에 다음 값을 넣는다.

```text
EMAIL_PROVIDER=gmail
EMAIL_FROM_ADDRESS=<발송용 Gmail 주소>
GMAIL_CLIENT_ID=<OAuth client ID>
GMAIL_CLIENT_SECRET=<OAuth client secret>
GMAIL_REFRESH_TOKEN=<refresh token>
```

값을 저장한 뒤 backend service를 재시작하거나 재배포한다.

## 6. 동작 확인

1. 앱에서 마이페이지의 수신 동의 영역으로 이동한다.
2. Google Mail 수신 이메일을 입력하고 인증 코드 발송을 요청한다.
3. 브라우저 DevTools Network에서 `/api/notifications/channels/email/verify` 응답을 확인한다.
4. 성공하면 `200`과 함께 인증 코드가 API 응답에 노출되지 않고, 실제 Gmail로 코드가 발송된다.
5. 실패하면 `503`과 함께 다음 형태의 detail이 내려온다.

```json
{
  "detail": "Gmail verification code delivery failed. ..."
}
```

대표 원인:

- `EMAIL_PROVIDER`가 `gmail`이 아니다.
- `EMAIL_FROM_ADDRESS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` 중 누락된 값이 있다.
- refresh token이 만료, 폐기, 권한 철회, 비밀번호 변경 등으로 더 이상 유효하지 않다.
- Gmail API가 비활성화되어 있거나 OAuth scope에 `gmail.send`가 없다.

## 보안 주의

- `GMAIL_REFRESH_TOKEN`과 `GMAIL_CLIENT_SECRET`은 secret이다.
- `.env.example`에는 placeholder만 둔다.
- 실제 값은 Render 환경변수 또는 로컬 `.env`에만 저장한다.
- 토큰이 로그, 채팅, 스크린샷, 문서에 노출되면 즉시 폐기하고 새로 발급한다.
- Gmail 계정 비밀번호나 앱 비밀번호를 이 프로젝트 환경변수에 넣지 않는다. 현재 구현은 Gmail API OAuth refresh token 방식을 사용한다.
