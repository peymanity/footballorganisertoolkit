# Football Organiser Toolkit

CLI tool for managing football team events/availability in Spond.

## Project structure

- `footballorganisertoolkit/cli.py` - Click CLI commands
- `footballorganisertoolkit/spond_client.py` - Async Spond API wrapper (extends the `spond` PyPI package with event creation)
- `footballorganisertoolkit/config.py` - Credentials and config stored at `~/.config/footballorganisertoolkit/config.json`

## CLI entry point

Installed as `fot` command via pyproject.toml `[project.scripts]`.

## Key decisions

- The `spond` package (v1.1.1) has no `create_event` — we POST directly to `{api_url}sponds/` using the authenticated session
- All Spond API calls are async (aiohttp); CLI wraps with `asyncio.run()`
- Config stores Spond credentials locally (not in repo)

## Spond API notes

- Base URL: `https://api.spond.com/core/v1/`
- Auth: POST to `login` with email/password, returns `loginToken` used as Bearer token
- Events endpoint: `sponds/` (GET to list, POST to create)
- Groups endpoint: `groups/`
