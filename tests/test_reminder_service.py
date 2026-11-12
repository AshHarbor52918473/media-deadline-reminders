from datetime import datetime, timezone

from reminder_service import MediaDeadline, reminder_for


def test_reminder_starts_processing_before_creator_deadline() -> None:
    deadline = MediaDeadline(
        asset_id="episode-17",
        creator_email="ava@example.com",
        deadline=datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc),
        processing_minutes=45,
    )

    result = reminder_for(deadline)

    assert result.remind_at == datetime(2026, 10, 23, 11, 15, tzinfo=timezone.utc)
    assert result.stage == "creator_delivery"
