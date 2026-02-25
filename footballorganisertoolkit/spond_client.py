"""Extended Spond client with event creation support."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from spond.spond import Spond

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def _geocode_google(
    query: str, api_key: str, country: str = "gb"
) -> dict[str, Any] | None:
    """Geocode using Google Maps Geocoding API."""
    params = {
        "address": query,
        "key": api_key,
        "region": country,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(GOOGLE_GEOCODE_URL, params=params) as r:
            if not r.ok:
                return None
            data = await r.json()
            if data.get("status") != "OK" or not data.get("results"):
                return None

    result = data["results"][0]
    geo = result["geometry"]["location"]
    addr_components = {
        c["types"][0]: c
        for c in result.get("address_components", [])
        if c.get("types")
    }

    formatted = result.get("formatted_address", query)

    location_data: dict[str, Any] = {
        "feature": query,
        "address": formatted,
        "latitude": geo["lat"],
        "longitude": geo["lng"],
    }

    if "postal_code" in addr_components:
        location_data["postalCode"] = addr_components["postal_code"]["long_name"]
    if "country" in addr_components:
        location_data["country"] = addr_components["country"]["short_name"]
    if "administrative_area_level_1" in addr_components:
        location_data["administrativeAreaLevel1"] = addr_components[
            "administrative_area_level_1"
        ]["long_name"]
    if "administrative_area_level_2" in addr_components:
        location_data["administrativeAreaLevel2"] = addr_components[
            "administrative_area_level_2"
        ]["long_name"]

    return location_data


async def _geocode_nominatim(
    query: str, country: str = "gb"
) -> dict[str, Any] | None:
    """Geocode using OpenStreetMap Nominatim (no API key needed)."""
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

    name = result.get("name") or query
    road = addr.get("road", "")
    town = (
        addr.get("town")
        or addr.get("city")
        or addr.get("village")
        or addr.get("suburb")
        or ""
    )
    short_parts = [name]
    if road and road != name:
        short_parts.append(road)
    if town and town != name and town != road:
        short_parts.append(town)
    short_address = ", ".join(short_parts)

    location_data: dict[str, Any] = {
        "feature": query,
        "address": short_address,
        "latitude": float(result["lat"]),
        "longitude": float(result["lon"]),
    }

    if addr.get("postcode"):
        location_data["postalCode"] = addr["postcode"]
    if addr.get("country_code"):
        location_data["country"] = addr["country_code"].upper()
    if addr.get("state") or addr.get("region"):
        location_data["administrativeAreaLevel1"] = (
            addr.get("state") or addr.get("region")
        )
    if addr.get("county"):
        location_data["administrativeAreaLevel2"] = addr["county"]

    return location_data


async def geocode(query: str, country: str = "gb") -> dict[str, Any] | None:
    """Geocode a location string. Uses Google Maps if an API key is configured,
    otherwise falls back to OpenStreetMap Nominatim."""
    from .config import load_config

    api_key = load_config().get("google_maps_api_key")
    if api_key:
        return await _geocode_google(query, api_key, country)
    return await _geocode_nominatim(query, country)


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
    owner_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new availability request in Spond.

    Based on the structure of real events from the Harpenden Colts group.
    The spond package doesn't expose a create method, so we call the API
    directly using the authenticated session.

    location_data, if provided, takes precedence over location and should be
    a dict with keys like feature, address, latitude, longitude, postalCode, etc.

    owner_ids, if provided, sets the event hosts/owners.
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

    if owner_ids:
        event_data["owners"] = [{"id": oid} for oid in owner_ids]

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
