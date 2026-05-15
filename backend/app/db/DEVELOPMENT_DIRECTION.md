# DB 레이어 개발 방향성

이 폴더는 데이터베이스 연결과 세션 생성을 책임집니다.

## 현재 책임

- `base.py`: SQLAlchemy Base 정의
- `session.py`: Async engine, AsyncSessionLocal, `get_db` dependency 제공

## 개발 원칙

DB 세션은 FastAPI dependency인 `get_db`를 통해 주입받습니다. 라우터나 서비스에서 엔진을 새로 만들지 않습니다.

트랜잭션 경계는 명확히 유지합니다. 하나의 사용자 액션에 필요한 변경을 처리한 뒤 `commit`하고, 필요한 경우 `refresh`합니다.

ORM 모델은 현재 `backend/app/models.py`에 있습니다. 모델 파일이 커질 경우 도메인별 파일로 분리할 수 있지만, 그 경우 import cycle과 migration 전략을 먼저 정리해야 합니다.

운영 안정성을 높이는 다음 단계는 Alembic migration 도입입니다. `create_all`은 개발 초기에는 편하지만 스키마 변경 이력을 보존하지 못합니다.

