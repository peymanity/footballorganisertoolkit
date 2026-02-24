"""Extended Spond client with event creation support."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from spond.spond import Spond


async def _run(coro):
    """Run a coroutine and clean up the client session."""
    return await coro


def run_async(func):
    """Decorator to run an async function synchronously."""
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper


async def get_client(username: str, password: str) -> Spond:
    """Create and authenticate a Spond client."""
    return Spond(username=username, password=password)


async def list_groups(client: Spond) -> list[dict]:
    """List all groups the user has access to."""
    groups = await client.get_groups()
    return groups or []


async def list_events(
    client: Spond,
    group_id: str | None = None,
    min_start: datetime | None = None,
    max_events: int = 20,
) -> list[dict]:
    """List events, optionally filtered by group and date."""
    return await client.get_events(
        group_id=group_id,
        min_start=min_start,
        max_events=max_events,
    ) or []


async def create_event(
    client: Spond,
    group_id: str,
    heading: str,
    start: datetime,
    end: datetime,
    description: str = "",
    location: str | None = None,
    subgroup_id: str | None = None,
    invite_all: bool = True,
) -> dict[str, Any]:
    """Create a new event (availability request) in Spond.

    The spond package doesn't expose a create method, so we call the API
    directly using the authenticated session.
    """
    # Ensure client is authenticated
    if not client.token:
        await client.login()

    url = f"{client.api_url}sponds/"

    event_data: dict[str, Any] = {
        "heading": heading,
        "description": description,
        "spondType": "EVENT",
        "startTimestamp": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endTimestamp": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "commentsDisabled": False,
        "maxAccepted": 0,
        "rsvpDate": None,
        "location": {
            "id": None,
            "feature": location,
            "address": location,
            "latitude": None,
            "longitude": None,
        },
        "visibility": "INVITEES",
        "participantsHidden": False,
        "autoReminderType": "DISABLED",
        "autoAccept": False,
        "payment": {},
        "attachments": [],
        "tasks": {"openTasks": [], "assignedTasks": []},
        "type": "EVENT",
    }

    # Attach to the group
    recipients: dict[str, Any] = {"group": {"id": group_id}}
    if subgroup_id:
        recipients["group"]["subGroups"] = [subgroup_id]

    event_data["recipients"] = recipients

    async with client.clientsession.post(
        url, json=event_data, headers=client.auth_headers
    ) as r:
        if not r.ok:
            error_text = await r.text()
            raise RuntimeError(
                f"Failed to create event (HTTP {r.status}): {error_text}"
            )
        return await r.json()
