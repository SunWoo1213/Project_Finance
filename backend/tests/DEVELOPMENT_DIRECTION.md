# Backend Tests 개발 방향성

이 폴더는 백엔드 동작을 외부 API와 최대한 분리해서 검증하는 곳입니다.

## 테스트 원칙

외부 금융 API, OpenAI API, 실제 운영 DB에 의존하지 않는 테스트를 우선합니다.

테스트에서 필요한 외부 응답은 monkeypatch, fake client, fixture로 고정합니다. 네트워크 상태에 따라 성공/실패가 달라지는 테스트는 기본 테스트로 두지 않습니다.

우선 검증해야 할 영역은 다음입니다.

- ticker 정규화와 자산군 분기
- 빈 데이터 또는 잘못된 ticker에 대한 응답
- 인증/권한 실패
- 댓글 CRUD와 좋아요 토글
- 리포트 조회 실패와 생성 실패 처리

E2E 또는 실제 API smoke test가 필요할 경우 별도 명령으로 분리하고, 기본 CI 테스트와 섞지 않습니다.

## 하네스 문서 연계

테스트를 추가하거나 검증 전략을 바꾸면 해당 기능 문서의 `Verification` 섹션도 갱신합니다.

- 인증 테스트: `docs/harness/features/authentication.md`
- 시장 데이터/provider 테스트: `docs/harness/features/market-data.md`
- AI 리포트/커뮤니티 테스트: `docs/harness/features/asset-detail-ai-community.md`

변경 기록에는 실행한 명령, 실패한 명령, 외부 의존성을 mock했는지 여부를 남깁니다.
