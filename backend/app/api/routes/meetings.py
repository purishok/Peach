"""The ordinary validated write path for meetings and agendas."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.ai.agenda import ParsedAgenda
from app.auth import CurrentUser
from app.db import SessionDep
from app.models.meeting import Meeting

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Time zone offset required")
        return value


class MeetingRead(MeetingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    agenda: dict | None = None
    ai_suggestion: dict | None = None


class MeetingList(BaseModel):
    meetings: list[MeetingRead]


class AgendaSave(BaseModel):
    agenda: ParsedAgenda
    ai_suggestion: dict | None = None


async def owned_meeting(session: SessionDep, user: CurrentUser, meeting_id: uuid.UUID) -> Meeting:
    meeting = await session.scalar(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.organizer_id == user.id)
    )
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    return meeting


@router.get("", response_model=MeetingList)
async def list_meetings(session: SessionDep, user: CurrentUser) -> MeetingList:
    rows = (
        await session.scalars(
            select(Meeting)
            .where(Meeting.organizer_id == user.id)
            .order_by(Meeting.starts_at.desc())
            .limit(100)
        )
    ).all()
    return MeetingList(meetings=[MeetingRead.model_validate(row) for row in rows])


@router.post("", response_model=MeetingRead, status_code=201)
async def create_meeting(
    payload: MeetingCreate, session: SessionDep, user: CurrentUser
) -> MeetingRead:
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(422, "End must be after start")
    meeting = Meeting(
        organizer_id=user.id,
        title=payload.title.strip(),
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        participant_count=0,
    )
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)
    return MeetingRead.model_validate(meeting)


@router.get("/{meeting_id}", response_model=MeetingRead)
async def get_meeting(meeting_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> MeetingRead:
    return MeetingRead.model_validate(await owned_meeting(session, user, meeting_id))


@router.put("/{meeting_id}/agenda", response_model=MeetingRead)
async def save_agenda(
    meeting_id: uuid.UUID, payload: AgendaSave, session: SessionDep, user: CurrentUser
) -> MeetingRead:
    meeting = await owned_meeting(session, user, meeting_id)
    suggestion = payload.ai_suggestion
    if suggestion is not None:
        if set(suggestion) != {"agenda", "model", "prompt_version"}:
            raise HTTPException(422, "Invalid AI suggestion metadata")
        try:
            ParsedAgenda.model_validate(suggestion["agenda"])
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, "Invalid AI suggestion") from exc
        if not all(
            isinstance(suggestion[k], str) and len(suggestion[k]) <= 120
            for k in ("model", "prompt_version")
        ):
            raise HTTPException(422, "Invalid AI suggestion metadata")
    meeting.agenda = payload.agenda.model_dump(mode="json")
    meeting.ai_suggestion = suggestion
    await session.commit()
    await session.refresh(meeting)
    return MeetingRead.model_validate(meeting)
