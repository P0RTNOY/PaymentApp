"""Cloud Tasks enqueue helper for retryable async work."""

from __future__ import annotations

import json
import logging
from typing import Any

from google.cloud import tasks_v2  # type: ignore[attr-defined]
from google.protobuf import timestamp_pb2  # type: ignore[attr-defined]

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: tasks_v2.CloudTasksClient | None = None


def get_tasks_client() -> tasks_v2.CloudTasksClient:
    """Return a cached Cloud Tasks client."""
    global _client
    if _client is None:
        _client = tasks_v2.CloudTasksClient()
        logger.info("Cloud Tasks client initialised")
    return _client


async def enqueue_task(
    queue_name: str,
    handler_path: str,
    payload: dict[str, Any],
    *,
    task_id: str | None = None,
    delay_seconds: int = 0,
) -> str:
    """Create an HTTP task targeting the worker service.

    Parameters
    ----------
    queue_name:
        Queue short name (e.g. ``"provider-sync"``).
    handler_path:
        Path on the worker service (e.g. ``"/internal/tasks/process-sync-page"``).
    payload:
        JSON-serialisable dict.
    task_id:
        Optional deterministic task ID for dedup-sensitive operations.
    delay_seconds:
        Schedule delay from now.

    Returns
    -------
    str
        The created task name.
    """
    settings = get_settings()
    client = get_tasks_client()

    parent = client.queue_path(
        settings.project_id,
        settings.cloud_tasks_location,
        queue_name,
    )

    task: dict[str, Any] = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{settings.worker_service_url}{handler_path}",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload, default=str).encode(),
        },
    }

    if task_id:
        task["name"] = f"{parent}/tasks/{task_id}"

    if delay_seconds > 0:
        schedule_time = timestamp_pb2.Timestamp()
        schedule_time.GetCurrentTime()
        schedule_time.seconds += delay_seconds
        task["schedule_time"] = schedule_time

    response = client.create_task(request={"parent": parent, "task": task})
    logger.info(
        "Enqueued task",
        extra={
            "queue": queue_name,
            "handler": handler_path,
            "taskName": response.name,
        },
    )
    return response.name
