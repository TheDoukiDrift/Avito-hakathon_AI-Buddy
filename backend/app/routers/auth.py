from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security import create_token
from app.services import audit
from app.services import users as users_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await users_service.authenticate(session, payload.email, payload.password)
    await audit.log(session, user.id, "auth.login", {"email": user.email})
    await session.commit()
    return TokenResponse(token=create_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
