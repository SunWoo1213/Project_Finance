from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from .models import AssetCategory

# -----------------
# User Schemas
# -----------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    created_at: datetime
    
    # ORM 모델의 객체 인스턴스를 Pydantic 모델로 변환할 수 있도록 설정
    model_config = ConfigDict(from_attributes=True)

# -----------------
# Asset Schemas
# -----------------
class AssetResponse(BaseModel):
    id: int
    ticker: str
    name: str
    category: AssetCategory

    model_config = ConfigDict(from_attributes=True)

# -----------------
# Comment Schemas
# -----------------
class CommentCreate(BaseModel):
    content: str


class CommentUpdate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: int
    user_id: int
    asset_id: int
    content: str
    created_at: datetime
    likes_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class CommentResponseWithAuthor(CommentResponse):
    author_nickname: str
