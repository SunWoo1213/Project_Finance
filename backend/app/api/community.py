from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.cache import market_cache
from ..db.session import get_db
from ..models import Asset, AssetCategory, Comment, CommentLike, CommentReport, User
from ..schemas import CommentCreate, CommentResponseWithAuthor, CommentUpdate
from .deps import get_current_user

router = APIRouter(prefix="/api/community", tags=["Community"])

REPORT_DELETE_THRESHOLD = 100


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


def _category_from_cache_group(group_name: str, ticker: str) -> AssetCategory:
    if group_name == "macro":
        return AssetCategory.INDEX
    if group_name == "bonds":
        return AssetCategory.BOND_KR if ticker.startswith("KTB_") else AssetCategory.BOND_US
    if group_name == "commodities":
        return AssetCategory.COMMODITY
    if group_name == "cryptos":
        return AssetCategory.CRYPTO
    if group_name == "kr_top10":
        return AssetCategory.STOCK_KR
    return AssetCategory.STOCK_US


def _find_cached_asset_payload(asset_key: str) -> tuple[str, dict] | None:
    key = str(asset_key).strip()
    for group_name, group in (market_cache.get("prices") or {}).items():
        if not isinstance(group, dict):
            continue
        for label, payload in group.items():
            if not isinstance(payload, dict):
                continue
            if key in {str(label), str(payload.get("symbol", ""))}:
                return group_name, payload
    return None


async def _resolve_or_create_asset_for_comment(db: AsyncSession, asset_key: str) -> Asset | None:
    asset = await _resolve_asset(db, asset_key)
    if asset:
        return asset

    cached = _find_cached_asset_payload(asset_key)
    if cached is None:
        return None

    group_name, payload = cached
    ticker = str(payload.get("symbol") or asset_key).strip()
    if not ticker:
        return None

    asset = Asset(
        ticker=ticker,
        name=ticker,
        category=_category_from_cache_group(group_name, ticker),
    )
    db.add(asset)
    await db.flush()
    return asset


async def _get_comment_or_404(db: AsyncSession, comment_id: int) -> Comment:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다")
    return comment


async def _count_likes(db: AsyncSession, comment_id: int) -> int:
    result = await db.execute(select(func.count(CommentLike.user_id)).where(CommentLike.comment_id == comment_id))
    return result.scalar_one() or 0


async def _count_reports(db: AsyncSession, comment_id: int) -> int:
    result = await db.execute(select(func.count(CommentReport.user_id)).where(CommentReport.comment_id == comment_id))
    return result.scalar_one() or 0


def _comment_response_payload(comment: Comment, author_nickname: str, likes_count: int, reports_count: int = 0) -> dict:
    return {
        "id": comment.id,
        "user_id": comment.user_id,
        "asset_id": comment.asset_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "likes_count": likes_count,
        "reports_count": reports_count,
        "author_nickname": author_nickname,
    }


def _ensure_comment_profile_complete(user: User) -> None:
    if user.nickname_confirmed_at is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "NICKNAME_REQUIRED",
                "message": "댓글을 작성하려면 마이페이지에서 닉네임을 먼저 설정해주세요.",
            },
        )


@router.post("/{asset_id}/comments", response_model=CommentResponseWithAuthor)
async def create_comment(
    asset_id: str,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_comment_profile_complete(current_user)

    asset = await _resolve_or_create_asset_for_comment(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="자산을 찾을 수 없습니다")

    content = comment_in.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="댓글 내용을 입력해주세요")

    db_comment = Comment(user_id=current_user.id, asset_id=asset.id, content=content)
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)

    return _comment_response_payload(db_comment, current_user.nickname, likes_count=0, reports_count=0)


@router.get("/{asset_id}/comments", response_model=List[CommentResponseWithAuthor])
async def get_comments(asset_id: str, db: AsyncSession = Depends(get_db)):
    asset = await _resolve_asset(db, asset_id)
    if not asset:
        return []

    query = (
        select(
            Comment,
            User.nickname.label("author_nickname"),
            func.count(func.distinct(CommentLike.user_id)).label("likes_count"),
            func.count(func.distinct(CommentReport.user_id)).label("reports_count"),
        )
        .join(User, Comment.user_id == User.id)
        .outerjoin(CommentLike, Comment.id == CommentLike.comment_id)
        .outerjoin(CommentReport, Comment.id == CommentReport.comment_id)
        .where(Comment.asset_id == asset.id)
        .group_by(Comment.id, User.nickname)
        .order_by(Comment.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        _comment_response_payload(comment, author_nickname, likes_count, reports_count)
        for comment, author_nickname, likes_count, reports_count in rows
    ]


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
    reports_count = await _count_reports(db, comment.id)
    return _comment_response_payload(comment, current_user.nickname, likes_count, reports_count)


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


@router.post("/comments/{comment_id}/report")
async def report_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = await _get_comment_or_404(db, comment_id)
    if comment.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="본인 댓글은 신고할 수 없습니다")

    query = select(CommentReport).where(
        and_(CommentReport.user_id == current_user.id, CommentReport.comment_id == comment_id)
    )
    result = await db.execute(query)
    existing_report = result.scalar_one_or_none()

    if existing_report:
        reports_count = await _count_reports(db, comment_id)
        return {
            "status": "already_reported",
            "comment_id": comment_id,
            "reports_count": reports_count,
            "deleted": False,
        }

    db.add(CommentReport(user_id=current_user.id, comment_id=comment_id))
    await db.flush()

    reports_count = await _count_reports(db, comment_id)
    deleted = reports_count >= REPORT_DELETE_THRESHOLD
    if deleted:
        await db.delete(comment)

    await db.commit()
    return {
        "status": "reported",
        "comment_id": comment_id,
        "reports_count": reports_count,
        "deleted": deleted,
    }


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
