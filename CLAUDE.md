# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord Quest Completer — a single-file Python script (`quest_completer.py`) that auto-completes Discord game-play quests by sending heartbeat requests to the Discord API. No external dependencies; uses only the Python standard library (`urllib`, `json`, `base64`, etc.).

## Running

```bash
python quest_completer.py
```

The script prompts for a Discord user token on first run (saved to `.token` file) or reads from the `DISCORD_TOKEN` environment variable.

## Architecture

Everything lives in `quest_completer.py`. Key flow:

1. **Authentication** — Token from env var or `.token` file, prompted if missing
2. **Quest discovery** — `GET /quests/@me` fetches active quests, filtered to incomplete play tasks (`PLAY_ON_DESKTOP`, `STREAM_ON_DESKTOP`, `PLAY_ACTIVITY`)
3. **Enrollment** — Auto-enrolls if not already enrolled
4. **Heartbeat loop** — Sends `POST /quests/{id}/heartbeat` every 20s with a synthetic stream key, using Electron desktop client headers (required by the endpoint). Displays a progress bar until target duration is reached, then sends a terminal heartbeat.

Two sets of request headers are maintained: Electron client UA (for heartbeats) and Chrome browser UA (for general API calls). Both include `X-Super-Properties` with encoded client metadata.

## Key Details

- The heartbeat endpoint requires the Electron/desktop `User-Agent` and matching `X-Super-Properties` — browser UA will get 401s
- `client_build_number` in super properties must stay reasonably current or requests may be rejected
- Quest config can be nested under `task_config_v2` or `task_config`; user status can be under `userStatus` or `user_status` (both camelCase and snake_case are handled)
- `.token` is gitignored
