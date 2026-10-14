"""Deterministic weekly meeting report generation."""

import asyncio
import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import SessionFactory
from app.models import Meeting, User

REPORT_TIMEZONE = ZoneInfo("Europe/Kyiv")
ISO_WEEK_PATTERN = re.compile(r"^(?P<year>[0-9]{4})-W(?P<week>[0-9]{2})$")


@dataclass(frozen=True)
class WeekRange:
    label: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class MeetingRecord:
    title: str
    starts_at: datetime
    ends_at: datetime
    participant_count: int
    organizer: str = ""

    @property
    def duration_seconds(self) -> int:
        return int((self.ends_at - self.starts_at).total_seconds())


def parse_iso_week(week: str) -> WeekRange:
    """Parse ``YYYY-Www`` and return Kyiv-local, half-open week boundaries."""
    match = ISO_WEEK_PATTERN.fullmatch(week)
    if not match:
        raise ValueError("week must use ISO format YYYY-Www")

    year = int(match.group("year"))
    week_number = int(match.group("week"))
    try:
        monday = date.fromisocalendar(year, week_number, 1)
    except ValueError as exc:
        raise ValueError(f"invalid ISO week: {week}") from exc

    start = datetime.combine(monday, datetime.min.time(), tzinfo=REPORT_TIMEZONE)
    return WeekRange(label=week, start=start, end=start + timedelta(days=7))


def previous_iso_week(week: str) -> str:
    previous_monday = parse_iso_week(week).start.date() - timedelta(days=7)
    year, week_number, _ = previous_monday.isocalendar()
    return f"{year:04d}-W{week_number:02d}"


def previous_iso_week_for(now: datetime | None = None) -> str:
    """Return the preceding ISO week in Europe/Kyiv."""
    current = (now or datetime.now(REPORT_TIMEZONE)).astimezone(REPORT_TIMEZONE)
    previous_day = current.date() - timedelta(days=7)
    year, week_number, _ = previous_day.isocalendar()
    return f"{year:04d}-W{week_number:02d}"


def _hours(seconds: int) -> str:
    value = (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


def _minutes(seconds: int) -> str:
    value = (Decimal(seconds) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


def render_weekly_report(
    week: str,
    current_meetings: list[MeetingRecord],
    previous_meetings: list[MeetingRecord],
) -> bytes:
    """Render already-fetched meetings as stable UTF-8 CSV bytes."""
    parse_iso_week(week)
    previous_week = previous_iso_week(week)
    current_seconds = sum(meeting.duration_seconds for meeting in current_meetings)
    previous_seconds = sum(meeting.duration_seconds for meeting in previous_meetings)

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Weekly meetings report", week])
    writer.writerow([])
    writer.writerow(["Metric", week, previous_week, "Difference"])
    writer.writerow(
        [
            "Meeting count",
            len(current_meetings),
            len(previous_meetings),
            len(current_meetings) - len(previous_meetings),
        ]
    )
    writer.writerow(
        [
            "Total duration (hours)",
            _hours(current_seconds),
            _hours(previous_seconds),
            _hours(current_seconds - previous_seconds),
        ]
    )
    writer.writerow([])
    writer.writerow(["Five longest meetings"])
    writer.writerow(
        ["Title", "Starting time (Europe/Kyiv)", "Duration (minutes)", "Participant count"]
    )
    longest = sorted(
        current_meetings,
        key=lambda meeting: (
            -meeting.duration_seconds,
            meeting.starts_at.astimezone(UTC),
            meeting.title,
        ),
    )[:5]
    for meeting in longest:
        writer.writerow(
            [
                meeting.title,
                meeting.starts_at.astimezone(REPORT_TIMEZONE).isoformat(),
                _minutes(meeting.duration_seconds),
                meeting.participant_count,
            ]
        )

    organizer_counts = Counter(
        meeting.organizer for meeting in current_meetings if meeting.organizer
    )
    if organizer_counts:
        writer.writerow([])
        writer.writerow(["Meetings by organizer"])
        writer.writerow(["Organizer", "Meeting count"])
        for organizer, count in sorted(organizer_counts.items(), key=lambda item: item[0]):
            writer.writerow([organizer, count])

    return output.getvalue().encode("utf-8")


async def _query_meetings(start: datetime, end: datetime) -> list[MeetingRecord]:
    statement = (
        select(Meeting, User.email)
        .outerjoin(User, Meeting.organizer_id == User.id)
        .where(
            Meeting.starts_at >= start.astimezone(UTC),
            Meeting.starts_at < end.astimezone(UTC),
        )
        .order_by(Meeting.starts_at, Meeting.id)
    )
    async with SessionFactory() as session:
        rows = (await session.execute(statement)).all()
    return [
        MeetingRecord(
            title=meeting.title,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            participant_count=meeting.participant_count,
            organizer=email or "",
        )
        for meeting, email in rows
    ]


async def build_weekly_report_async(week: str) -> bytes:
    """Query the database and build one deterministic weekly CSV report."""
    current = parse_iso_week(week)
    previous = parse_iso_week(previous_iso_week(week))
    current_meetings = await _query_meetings(current.start, current.end)
    previous_meetings = await _query_meetings(previous.start, previous.end)
    return render_weekly_report(week, current_meetings, previous_meetings)


def build_weekly_report(week: str) -> bytes:
    """Query meetings for one ISO week and return a UTF-8 CSV report."""
    return asyncio.run(build_weekly_report_async(week))
