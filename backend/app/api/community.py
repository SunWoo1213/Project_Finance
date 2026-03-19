from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import Asset, Comment, CommentLike, User
from ..schemas import CommentCreate, CommentResponseWithAuthor, CommentUpdate
from .deps import get_current_user

router = APIRouter(prefix="/api/community", tags=["Community"])


async def _resolve_asset(db: AsyncSession, asset_key: str) -> Asset | None:
    key = str(asset_key).strip()
    if not key:
        return None

    if key.isdigit():
        asset = await db.get(Asset, int(key))
        if asset:
            return asset

    result = await db.execute(select(Asset).where(Asset.ticker == key))
    return result.scalar_one_or_none()


async def _get_comment_or_404(db: AsyncSession, comment_id: int) -> Comment:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다")
    return comment


async def _count_likes(db: AsyncSession, comment_id: int) -> int:
    result = await db.execute(select(func.count(CommentLike.user_id)).where(CommentLike.comment_id == comment_id))
    return result.scalar_one() or 0


def _comment_response_payload(comment: Comment, author_nickname: str, likes_count: int) -> dict:
    return {
        "id": comment.id,
        "user_id": comment.user_id,
        "asset_id": comment.asset_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "likes_count": likes_count,
        "author_nickname": author_nickname,
    }


@router.post("/{asset_id}/comments", response_model=CommentResponseWithAuthor)
async def create_comment(
    asset_id: str,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await _resolve_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="자산을 찾을 수 없습니다")

    content = comment_in.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="댓글 내용을 입력해주세요")

    db_comment = Comment(user_id=current_user.id, asset_id=asset.id, content=content)
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)

    return _comment_response_payload(db_comment, current_user.nickname, likes_count=0)


@router.get("/{asset_id}/comments", response_model=List[CommentResponseWithAuthor])
async def get_comments(asset_id: str, db: AsyncSession = Depends(get_db)):
    asset = await _resolve_asset(db, asset_id)
    if not asset:
        return []

    query = (
        select(
            Comment,
            User.nickname.label("author_nickname"),
            func.count(CommentLike.user_id).label("likes_count"),
        )
        .join(User, Comment.user_id == User.id)
        .outerjoin(CommentLike, Comment.id == CommentLike.comment_id)
        .where(Comment.asset_id == asset.id)
        .group_by(Comment.id, User.nickname)
        .order_by(Comment.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    return [_comment_response_payload(comment, author_nickname, likes_count) for comment, author_nickname, likes_count in rows]


@router.put("/{asset_id}/comments/{comment_id}", response_model=CommentResponseWithAuthor)
async def update_comment(
    asset_id: str,
    comment_id: int,
    comment_in: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await _resolve_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="자산을 찾을 수 없습니다")

    comment = await _get_comment_or_404(db, comment_id)
    if comment.asset_id != asset.id:
        raise HTTPException(status_code=404, detail="해당 자산의 댓글이 아닙니다")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="수정 권한이 없습니다")

    content = comment_in.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="댓글 내용을 입력해주세요")

    comment.content = content
    await db.commit()
    await db.refresh(comment)
    likes_count = await _count_likes(db, comment.id)
    return _comment_response_payload(comment, current_user.nickname, likes_count)


@router.delete("/{asset_id}/comments/{comment_id}")
async def delete_comment(
    asset_id: str,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await _resolve_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="자산을 찾을 수 없습니다")

    comment = await _get_comment_or_404(db, comment_id)
    if comment.asset_id != asset.id:
        raise HTTPException(status_code=404, detail="해당 자산의 댓글이 아닙니다")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다")

    await db.delete(comment)
    await db.commit()
    return {"message": "삭제 완료"}


@router.post("/comments/{comment_id}/like")
async def toggle_like(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_comment_or_404(db, comment_id)

    query = select(CommentLike).where(
        and_(CommentLike.user_id == current_user.id, CommentLike.comment_id == comment_id)
    )
    result = await db.execute(query)
    existing_like = result.scalar_one_or_none()

    if existing_like:
        await db.delete(existing_like)
        action = "unliked"
    else:
        db.add(CommentLike(user_id=current_user.id, comment_id=comment_id))
        action = "liked"

    await db.commit()
    return {"status": "success", "action": action, "comment_id": comment_id}
