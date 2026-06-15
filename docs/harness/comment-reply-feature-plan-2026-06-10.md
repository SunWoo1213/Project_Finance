# 댓글 대댓글(답글) 기능 추가 계획

Date: 2026-06-10
Status: 계획(Plan) — 구현 전. DB 스키마 변경 포함이므로 사용자 승인 필요.

## 1. 목적 (Objective)

자산 상세 페이지 커뮤니티(종토방)의 댓글에 **대댓글(답글)** 을 달 수 있게 한다.
현재는 자산(`asset_id`)에 대한 1단계 평면 댓글만 가능하다. 특정 댓글에 답글을 연결해
대화 맥락이 이어지도록 한다.

## 2. 현재 동작 / 목표 동작

### 현재 동작
- `comments` 테이블은 `user_id`, `asset_id`, `content`, `created_at`만 가진다([models.py:119](backend/app/models.py#L119)).
- 모든 댓글이 같은 자산 아래 평면으로 나열된다. 댓글 간 부모-자식 관계가 없다.
- `GET /api/community/{asset_id}/comments`는 자산의 모든 댓글을 `created_at desc`로 반환한다([community.py:149](backend/app/api/community.py#L149)).
- 프론트는 `comments.map(...)`로 단일 레벨 목록만 렌더한다([AssetDetail.jsx:517](frontend/src/pages/AssetDetail.jsx#L517)).
- 좋아요/수정/삭제/신고는 댓글 단위로 동작한다.

### 목표 동작
- 각 최상위 댓글 아래에 답글을 달 수 있다(**1단계 중첩** 권장 — 아래 위험/결정 참고).
- 답글도 댓글이므로 좋아요·수정·삭제·신고 메커니즘을 그대로 재사용한다.
- 부모 댓글이 삭제되면(소유자 삭제 또는 신고 100건 자동삭제) 그 답글들도 함께 삭제된다(cascade).
- 답글 작성도 기존 댓글과 동일하게 JWT + `nickname_confirmed_at` 확인을 요구한다.

## 3. 변경 대상 파일

### Backend
- [backend/app/models.py](backend/app/models.py) — `Comment`에 자기참조 `parent_id` 컬럼 + 관계/캐스케이드 추가.
- [backend/app/schemas.py](backend/app/schemas.py) — `CommentCreate.parent_id`(선택), `CommentResponse.parent_id` 추가.
- [backend/app/api/community.py](backend/app/api/community.py) — 생성 시 `parent_id` 검증, 목록 응답에 `parent_id` 포함.

### DB (마이그레이션 — Risky)
- `backend/alembic/versions/20260610_0001_add_comment_parent_id.py` (신규) — `comments.parent_id` 컬럼 + FK 추가.
- 로컬 부트스트랩 경로(`ENABLE_DB_SCHEMA_BOOTSTRAP=true`일 때 lifespan의 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`)가 있다면 동일 컬럼을 추가하도록 보강 검토([main.py](backend/app/main.py)).

### Frontend
- [frontend/src/pages/AssetDetail.jsx](frontend/src/pages/AssetDetail.jsx) — 답글 입력 상태, 답글 작성 핸들러, 부모 아래 답글 중첩 렌더, "답글" 버튼 추가.

## 4. 단계별 구현 계획

### 4-1. 데이터 모델 (models.py)
- `Comment`에 추가:
  ```python
  parent_id: Mapped[int | None] = mapped_column(
      Integer, ForeignKey("comments.id"), nullable=True, index=True
  )
  replies: Mapped[List["Comment"]] = relationship(
      "Comment",
      back_populates="parent",
      cascade="all, delete-orphan",
      single_parent=True,
  )
  parent: Mapped["Comment | None"] = relationship(
      "Comment", remote_side="Comment.id", back_populates="replies"
  )
  ```
- 부모 삭제 시 답글 자동 삭제(cascade)로, 기존 신고 100건 자동삭제 로직과도 자연스럽게 연동된다.

### 4-2. 스키마 (schemas.py)
- `CommentCreate`에 `parent_id: int | None = None` 추가.
- `CommentResponse`에 `parent_id: int | None = None` 추가(→ `CommentResponseWithAuthor`에도 상속됨).

### 4-3. 라우터 (community.py)
- `create_comment`:
  - `comment_in.parent_id`가 있으면 부모 댓글을 조회해 (a) 존재하고 (b) 같은 `asset.id`에 속하며 (c) **부모가 또 다른 답글이 아닌 최상위 댓글**(`parent_id is None`)인지 검증. 위반 시 HTTP 422/404.
  - `Comment(... parent_id=parent.id)`로 저장.
  - 응답 payload(`_comment_response_payload`)에 `parent_id` 추가.
- `get_comments`: 기존 집계 쿼리에 `Comment.parent_id`가 응답되도록 `_comment_response_payload`에 `comment.parent_id` 포함. 정렬은 부모 우선이 되도록 프론트에서 그룹핑하거나(권장), 백엔드에서 `parent_id nulls first, created_at` 정렬 고려.
- 수정/삭제/좋아요/신고 핸들러는 댓글 id 기반이라 답글에도 그대로 동작 — 수정 불필요.

### 4-4. 마이그레이션
- 기존 마이그레이션 형식([20260602_0002](backend/alembic/versions/20260602_0002_add_user_nickname_confirmed_at.py)) 따라 신규 리비전 작성:
  - `down_revision = "20260602_0002"`
  - `upgrade`: `op.add_column("comments", sa.Column("parent_id", sa.Integer(), nullable=True))` + `op.create_foreign_key(..., "comments", "comments", ["parent_id"], ["id"])` + 인덱스.
  - `downgrade`: FK/인덱스/컬럼 drop.

### 4-5. 프론트엔드 (AssetDetail.jsx)
- 상태 추가: `replyingToId`, `replyContent`.
- `comments`를 부모/답글로 그룹핑: `parent_id === null`인 댓글을 최상위로, 각 부모 아래 `parent_id === parent.id`인 답글을 들여쓰기 렌더.
- 각 최상위 댓글에 "답글" 버튼 → 답글 입력창 토글.
- `handlePostReply(parentId)`: 기존 `handlePostComment`와 동일 엔드포인트(`POST /api/community/{asset}/comments`)에 `{ content, parent_id: parentId }` 전송 후 `fetchComments()`.
- 답글에도 좋아요/수정/삭제/신고 버튼 재사용(소유자 판별 동일).

## 5. 위험과 Risky Change 여부

- **Risky Change (사용자 승인 필요)**: AGENTS.md 섹션 9의 "DB 스키마 변경(마이그레이션 필요)"에 해당한다. `comments`에 `parent_id` 컬럼/FK를 추가한다.
  - 기존 운영 DB는 `python -m alembic upgrade head` 적용 전까지 새 컬럼이 없으므로, ORM이 `parent_id`를 select/insert하면 오류가 난다. **배포 시 마이그레이션 선적용이 필수.**
  - `ENABLE_DB_SCHEMA_BOOTSTRAP=true` 로컬 환경은 lifespan 부트스트랩으로 컬럼 추가가 가능하나, 운영은 Alembic에 의존.
- 인증/스케줄러/리포트 비용에는 영향 없음(읽기 전용 공개 조회 + 인증 쓰기 분리 유지).
- 자기참조 cascade 삭제 동작은 테스트로 확인 필요(부모 삭제 시 답글 동반 삭제).

### 결정이 필요한 사항 (구현 전 확인)
1. **중첩 깊이**: 1단계(답글에는 답글 불가, 권장) vs 다단계(스레드형). 권장은 1단계 — UI/쿼리가 단순하고 무한 들여쓰기 방지.
2. **답글의 신고 100건 자동삭제 / 좋아요 적용 여부**: 답글도 댓글이므로 기본 적용을 권장.

## 6. 검증 계획 (AGENTS.md 섹션 6 최소 집합)

- Backend 구문/임포트: `py -m compileall backend\app`
- Backend 커뮤니티 테스트(가능 시): 답글 생성, 부모-자산 정합 검증, 부모 cascade 삭제, 기존 댓글 회귀를 `backend/tests/`에 추가/실행. 실제 LLM/외부 호출 없음.
- DB 의존 검증 시 PostgreSQL 기동 후 `python -m alembic upgrade head` 적용 확인.
- Frontend: `frontend/`에서 `npm run lint`, `npm run build`(실행 정책상 `npm.cmd` 사용).

## 7. 갱신할 문서

- `docs/harness/features/asset-detail-ai-community.md`
  - Current Behavior에 대댓글 동작 추가, Contracts에 `parent_id`(생성 요청/응답) 명시, Data Flow에 답글 흐름 추가, Change Records에 구현 기록 링크.
- `docs/harness/feature-index.md`
  - "Asset detail, AI report, community" 행 Change records에 본 계획서 + 구현 기록 링크 추가.
- 구현 단계에서 `docs/harness/comment-reply-feature-implementation-2026-06-10.md` 작성.
- 데이터 모델/라우트 구조 변경이므로 루트 `CODE_UNDERSTANDING.md`의 커뮤니티/모델 절도 함께 최신화 검토.
