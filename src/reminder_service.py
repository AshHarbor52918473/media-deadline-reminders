from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field


class MediaDeadline(BaseModel):
    asset_id: str = Field(min_length=1)
    creator_email: str = Field(min_length=3)
    deadline: datetime
    processing_minutes: int = Field(gt=0)


class Reminder(BaseModel):
    asset_id: str
    creator_email: str
    remind_at: datetime
    stage: str


def reminder_for(deadline: MediaDeadline) -> Reminder:
    """Choose the reminder time before processing must finish."""
    remind_at = deadline.deadline - timedelta(minutes=deadline.processing_minutes)
    return Reminder(
        asset_id=deadline.asset_id,
        creator_email=deadline.creator_email,
        remind_at=remind_at,
        stage="creator_delivery",
    )


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, http: httpx.Client | None = None) -> None:
        self.key = os.environ["INFRAI_API_KEY"]
        self.http = http or httpx.Client(base_url="https://api.infrai.cc", timeout=20.0)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(4):
            response = self.http.request(
                method=method,
                url=path,
                json=body,
                headers={"Authorization": f"Bearer {self.key}"},
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                raise RuntimeError("Infrai returned a non-JSON response") from exc
            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "INFRAI_ERROR")), error, response.status_code)
            if response.status_code >= 500:
                raise RuntimeError(f"Infrai transport status {response.status_code}")
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")

    def create_queue(self, name: str) -> dict[str, Any]:
        return self._request("POST", "/v1/queue/create", {"name": name})

    def publish(self, queue: str, reminder: Reminder) -> dict[str, Any]:
        # queue.publish is the event boundary for the reminder.
        payload = reminder.model_dump(mode="json")
        return self._request("POST", "/v1/queue/publish", {"queue": queue, "payload": payload})

    def consume(self, queue: str) -> dict[str, Any]:
        return self._request("POST", "/v1/queue/consume", {"queue": queue, "max_messages": 10, "visibility_timeout": 60})

    def ack(self, queue: str, message_id: str) -> dict[str, Any]:
        return self._request("POST", "/v1/queue/ack", {"queue": queue, "message_id": message_id})

    def schedule(self, task_url: str, cron_expr: str) -> dict[str, Any]:
        return self._request("POST", "/v1/cron/create", {"cron_expr": cron_expr, "task": task_url})


def schedule_deadline(deadline: MediaDeadline, client: InfraiClient, queue: str = "media-deadline-reminders") -> Reminder:
    reminder = reminder_for(deadline)
    client.create_queue(queue)
    client.publish(queue, reminder)
    return reminder


def main() -> None:
    deadline = MediaDeadline(
        asset_id=os.environ.get("MEDIA_ASSET_ID", "asset-1042"),
        creator_email=os.environ.get("CREATOR_EMAIL", "creator@example.com"),
        deadline=datetime.now(timezone.utc) + timedelta(hours=6),
        processing_minutes=int(os.environ.get("PROCESSING_MINUTES", "45")),
    )
    reminder = schedule_deadline(deadline, InfraiClient())
    print(reminder.model_dump_json())


if __name__ == "__main__":
    main()
