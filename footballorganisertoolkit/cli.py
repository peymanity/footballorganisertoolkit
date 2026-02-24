"""CLI entry point for the Football Organiser Toolkit."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import click

from .config import get_credentials, get_group_id, load_config, save_config
from .spond_client import create_event, get_client, list_events, list_groups


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
@click.option("--time", "start_time", required=True, help="Kick-off time (HH:MM)")
@click.option(
    "--duration",
    default=90,
    help="Duration in minutes (default: 90)",
)
@click.option("--description", default="", help="Event description")
@click.option("--location", default=None, help="Venue / location")
@click.option("--meetup-prior", default=30, help="Meetup time before kick-off in minutes (default: 30)")
@click.option("--group-id", default=None, help="Group ID (uses default if not set)")
@click.option("--subgroup-id", default=None, help="Subgroup ID")
@click.option("--dry-run", is_flag=True, help="Show what would be created without creating")
def create_cmd(heading, date, start_time, duration, description, location, meetup_prior, group_id, subgroup_id, dry_run):
    """Create an availability request in Spond."""
    gid = group_id or get_group_id()

    # Parse time
    try:
        hour, minute = map(int, start_time.split(":"))
    except ValueError:
        raise click.BadParameter("Time must be in HH:MM format", param_hint="--time")

    start = date.replace(hour=hour, minute=minute)
    end = start + timedelta(minutes=duration)
    meetup = start - timedelta(minutes=meetup_prior)

    click.echo(f"\n  Event:    {heading}")
    click.echo(f"  Date:     {start.strftime('%a %d %b %Y')}")
    click.echo(f"  Meetup:   {meetup.strftime('%H:%M')}")
    click.echo(f"  Kick-off: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")
    click.echo(f"  Duration: {duration} min")
    if location:
        click.echo(f"  Location: {location}")
    if description:
        click.echo(f"  Description: {description}")
    click.echo(f"  Group:    {gid}")
    if subgroup_id:
        click.echo(f"  Subgroup: {subgroup_id}")

    if dry_run:
        click.echo("\n  [DRY RUN] Event not created.")
        return

    if not click.confirm("\n  Create this event?"):
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
                description=description,
                location=location,
                meetup_prior=meetup_prior,
                subgroup_id=subgroup_id,
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
                )
                click.echo(
                    f"  Created: {evt['heading']} -> ID: {result.get('id', '?')}"
                )
        finally:
            await client.clientsession.close()

    _run(_batch())
