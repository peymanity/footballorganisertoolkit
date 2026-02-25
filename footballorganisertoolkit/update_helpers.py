"""Helper functions for updating Spond events from the CLI or skills."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from spond.spond import Spond

from .config import get_credentials, get_group_id
from .spond_client import geocode, get_client


def run(coro):
    return asyncio.run(coro)


def list_upcoming_events(max_events: int = 20) -> list[dict]:
    """List upcoming events as dicts with key fields."""

    async def _list():
        u, p = get_credentials()
        client = await get_client(u, p)
        try:
            gid = get_group_id()
            events = await client.get_events(
                group_id=gid,
                min_start=datetime.utcnow(),
                max_events=max_events,
            )
            return events or []
        finally:
            await client.clientsession.close()

    return run(_list())


def get_event_summary(events: list[dict]) -> str:
    """Format events into a readable summary for matching."""
    lines = []
    for e in events:
        start = e.get("startTimestamp", "?")[:16].replace("T", " ")
        heading = e.get("heading", "(no title)")
        eid = e["id"]
        loc = e.get("location", {}).get("address", "")
        desc = (e.get("description") or "")[:100]
        lines.append(f"  {start}  {heading}")
        lines.append(f"  ID: {eid}")
        if loc:
            lines.append(f"  Location: {loc}")
        if desc:
            lines.append(f"  Description: {desc}...")
        lines.append("")
    return "\n".join(lines)


def update_event(
    event_id: str,
    heading: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    meetup_prior: int | None = None,
    description: str | None = None,
    location_query: str | None = None,
    location_data: dict | None = None,
) -> dict:
    """Update an existing Spond event."""

    async def _update():
        u, p = get_credentials()
        client = await get_client(u, p)
        try:
            updates: dict[str, Any] = {}

            if heading is not None:
                updates["heading"] = heading

            if start is not None:
                updates["startTimestamp"] = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                if meetup_prior is not None:
                    meetup = start - timedelta(minutes=meetup_prior)
                    updates["meetupTimestamp"] = meetup.strftime(
                        "%Y-%m-%dT%H:%M:%S.000Z"
                    )
                    updates["meetupPrior"] = meetup_prior

            if end is not None:
                updates["endTimestamp"] = end.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            if description is not None:
                updates["description"] = description

            loc = location_data
            if loc is None and location_query is not None:
                loc = await geocode(location_query)
            if loc is not None:
                updates["location"] = loc

            result = await client.update_event(event_id, updates)
            return {"status": "ok", "updates": updates}
        finally:
            await client.clientsession.close()

    return run(_update())
