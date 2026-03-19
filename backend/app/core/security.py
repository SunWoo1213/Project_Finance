from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt

from .config import settings

# bcrypt 기반의 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    평문 비밀번호를 bcrypt 해싱하여 반환합니다.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 DB에 저장된 해시 비밀번호가 일치하는지 검증합니다.
    """
    return pwd_context.verify(plain_password, hashed_password)

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
