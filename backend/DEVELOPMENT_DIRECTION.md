# Backend 개발 방향성

백엔드는 금융 데이터 수집, 캐시, 인증, 커뮤니티, AI 리포트 생성을 담당합니다.

## 책임 범위

- FastAPI 앱 구성과 라우터 등록
- DB 세션과 ORM 모델을 통한 데이터 접근
- 시장 데이터 수집 및 정규화
- AI 리포트 생성 및 조회
- JWT 인증과 커뮤니티 권한 처리
- APScheduler 기반 백그라운드 갱신 작업

## 레이어 기준

- `app/api`: HTTP 라우터, 인증 의존성, 요청/응답 계약
- `app/services`: 비즈니스 로직, 외부 API 호출, 캐시 갱신, AI 파이프라인
- `app/core`: 설정, 보안, 캐시 같은 전역 인프라
- `app/db`: DB 엔진, 세션, SQLAlchemy Base
- `app/models.py`: ORM 테이블 정의
- `app/schemas.py`: API 입출력 스키마
- `tests`: 외부 API와 DB를 격리한 검증 코드

## 개발 원칙

라우터에 외부 API 호출이나 복잡한 데이터 가공을 직접 추가하지 않습니다. 라우터는 서비스를 호출하고, 서비스는 순수하게 도메인 로직을 수행하도록 유지합니다.

시장 데이터나 AI 리포트처럼 외부 의존성이 있는 기능은 실패 응답, 빈 데이터, timeout을 정상 흐름으로 취급해야 합니다.

DB 테이블 생성은 현재 lifespan에서 `create_all`로 처리됩니다. 운영 수준으로 확장할 때는 Alembic migration 도입을 우선 검토합니다.

## Migration Workflow

Subscription billing tables are tracked by Alembic under `backend/alembic/`.
Use these commands from `backend/` after dependencies are installed:

```powershell
alembic upgrade head
alembic downgrade -1
```

The development lifespan still calls `Base.metadata.create_all` for local bootstrap, but production-like database changes should be represented as Alembic revisions before release.

## Deployment Runtime Notes

For Vercel + Supabase deployment, the FastAPI backend should run on a persistent runtime rather than Vercel serverless functions because `APScheduler`, market cache warm-up, and scheduled AI report generation assume a long-running process.

Production-like deployments should set `ENABLE_DB_SCHEMA_BOOTSTRAP=false` and run `python -m alembic upgrade head` before starting the app. In that mode startup checks required tables and AI report metadata columns without creating or altering schema.

Use `BACKEND_CORS_ORIGINS` for exact Vercel frontend origins and keep wildcard origins out of credentialed CORS. Keep `ENABLE_MARKET_WARMUP=false` and `ENABLE_SCHEDULER=false` for the first smoke deployment, then enable runtime jobs only after API, DB, cost, and rate-limit checks.

## 하네스 문서 연계

백엔드 기능을 수정할 때는 먼저 `docs/harness/feature-index.md`에서 대상 기능 문서를 찾습니다.

- 인증 라우터, JWT, 사용자 모델 변경: `docs/harness/features/authentication.md`
- 시장 가격, 뉴스, 히스토리, 캐시, 매크로 서비스 변경: `docs/harness/features/market-data.md`
- AI 리포트, LangGraph, 커뮤니티 댓글/좋아요 변경: `docs/harness/features/asset-detail-ai-community.md`

수정 후에는 관련 기능 문서의 `Ownership Map`, `Data Flow`, `Contracts`, `Change Records`를 갱신하고, 별도 변경 기록을 `docs/harness/`에 남깁니다.
