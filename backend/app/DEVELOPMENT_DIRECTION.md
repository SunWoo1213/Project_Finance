# Backend App 개발 방향성

`backend/app`은 FastAPI 애플리케이션의 실제 소스 루트입니다.

## 이 위치의 역할

- `main.py`: 앱 생성, 미들웨어, lifespan, 스케줄러, 라우터 등록
- `models.py`: SQLAlchemy ORM 모델
- `schemas.py`: Pydantic API 스키마
- `api`: HTTP 라우터
- `services`: 비즈니스 로직과 외부 연동
- `core`: 설정, 보안, 캐시
- `db`: DB 연결과 세션

## 개발 원칙

`main.py`는 앱 조립 지점입니다. 새 기능의 상세 로직을 계속 추가하지 말고, 기능이 커지면 `api`와 `services`로 분리합니다.

`models.py`는 DB 저장 구조, `schemas.py`는 API 입출력 구조입니다. 둘은 비슷해 보여도 목적이 다릅니다. DB 필드가 그대로 외부 응답이 되어야 한다고 가정하지 않습니다.

새 기능을 추가할 때 기본 흐름은 다음입니다.

1. DB 저장이 필요한가를 먼저 판단합니다.
2. 필요하다면 `models.py`와 `schemas.py`의 책임을 나눕니다.
3. HTTP 입구는 `api`에 둡니다.
4. 실제 처리 로직은 `services`에 둡니다.
5. 공통 설정이나 보안 처리는 `core`에 둡니다.

