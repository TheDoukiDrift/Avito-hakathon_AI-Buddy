from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas import ContactOut
from app.services import contacts as contacts_service

router = APIRouter(tags=["contacts"])


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    query: str | None = Query(default=None, description="Поиск по имени, роли или email"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ContactOut]:
    contacts = await contacts_service.list_contacts(session, user, query)
    return [ContactOut.model_validate(contact) for contact in contacts]
