# Football Organiser Toolkit

CLI tool for managing football team availability in [Spond](https://spond.com). Built for coaches who get fixture details from FA Full-Time and emails and need to quickly create/update availability requests for their team.

## Install

```bash
pip install -e .
```

This installs the `fot` command.

## Setup

```bash
fot config
```

Prompts for your Spond email and password, then lists your groups so you can pick a default.

Config is stored at `~/.config/footballorganisertoolkit/config.json`.

## Usage

### Create a home match

```bash
fot create --heading "HOME vs Team X U13" --date 2026-03-21 --home -y
```

`--home` sets:
- Kick-off 10:00, meetup 09:30
- 75 min duration
- Rothamsted Park with GPS coordinates
- Description with blue kit info and venue link

### Create an away match

```bash
fot create --heading "AWAY vs Team X U13" --date 2026-03-07 --away -y
```

`--away` sets:
- 10:00-13:30 placeholder block (3.5 hours to cover typical 10am-12pm kickoffs)
- Heading suffixed with "- TIME AND DETAILS TBC"
- Description noting details will be confirmed at least 3 days before

### Create with specific details

```bash
fot create \
  --heading "AWAY vs Hitchin Belles Youth U13 Reds" \
  --date 2026-02-28 \
  --away \
  --time 10:00 \
  --duration 75 \
  --location "The Priory School, Hitchin" \
  --description "Pitch 6\nNo dogs allowed on site." \
  -y
```

Locations are automatically geocoded via OpenStreetMap to get coordinates.

### Batch create from CSV

```bash
fot batch-create fixtures.csv
```

CSV format:

```
heading,date,time,duration_mins,location,description
Match vs Arsenal U10,2026-03-07,10:00,90,Hackney Marshes,League match
Match vs Chelsea U10,2026-03-14,14:00,90,Victoria Park,Cup match
```

### List groups and events

```bash
fot groups          # list your Spond groups with IDs
fot events          # list upcoming events with attendance counts
fot events --all    # include past events
```

### Update match details (Claude Code skill)

When using this repo with [Claude Code](https://claude.ai/claude-code), the `/update-match` command lets you paste in an email or message and have the matching Spond event updated automatically:

```
/update-match <paste email content here>
```

## Options reference

| Flag             | Description                                              |
|------------------|----------------------------------------------------------|
| `--home`         | Home match defaults (Rothamsted, blue kit, 75 min)       |
| `--away`         | Away match defaults (3.5hr block, TBC heading)           |
| `--date`         | Match date (YYYY-MM-DD)                                  |
| `--time`         | Kick-off time (HH:MM)                                    |
| `--duration`     | Duration in minutes                                      |
| `--location`     | Venue (auto-geocoded)                                    |
| `--description`  | Event description (appended to home/away defaults)       |
| `--meetup-prior` | Minutes before kick-off for meetup (default: 30)         |
| `--group-id`     | Override default group                                   |
| `--subgroup-id`  | Target a subgroup                                        |
| `-y` / `--yes`   | Skip confirmation prompt                                 |
| `--dry-run`      | Preview without creating                                 |

## How it works

Uses the [spond](https://pypi.org/project/spond/) PyPI package for authentication and reading data. Event creation calls the Spond API directly (`POST /core/v1/sponds/`) since the package doesn't have a create method.
