"""Extended Spond client with event creation support."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from spond.spond import Spond

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def geocode(query: str, country: str = "gb") -> dict[str, Any] | None:
    """Geocode a location string using OpenStreetMap Nominatim.

    Returns a dict with feature, address, latitude, longitude, and any
    available address components matching the Spond location format.
    Returns None if no results found.
    """
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": "1",
        "countrycodes": country,
    }
    headers = {"User-Agent": "footballorganisertoolkit/0.1.0"}

    async with aiohttp.ClientSession() as session:
        async with session.get(NOMINATIM_URL, params=params, headers=headers) as r:
            if not r.ok:
                return None
            results = await r.json()
            if not results:
                return None

    result = results[0]
    addr = result.get("address", {})

    # Build a short address like "The Priory School, Bedford Road, Hitchin"
    name = result.get("name") or query
    road = addr.get("road", "")
    town = (
        addr.get("town")
        or addr.get("city")
        or addr.get("village")
        or addr.get("suburb")
        or ""
    )
    parts = [p for p in [name, road, town] if p and p != name or p == name]
    # Deduplicate: name is always first, only add road/town if different
    short_parts = [name]
    if road and road != name:
        short_parts.append(road)
    if town and town != name and town != road:
        short_parts.append(town)
    short_address = ", ".join(short_parts)

    location_data: dict[str, Any] = {
        "feature": name,
        "address": short_address,
        "latitude": float(result["lat"]),
        "longitude": float(result["lon"]),
    }

    if addr.get("postcode"):
        location_data["postalCode"] = addr["postcode"]
    if addr.get("country_code"):
        location_data["country"] = addr["country_code"].upper()
    if addr.get("state") or addr.get("region"):
        location_data["administrativeAreaLevel1"] = addr.get("state") or addr.get("region")
    if addr.get("county"):
        location_data["administrativeAreaLevel2"] = addr["county"]

    return location_data


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
    location_data: dict[str, Any] | None = None,
    meetup_prior: int = 30,
    subgroup_id: str | None = None,
) -> dict[str, Any]:
    """Create a new availability request in Spond.

    Based on the structure of real events from the Harpenden Colts group.
    The spond package doesn't expose a create method, so we call the API
    directly using the authenticated session.

    location_data, if provided, takes precedence over location and should be
    a dict with keys like feature, address, latitude, longitude, postalCode, etc.
    """
    if not client.token:
        await client.login()

    url = f"{client.api_url}sponds/"

    meetup = start - timedelta(minutes=meetup_prior)

    event_data: dict[str, Any] = {
        "heading": heading,
        "description": description,
        "startTimestamp": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endTimestamp": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "meetupTimestamp": meetup.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "meetupPrior": meetup_prior,
        "commentsDisabled": False,
        "maxAccepted": 0,
        "rsvpDate": None,
        "visibility": "INVITEES",
        "participantsHidden": False,
        "autoReminderType": "DISABLED",
        "autoAccept": False,
        "hidden": False,
        "payment": {},
        "attachments": [],
        "tasks": {"openTasks": [], "assignedTasks": []},
        "type": "AVAILABILITY",
        "matchEvent": False,
    }

    if location_data:
        event_data["location"] = location_data
    elif location:
        event_data["location"] = {
            "feature": location,
            "address": location,
        }

    recipients: dict[str, Any] = {
        "group": {"id": group_id},
        "profiles": [],
        "guardians": [],
    }
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
