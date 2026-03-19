from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.session import get_db
from ..models import User
from ..schemas import UserCreate, UserResponse
from ..core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    사용자 회원가입 엔드포인트. 
    이메일과 닉네임의 중복을 검사하고 비밀번호를 해싱하여 DB에 추가합니다.
    """
    # 1. 이메일 중복 체크
    email_result = await db.execute(select(User).where(User.email == user_in.email))
    if email_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

    # 2. 닉네임 중복 체크
    nickname_result = await db.execute(select(User).where(User.nickname == user_in.nickname))
    if nickname_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 사용중인 닉네임입니다.")

    # 3. 새로운 유저 모델 생성
    new_user = User(
        email=user_in.email,
        nickname=user_in.nickname,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post("/login")
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    로그인 엔드포인트. (Swagger UI의 버튼과 완벽히 호환되도록 Form 형식을 수신합니다)
    성공 시 액세스 토큰을 반환합니다.
    """
    # username 인자로 전송된 email로 유저 검색
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일이나 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 식별자(id)를 문자열로 형변환하여 액세스 토큰 생성
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "nickname": user.nickname
    }
