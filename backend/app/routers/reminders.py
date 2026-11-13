"""S3 reminders: what the AI-cron owes the user, and acknowledging it."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas import ReminderAckOut, ReminderOut, RemindersOut
from app.services import reminders as reminders_service

router = APIRouter(tags=["reminders"])


@router.get("/reminders", response_model=RemindersOut)
async def list_reminders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RemindersOut:
    rows = await reminders_service.list_for_actor(session, user)
    return RemindersOut(reminders=[ReminderOut.model_validate(row) for row in rows])


@router.post("/reminders/{reminder_id}/ack", response_model=ReminderAckOut)
async def ack_reminder(
    reminder_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReminderAckOut:
    reminder = await reminders_service.ack(session, user, reminder_id)
    await session.commit()
    return ReminderAckOut(id=reminder.id, acked=True)
