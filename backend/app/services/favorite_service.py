from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Asset, UserFavoriteAsset


def normalize_ticker(value: str | None) -> str:
    return str(value or "").strip()


def favorite_to_response(favorite: UserFavoriteAsset) -> dict:
    return {
        "id": favorite.id,
        "symbol": favorite.ticker,
        "name": favorite.display_name,
        "categoryKey": favorite.category_key,
        "source": favorite.source,
        "created_at": favorite.created_at,
    }


async def list_user_favorites(db: AsyncSession, user_id: int) -> list[UserFavoriteAsset]:
    result = await db.execute(
        select(UserFavoriteAsset)
        .where(UserFavoriteAsset.user_id == user_id)
        .order_by(UserFavoriteAsset.created_at.desc(), UserFavoriteAsset.id.desc())
    )
    return list(result.scalars().all())


async def upsert_user_favorite(
    db: AsyncSession,
    *,
    user_id: int,
    ticker: str,
    display_name: str | None,
    category_key: str | None,
    source: str = "manual",
) -> UserFavoriteAsset:
    normalized_ticker = normalize_ticker(ticker)
    if not normalized_ticker:
        raise ValueError("Ticker is required.")

    result = await db.execute(
        select(UserFavoriteAsset).where(
            UserFavoriteAsset.user_id == user_id,
            UserFavoriteAsset.ticker == normalized_ticker,
        )
    )
    favorite = result.scalar_one_or_none()

    asset_result = await db.execute(select(Asset).where(Asset.ticker == normalized_ticker))
    asset = asset_result.scalar_one_or_none()

    if favorite is None:
        favorite = UserFavoriteAsset(
            user_id=user_id,
            asset_id=asset.id if asset else None,
            ticker=normalized_ticker,
            display_name=(display_name or normalized_ticker).strip() or normalized_ticker,
            category_key=category_key,
            source=source or "manual",
        )
        db.add(favorite)
    else:
        favorite.asset_id = asset.id if asset else favorite.asset_id
        favorite.display_name = (display_name or favorite.display_name or normalized_ticker).strip()
        favorite.category_key = category_key if category_key is not None else favorite.category_key
        favorite.source = source or favorite.source

    await db.commit()
    await db.refresh(favorite)
    return favorite


async def delete_user_favorite(db: AsyncSession, *, user_id: int, ticker: str) -> bool:
    normalized_ticker = normalize_ticker(ticker)
    result = await db.execute(
        select(UserFavoriteAsset).where(
            UserFavoriteAsset.user_id == user_id,
            UserFavoriteAsset.ticker == normalized_ticker,
        )
    )
    favorite = result.scalar_one_or_none()
    if favorite is None:
        return False

    await db.delete(favorite)
    await db.commit()
    return True


async def import_user_favorites(
    db: AsyncSession,
    *,
    user_id: int,
    favorites: list[dict],
) -> list[UserFavoriteAsset]:
    for favorite in favorites:
        ticker = normalize_ticker(favorite.get("symbol"))
        if not ticker:
            continue
        await upsert_user_favorite(
            db,
            user_id=user_id,
            ticker=ticker,
            display_name=favorite.get("name"),
            category_key=favorite.get("categoryKey"),
            source=favorite.get("source") or "local_import",
        )

    return await list_user_favorites(db, user_id)
