# Core 레이어 개발 방향성

이 폴더는 앱 전체에서 공유되는 인프라성 코드를 둡니다.

## 현재 책임

- `config.py`: `.env` 기반 설정 로드
- `security.py`: JWT 생성
- `cache.py`: 시장 데이터 in-memory cache

## 개발 원칙

이 폴더에는 특정 API 기능의 비즈니스 로직을 넣지 않습니다. 여러 기능이 공통으로 의존하는 설정, 보안, 캐시, 공통 인프라만 둡니다.

환경변수는 `settings`를 통해 접근합니다. 서비스나 라우터에서 `os.getenv`를 직접 호출하는 방식은 피합니다.

캐시는 프로세스 메모리 기반입니다. 서버 재시작 시 사라지며, 여러 프로세스/컨테이너를 운영할 경우 캐시 불일치가 생길 수 있습니다. 운영 확장 시 Redis 같은 외부 캐시로 이동할 수 있게 호출부를 단순하게 유지합니다.

## 하네스 문서 연계

`core` 변경은 여러 기능에 영향을 줄 수 있으므로 연결된 기능 문서를 함께 갱신합니다.

- `config.py`, `security.py`의 인증/JWT/Google 설정 변경: `docs/harness/features/authentication.md`
- `cache.py`의 시장 데이터 캐시 shape 또는 수명 변경: `docs/harness/features/market-data.md`

환경변수는 이름만 문서화하고 실제 값은 쓰지 않습니다. 설정, 보안, 캐시 계약이 바뀌면 `docs/harness/` 변경 기록에 영향 범위를 남깁니다.
