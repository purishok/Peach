from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Meeting, User
from app.reports import weekly
from app.reports.weekly import (
    MeetingRecord,
    parse_iso_week,
    previous_iso_week,
    render_weekly_report,
)


def meeting(
    title: str,
    starts_at: datetime,
    minutes: int,
    participants: int = 1,
    organizer: str = "",
) -> MeetingRecord:
    return MeetingRecord(
        title=title,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=minutes),
        participant_count=participants,
        organizer=organizer,
    )


def test_parse_iso_week_uses_kyiv_boundaries() -> None:
    parsed = parse_iso_week("2026-W40")
    assert parsed.start.isoformat() == "2026-09-28T00:00:00+03:00"
    assert parsed.end.isoformat() == "2026-10-05T00:00:00+03:00"


@pytest.mark.parametrize("value", ["2026-40", "2026-W00", "2026-W54", "26-W40", ""])
def test_parse_iso_week_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_iso_week(value)


def test_previous_week_crosses_iso_year_boundary() -> None:
    assert previous_iso_week("2026-W01") == "2025-W52"
    assert previous_iso_week("2021-W01") == "2020-W53"


def test_empty_week_has_zero_statistics() -> None:
    csv_text = render_weekly_report("2026-W40", [], []).decode("utf-8")
    assert "Meeting count,0,0,0\n" in csv_text
    assert "Total duration (hours),0.00,0.00,0.00\n" in csv_text


def test_counts_duration_and_previous_week_comparison() -> None:
    start = datetime(2026, 9, 28, 9, tzinfo=UTC)
    report = render_weekly_report(
        "2026-W40",
        [meeting("Planning", start, 60), meeting("Review", start, 90)],
        [meeting("Earlier", start - timedelta(days=7), 30)],
    ).decode("utf-8")
    assert "Meeting count,2,1,1\n" in report
    assert "Total duration (hours),2.50,0.50,2.00\n" in report


def test_only_five_longest_meetings_are_included_in_order() -> None:
    start = datetime(2026, 9, 28, 9, tzinfo=UTC)
    meetings = [meeting(f"Meeting {minutes}", start, minutes) for minutes in range(10, 70, 10)]
    report = render_weekly_report("2026-W40", meetings, []).decode("utf-8")
    longest_section = report.split("Five longest meetings\n", 1)[1]
    assert "Meeting 60" in longest_section
    assert "Meeting 20" in longest_section
    assert "Meeting 10" not in longest_section
    assert longest_section.index("Meeting 60") < longest_section.index("Meeting 50")


def test_csv_is_utf8_and_deterministic() -> None:
    start = datetime(2026, 9, 28, 9, tzinfo=UTC)
    meetings = [meeting("Зустріч", start, 45, organizer="Організатор")]
    first = render_weekly_report("2026-W40", meetings, [])
    second = render_weekly_report("2026-W40", meetings, [])
    assert first == second
    assert "Зустріч" in first.decode("utf-8")


async def test_build_weekly_report_queries_postgres(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    organizer = User(cognito_sub="report-organizer", email="organizer@example.com")
    session.add(organizer)
    await session.flush()
    session.add_all(
        [
            Meeting(
                organizer_id=organizer.id,
                title="Current meeting",
                starts_at=datetime(2026, 9, 30, 8, tzinfo=UTC),
                ends_at=datetime(2026, 9, 30, 9, 30, tzinfo=UTC),
                participant_count=4,
            ),
            Meeting(
                organizer_id=organizer.id,
                title="Previous meeting",
                starts_at=datetime(2026, 9, 23, 8, tzinfo=UTC),
                ends_at=datetime(2026, 9, 23, 8, 30, tzinfo=UTC),
                participant_count=2,
            ),
        ]
    )
    await session.flush()

    factory = async_sessionmaker(bind=session.bind, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(weekly, "SessionFactory", factory)
    report = (await weekly.build_weekly_report_async("2026-W40")).decode("utf-8")

    assert "Meeting count,1,1,0" in report
    assert "Total duration (hours),1.50,0.50,1.00" in report
    assert "organizer@example.com,1" in report
