from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas import AuditEventOut
from app.services import audit as audit_service

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditEventOut])
async def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200, description="Сколько последних событий"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventOut]:
    """Scoped audit feed: own events, the team's, or everything for HR BP."""
    events = await audit_service.list_for_actor(session, user, limit)
    return [AuditEventOut.model_validate(event) for event in events]
