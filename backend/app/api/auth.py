import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token
except ImportError:  # pragma: no cover - dependency availability is environment-specific
    google_requests = None
    google_id_token = None

from ..core.config import settings
from ..core.security import create_access_token
from ..db.session import get_db
from ..models import User
from ..schemas import AuthTokenResponse, GoogleLoginRequest

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _normalize_nickname(value: str | None, email: str) -> str:
    base = (value or email.split("@")[0] or "google-user").strip()
    base = re.sub(r"\s+", " ", base)
    return base[:30]


async def _build_unique_nickname(db: AsyncSession, preferred: str) -> str:
    nickname = preferred
    suffix = 1

    while True:
        result = await db.execute(select(User).where(User.nickname == nickname))
        if result.scalar_one_or_none() is None:
            return nickname

        suffix += 1
        trimmed = preferred[: max(1, 30 - len(str(suffix)) - 1)]
        nickname = f"{trimmed}-{suffix}"


def _verify_google_credential(credential: str) -> dict:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured.",
        )

    if google_requests is None or google_id_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication dependency is not installed.",
        )

    try:
        id_info = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not id_info.get("email") or not id_info.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential does not include required profile data.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not id_info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return id_info


@router.post("/google", response_model=AuthTokenResponse)
async def login_with_google(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Google Identity Services ID token을 검증한 뒤 앱 자체 JWT를 발급합니다.
    """
    id_info = _verify_google_credential(payload.credential)
    google_sub = str(id_info["sub"])
    email = str(id_info["email"]).lower()

    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            nickname = await _build_unique_nickname(
                db,
                _normalize_nickname(id_info.get("name"), email),
            )
            user = User(
                email=email,
                google_sub=google_sub,
                nickname=nickname,
            )
            db.add(user)
        else:
            user.google_sub = google_sub

        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id)})

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        nickname_confirmed=user.nickname_confirmed_at is not None,
        profile_complete=user.nickname_confirmed_at is not None,
    )
