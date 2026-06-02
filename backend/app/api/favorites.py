from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import User
from ..schemas import FavoriteAssetCreate, FavoriteAssetResponse, FavoriteImportRequest
from ..services.favorite_service import (
    delete_user_favorite,
    favorite_to_response,
    import_user_favorites,
    list_user_favorites,
    upsert_user_favorite,
)
from .deps import get_current_user

router = APIRouter(prefix="/api/favorites", tags=["Favorites"])


@router.get("", response_model=list[FavoriteAssetResponse])
async def get_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorites = await list_user_favorites(db, current_user.id)
    return [favorite_to_response(favorite) for favorite in favorites]


@router.post("", response_model=FavoriteAssetResponse)
async def add_favorite(
    payload: FavoriteAssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        favorite = await upsert_user_favorite(
            db,
            user_id=current_user.id,
            ticker=payload.symbol,
            display_name=payload.name,
            category_key=payload.categoryKey,
            source=payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return favorite_to_response(favorite)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_user_favorite(db, user_id=current_user.id, ticker=ticker)


@router.post("/import-local", response_model=list[FavoriteAssetResponse])
async def import_local_favorites(
    payload: FavoriteImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorites = [
        {
            "symbol": favorite.symbol,
            "name": favorite.name,
            "categoryKey": favorite.categoryKey,
            "source": favorite.source or "local_import",
        }
        for favorite in payload.favorites
    ]
    merged = await import_user_favorites(db, user_id=current_user.id, favorites=favorites)
    return [favorite_to_response(favorite) for favorite in merged]
