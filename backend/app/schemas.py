"""Pydantic v2 request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import (
    AbsenceStatus,
    AbsenceType,
    MessageRole,
    ProgressStatus,
    Role,
)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    full_name: str
    team: str | None = None


class TokenResponse(BaseModel):
    token: str
    user: UserOut


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    created_at: datetime
    tool_calls: list | dict | None = None


class ChecklistItemOut(BaseModel):
    id: int
    week: int
    title: str
    description: str | None = None
    position: int
    status: ProgressStatus
    completed_at: datetime | None = None


class ChecklistOut(BaseModel):
    user_id: int
    full_name: str
    done: int
    total: int
    items: list[ChecklistItemOut]


class AbsenceCreate(BaseModel):
    type: AbsenceType
    date_from: date
    date_to: date
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check_range(self) -> AbsenceCreate:
        if self.date_to < self.date_from:
            raise ValueError("date_to must not be earlier than date_from")
        return self


class AbsenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: AbsenceType
    date_from: date
    date_to: date
    reason: str | None = None
    status: AbsenceStatus
    created_at: datetime
    decided_by: int | None = None
    decided_at: datetime | None = None


class AbsenceDecision(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    team: str | None = None
    email: str


class HealthOut(BaseModel):
    status: str = "ok"
