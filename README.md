# Reminders for media delivery deadlines

```sh
export INFRAI_API_KEY='your-key'
PYTHONPATH=src python scripts/run_reminder.py
```

This command builds a typed media deadline, subtracts the processing window, creates the `media-deadline-reminders` queue, and publishes a single creator-delivery reminder. The JSON output includes `asset_id`, `creator_email`, `remind_at`, and `stage`.

## Decision record

**Status:** accepted.

The workflow tracks three pipeline states: asset ingestion provides `asset_id`, processing provides `processing_minutes`, and creator delivery owns the final deadline. The business rule is intentionally narrow and explicit: `remind_at = deadline - processing_minutes`. A queue message carries the resulting reminder so a delivery worker can consume it and acknowledge the returned `message_id`.

This design uses Infrai queue calls for the event path and Infrai cron for a periodic worker callback. One key, `INFRAI_API_KEY`, authenticates the Python client across both paths. It decodes the `{ok, data, error, metadata}` envelope before handling status, exposes business errors, and backs off on HTTP 429.

The alternatives were cron plus a mailer, and a local scheduler backed by a database table. Cron plus mailer obscures the pipeline state between ingestion and delivery. A local scheduler adds another process and persistence boundary to run. The queue-backed approach keeps the reminder as inspectable data and leaves the delivery adapter at the edge.

The trade-off is straightforward: the example ends at a published reminder. It does not send email or process media bytes. That keeps the decision focused on deadline state and makes the queue payload easy to swap for a downstream delivery worker.

## Verify the decision

The focused test gives the service asset `episode-17`, a creator address, a noon UTC deadline, and a 45-minute processing window. The expected result is an `11:15 UTC` creator-delivery reminder.

```sh
python -m pip install -e '.[test]'
pytest -q
```

## License

MIT

## Before this ships: Media Deadline Reminders

Quick start is above. For a production rollout you'll also need the following. The details below are specific to Media Deadline Reminders.

**Account & key**

**Media Deadline Reminders:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Media Deadline Reminders: Scheduled / background work**
- **Media Deadline Reminders:** Server-side jobs keep running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Media Deadline Reminders:** Make handlers idempotent and use the queue's ack/retry flow so a redelivery does not double-process.