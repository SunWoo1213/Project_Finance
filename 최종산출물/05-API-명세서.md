# 5. API 명세서

기준: `backend/app/main.py`, `backend/app/api/*.py`, `backend/app/schemas.py`. 베이스 프로토콜: REST / JSON. 인증: `Authorization: Bearer <JWT>`.

> 보안: 본 문서에는 실제 키/시크릿/`.env` 값을 기재하지 않는다. 인증 토큰은 Google 로그인으로 발급된 JWT를 사용한다.

## 5.1 시스템 / 헬스

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/health` | - | 서버 상태·프로젝트명 반환 |
| GET | `/db-check` | - | `SELECT 1`로 DB 연결 확인 |

## 5.2 인증 (`/api/auth`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | `/api/auth/google` | - | Google ID Token 검증 후 JWT 발급. 응답: `AuthTokenResponse` |

## 5.3 프로필 (`/api/profile`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/api/profile/me` | 필요 | 내 프로필 조회 (`ProfileMeResponse`) |
| GET | `/api/profile/nickname-availability` | 필요 | 닉네임 사용 가능 여부 |
| PATCH | `/api/profile/nickname` | 필요 | 닉네임 변경 |

## 5.4 시장 데이터 (`/api/market`, `/api/reports`, `/api/ai`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/api/market/prices` | - | 캐시된 전체 시장 가격 |
| GET | `/api/market/news` | - | 캐시된 전체 뉴스 |
| GET | `/api/market/latest-context/{ticker}` | - | 티커 최신 컨텍스트 |
| GET | `/api/market/history/{ticker}?period=` | - | 기간별 히스토리 (`1d,1mo,1y,5y`) |
| GET | `/api/reports/{ticker}` | 필요(PLUS↑) | 최신 AI 리포트 조회 (`require_report_access`) |
| POST | `/api/ai/generate/{ticker}` | 운영 한정 | 리포트 생성. **일반 사용자 기본 흐름 아님**(AGENTS.md §14) |

## 5.5 커뮤니티 (`/api/community`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/api/community/{asset_id}/comments` | - | 댓글 목록(최신순, 작성자/좋아요 수 포함) |
| POST | `/api/community/{asset_id}/comments` | 필요 | 댓글 작성 (asset_id = ID 또는 티커) |
| PUT | `/api/community/{asset_id}/comments/{comment_id}` | 필요(본인) | 댓글 수정 |
| DELETE | `/api/community/{asset_id}/comments/{comment_id}` | 필요(본인) | 댓글 삭제 |
| POST | `/api/community/comments/{comment_id}/like` | 필요 | 좋아요 토글 |
| POST | `/api/community/comments/{comment_id}/report` | 필요 | 댓글 신고(중복 차단) |

예외: 공백 댓글 422, 타인 댓글 수정/삭제 403.

## 5.6 즐겨찾기 (`/api/favorites`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/api/favorites` | 필요 | 즐겨찾기 목록 |
| POST | `/api/favorites` | 필요 | 즐겨찾기 추가 |
| DELETE | `/api/favorites/{ticker}` | 필요 | 즐겨찾기 삭제 (204) |
| POST | `/api/favorites/import-local` | 필요 | 로컬 즐겨찾기 서버 동기화 |

## 5.7 알림 (`/api/notifications`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/api/notifications/preferences` | 필요 | 알림 설정 조회 |
| PUT | `/api/notifications/preferences` | 필요 | 알림 설정 갱신 |
| GET | `/api/notifications/channels` | 필요 | 채널 목록 |
| POST | `/api/notifications/channels/telegram/connect` | 필요 | Telegram 연결 시작 |
| POST | `/api/notifications/channels/telegram/verify` | 필요 | Telegram 검증 |
| DELETE | `/api/notifications/channels/telegram` | 필요 | Telegram 연결 해제 (204) |
| POST | `/api/notifications/channels/email/verify` | 필요 | 이메일 검증 코드 발송 |
| POST | `/api/notifications/channels/email/confirm` | 필요 | 이메일 검증 확인 |
| DELETE | `/api/notifications/channels/email` | 필요 | 이메일 연결 해제 (204) |
| GET | `/api/notifications/history` | 필요 | 알림 발송 이력 |
| POST | `/api/notifications/test` | 필요 | 테스트 알림 발송 |

> 알림 기능은 PLUS 이상 entitlement(`can_use_notifications`)에서 동작.

## 5.8 구독 / 결제 (`/api/billing`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| GET | `/api/billing/plans` | - | 요금제 목록 (`BillingPlanResponse[]`) |
| GET | `/api/billing/me` | 필요 | 내 구독/등급/entitlement |
| POST | `/api/billing/checkout` | 필요 | 결제(빌링) 인텐트 생성 |
| GET | `/api/billing/checkout/{intent_id}` | 필요 | 인텐트 상태 조회 |
| POST | `/api/billing/toss/billing-key` | 필요 | Toss 빌링키 등록 → 구독 활성화 |
| POST | `/api/billing/cancel` | 필요 | 구독 취소 |
| POST | `/api/billing/webhook` | 서명검증 | 결제 웹훅(멱등 처리) |

## 5.9 챗봇 (`/api/chat`)

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | `/api/chat/message` | 필요(PRO) | 멀티턴 챗봇 메시지 (`ChatResponse`). 저장 리포트 조회 기반 |

## 5.10 공통 응답 / 에러 규약

| 코드 | 의미 |
| --- | --- |
| 200 / 201 | 성공 |
| 204 | 성공(본문 없음, 삭제) |
| 401 | 인증 토큰 없음/무효 |
| 403 | 권한 없음(본인 아님 / 등급 미달) |
| 404 | 리소스 없음(리포트 미존재 등) |
| 422 | 입력 검증 실패(빈 댓글 등) |

> 요청/응답 스키마 상세는 `backend/app/schemas.py`의 Pydantic 모델을 단일 진실 소스로 참조한다.
