"""CLI entry point for the Football Organiser Toolkit."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import click

from .config import CONFIGURABLE_KEYS, get_credentials, get_group_id, load_config, save_config
from .spond_client import create_event, geocode, get_client, list_events, list_groups

# Peyman + Christian as co-hosts on all events
DEFAULT_OWNER_IDS = [
    "34622EBE338D2C6D39960BA0ED32E231",  # Peyman Owladi
    "67CCEE9213574F305B5B99A8B575C850",  # Christian Dam
]

HOME_DEFAULTS = {
    "time": "10:00",
    "duration": 75,
    "meetup_prior": 30,
    "description": (
        "BLUE (home) kit\n"
        "\n"
        "Rothamsted venue info: https://drive.google.com/file/d/1Z21E2VEupl3gc1yIs305VgQ9TXECRK70/view?usp=sharing"
    ),
    "location_data": {
        "feature": "Rothamsted Park",
        "address": "Rothamsted Park, Harpenden",
        "latitude": 51.811954,
        "longitude": -0.3605304,
        "country": "GB",
        "administrativeAreaLevel1": "England",
        "administrativeAreaLevel2": "Hertfordshire",
    },
}

AWAY_DEFAULTS = {
    "time": "10:00",
    "duration": 210,
    "meetup_prior": 30,
    "heading_suffix": " - TIME AND DETAILS TBC",
    "description": (
        "Meeting/kickoff time and full details will be confirmed at least 3 days "
        "before the match once notified by the home team."
    ),
}


def _run(coro):
    """Run an async coroutine and ensure the client session is closed."""
    return asyncio.run(coro)


async def _with_client(func, *args, **kwargs):
    """Run an async function with a Spond client, closing the session after."""
    username, password = get_credentials()
    client = await get_client(username, password)
    try:
        return await func(client, *args, **kwargs)
    finally:
        await client.clientsession.close()


@click.group()
def cli():
    """Football Organiser Toolkit - manage Spond availability for your team."""
    pass


@cli.command()
@click.option("--username", prompt="Spond email", help="Your Spond login email")
@click.option(
    "--password", prompt="Spond password", hide_input=True, help="Your Spond password"
)
def config(username, password):
    """Configure Spond credentials and default group."""
    cfg = load_config()
    cfg["spond_username"] = username
    cfg["spond_password"] = password
    save_config(cfg)
    click.echo("Credentials saved. Fetching your groups...")

    async def _pick_group():
        client = await get_client(username, password)
        try:
            grps = await list_groups(client)
        finally:
            await client.clientsession.close()
        return grps

    grps = _run(_pick_group())

    if not grps:
        click.echo("No groups found. You can set a group ID later with: fot config")
        return

    click.echo("")
    for i, g in enumerate(grps, 1):
        member_count = len(g.get("members", []))
        click.echo(f"  {i}. {g['name']} ({member_count} members)")

    if len(grps) == 1:
        choice = 1
        click.echo(f"\nOnly one group found, selecting: {grps[0]['name']}")
    else:
        choice = click.prompt(
            "\nSelect default group",
            type=click.IntRange(1, len(grps)),
        )

    selected = grps[choice - 1]
    cfg["group_id"] = selected["id"]
    cfg["group_name"] = selected["name"]
    save_config(cfg)
    click.echo(f"Default group set to: {selected['name']}")


@cli.command("config-set")
@click.argument("key", type=click.Choice(list(CONFIGURABLE_KEYS.keys()), case_sensitive=False))
@click.argument("value")
def config_set(key, value):
    """Set a config value.

    \b
    Available keys:
      google_maps_api_key  Google Maps Geocoding API key
      group_id             Default Spond group ID
      group_name           Default Spond group name
    """
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    click.echo(f"Set {key}.")


@cli.command()
def groups():
    """List your Spond groups and their IDs."""

    async def _list():
        username, password = get_credentials()
        client = await get_client(username, password)
        try:
            grps = await list_groups(client)
            if not grps:
                click.echo("No groups found.")
                return
            for g in grps:
                click.echo(f"\n  Group: {g['name']}")
                click.echo(f"  ID:    {g['id']}")
                if "subGroups" in g and g["subGroups"]:
                    for sg in g["subGroups"]:
                        click.echo(f"    Subgroup: {sg['name']}  ID: {sg['id']}")
                member_count = len(g.get("members", []))
                click.echo(f"  Members: {member_count}")
        finally:
            await client.clientsession.close()

    _run(_list())


@cli.command()
@click.option("--group-id", default=None, help="Filter by group ID")
@click.option("--upcoming/--all", default=True, help="Show only upcoming events")
@click.option("--max", "max_events", default=20, help="Max events to retrieve")
def events(group_id, upcoming, max_events):
    """List events from Spond."""

    async def _list():
        username, password = get_credentials()
        client = await get_client(username, password)
        gid = group_id or load_config().get("group_id")
        try:
            min_start = datetime.utcnow() if upcoming else None
            evts = await list_events(
                client, group_id=gid, min_start=min_start, max_events=max_events
            )
            if not evts:
                click.echo("No events found.")
                return
            for e in evts:
                start = e.get("startTimestamp", "?")[:16].replace("T", " ")
                heading = e.get("heading", "(no title)")
                eid = e["id"]
                accepted = sum(
                    1
                    for r in e.get("responses", {}).get("acceptedIds", [])
                )
                declined = sum(
                    1
                    for r in e.get("responses", {}).get("declinedIds", [])
                )
                click.echo(f"\n  {start}  {heading}")
                click.echo(f"  ID: {eid}")
                click.echo(f"  Accepted: {accepted}  Declined: {declined}")
                if e.get("location", {}).get("address"):
                    click.echo(f"  Location: {e['location']['address']}")
        finally:
            await client.clientsession.close()

    _run(_list())


@cli.command("create")
@click.option("--heading", required=True, help="Event title, e.g. 'Match vs Team X'")
@click.option(
    "--date",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Event date (YYYY-MM-DD)",
)
@click.option("--time", "start_time", default=None, help="Kick-off time (HH:MM), default 10:00 for home")
@click.option("--duration", default=None, type=int, help="Duration in minutes (default: 75)")
@click.option("--description", default=None, help="Event description (appended to home/away defaults)")
@click.option("--location", default=None, help="Venue / location")
@click.option("--meetup-prior", default=None, type=int, help="Meetup time before kick-off in minutes (default: 30)")
@click.option("--home", is_flag=True, help="Home match: Rothamsted Park, 10:00 KO, blue kit, venue info link")
@click.option("--away", is_flag=True, help="Away match: 10:00-13:30 block, TBC heading/description")
@click.option("--group-id", default=None, help="Group ID (uses default if not set)")
@click.option("--subgroup-id", default=None, help="Subgroup ID")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--dry-run", is_flag=True, help="Show what would be created without creating")
def create_cmd(heading, date, start_time, duration, description, location, meetup_prior, home, away, group_id, subgroup_id, yes, dry_run):
    """Create an availability request in Spond.

    Use --home for home matches (Rothamsted Park, 10:00 KO, 75 min, blue kit info).
    Use --away for away matches (10:00-13:30 block, TBC heading/description).
    All defaults can be overridden with explicit flags.
    """
    if home and away:
        raise click.UsageError("Cannot use both --home and --away.")
    gid = group_id or get_group_id()

    # Apply home/away defaults
    if home:
        defaults = HOME_DEFAULTS
    elif away:
        defaults = AWAY_DEFAULTS
    else:
        defaults = {}
    location_data = None

    if start_time is None:
        start_time = defaults.get("time") or "10:00"
    if duration is None:
        duration = defaults.get("duration") or 75
    if meetup_prior is None:
        meetup_prior = defaults.get("meetup_prior") or 30

    # Apply heading suffix for away matches
    if away and "heading_suffix" in defaults and defaults["heading_suffix"] not in heading:
        heading = heading + defaults["heading_suffix"]

    # Build description
    default_desc = defaults.get("description", "")
    if description is not None and default_desc:
        final_description = default_desc + "\n\n" + description
    elif description is not None:
        final_description = description
    else:
        final_description = default_desc

    # Location: --home uses Rothamsted with lat/lng, explicit --location gets geocoded
    if home and location is None:
        location_data = defaults["location_data"]
        location_display = location_data["address"]
    elif location:
        click.echo(f"  Geocoding '{location}'...")
        location_data = _run(geocode(location))
        if location_data:
            location_display = location_data["address"]
            click.echo(f"  Found: {location_display}")
            click.echo(f"  Coords: {location_data['latitude']}, {location_data['longitude']}")
        else:
            click.echo(f"  Geocoding failed, using location string as-is.")
            location_display = location
    else:
        location_display = None

    # Parse time
    try:
        hour, minute = map(int, start_time.split(":"))
    except ValueError:
        raise click.BadParameter("Time must be in HH:MM format", param_hint="--time")

    start = date.replace(hour=hour, minute=minute)
    end = start + timedelta(minutes=duration)
    meetup = start - timedelta(minutes=meetup_prior)

    click.echo(f"\n  Event:    {heading}")
    if home or away:
        click.echo(f"  Type:     {'HOME' if home else 'AWAY'}")
    click.echo(f"  Date:     {start.strftime('%a %d %b %Y')}")
    click.echo(f"  Meetup:   {meetup.strftime('%H:%M')}")
    click.echo(f"  Kick-off: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")
    click.echo(f"  Duration: {duration} min")
    if location_display:
        click.echo(f"  Location: {location_display}")
    if final_description:
        click.echo(f"  Description:\n    {final_description.replace(chr(10), chr(10) + '    ')}")

    if dry_run:
        click.echo("\n  [DRY RUN] Event not created.")
        return

    if not yes and not click.confirm("\n  Create this event?"):
        click.echo("  Cancelled.")
        return

    async def _create():
        username, password = get_credentials()
        client = await get_client(username, password)
        try:
            result = await create_event(
                client,
                group_id=gid,
                heading=heading,
                start=start,
                end=end,
                description=final_description,
                location=location if not location_data else None,
                location_data=location_data,
                meetup_prior=meetup_prior,
                subgroup_id=subgroup_id,
                owner_ids=DEFAULT_OWNER_IDS,
            )
            click.echo(f"\n  Event created! ID: {result.get('id', '?')}")
        finally:
            await client.clientsession.close()

    _run(_create())


@cli.command("batch-create")
@click.argument("file", type=click.Path(exists=True))
@click.option("--group-id", default=None, help="Group ID (uses default if not set)")
@click.option("--dry-run", is_flag=True, help="Show what would be created without creating")
def batch_create(file, group_id, dry_run):
    """Create multiple events from a CSV file.

    CSV columns: heading, date (YYYY-MM-DD), time (HH:MM), duration_mins, location, description

    Example CSV:
    \b
    heading,date,time,duration_mins,location,description
    Match vs Arsenal U10,2026-03-07,10:00,90,Hackney Marshes,League match
    Match vs Chelsea U10,2026-03-14,14:00,90,Victoria Park,Cup match
    """
    import csv

    gid = group_id or get_group_id()

    with open(file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        click.echo("No events found in CSV.")
        return

    click.echo(f"\nFound {len(rows)} event(s) to create:\n")
    events_to_create = []

    for row in rows:
        heading = row["heading"].strip()
        date_str = row["date"].strip()
        time_str = row["time"].strip()
        duration = int(row.get("duration_mins", "90").strip() or "90")
        location = row.get("location", "").strip() or None
        description = row.get("description", "").strip()

        date = datetime.strptime(date_str, "%Y-%m-%d")
        hour, minute = map(int, time_str.split(":"))
        start = date.replace(hour=hour, minute=minute)
        end = start + timedelta(minutes=duration)

        events_to_create.append(
            {
                "heading": heading,
                "start": start,
                "end": end,
                "duration": duration,
                "location": location,
                "description": description,
            }
        )

        click.echo(
            f"  {start.strftime('%a %d %b %H:%M')}-{end.strftime('%H:%M')}  {heading}"
        )
        if location:
            click.echo(f"    Location: {location}")

    if dry_run:
        click.echo("\n[DRY RUN] No events created.")
        return

    if not click.confirm(f"\nCreate all {len(events_to_create)} events?"):
        click.echo("Cancelled.")
        return

    async def _batch():
        username, password = get_credentials()
        client = await get_client(username, password)
        try:
            for evt in events_to_create:
                result = await create_event(
                    client,
                    group_id=gid,
                    heading=evt["heading"],
                    start=evt["start"],
                    end=evt["end"],
                    description=evt["description"],
                    location=evt["location"],
                    owner_ids=DEFAULT_OWNER_IDS,
                )
                click.echo(
                    f"  Created: {evt['heading']} -> ID: {result.get('id', '?')}"
                )
        finally:
            await client.clientsession.close()

    _run(_batch())
