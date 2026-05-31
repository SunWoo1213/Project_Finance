from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import User
from ..schemas import ChatMessageRequest, ChatResponse
from ..services.chat_service import handle_chat_message
from .deps import get_optional_current_user

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/message", response_model=ChatResponse)
async def post_chat_message(
    payload: ChatMessageRequest,
    current_user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await handle_chat_message(payload, current_user=current_user, db=db)
