from datetime import datetime, timedelta, timezone
from jose import jwt

from .config import settings

def create_access_token(data: dict) -> str:
    """
    유저 식별자(sub) 등 페이로드를 담아 지정된 만료 시간을 가진 JWT 토큰을 발급합니다.
    """
    to_encode = data.copy()
    
    # 토큰 만료 시간 설정 (현재 UTC 시간 기준 + 7일)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # HS256 알고리즘과 SECRET_KEY로 JWT 서명
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt
