"""
Discord Quest Completer
Completes game-play quests by sending heartbeats directly via the API.

Usage:
  python quest_completer.py
"""

import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API_BASE = "https://discord.com/api/v9"
TOKEN_FILE = Path(__file__).parent / ".token"

# Electron desktop client user-agent (required for heartbeat endpoint)
_ELECTRON_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) discord/1.0.9185 Chrome/128.0.6613.186 "
    "Electron/32.2.7 Safari/537.36"
)

_SUPER_PROPS = base64.b64encode(json.dumps({
    "os": "Windows",
    "browser": "Discord Client",
    "release_channel": "stable",
    "client_version": "1.0.9185",
    "os_version": "10.0.26200",
    "os_arch": "x64",
    "app_arch": "x64",
    "system_locale": "en-US",
    "has_client_mods": False,
    "browser_user_agent": _ELECTRON_UA,
    "browser_version": "32.2.7",
    "client_build_number": 504649,
    "client_event_source": None,
}, separators=(',', ':')).encode()).decode()

# Browser UA for general API calls (quest listing etc)
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

_BROWSER_SUPER_PROPS = base64.b64encode(json.dumps({
    "os": "Windows",
    "browser": "Chrome",
    "device": "",
    "system_locale": "en-US",
    "has_client_mods": False,
    "browser_user_agent": _BROWSER_UA,
    "browser_version": "145.0.0.0",
    "os_version": "10",
    "release_channel": "stable",
    "client_build_number": 504649,
    "client_event_source": None,
}, separators=(',', ':')).encode()).decode()


def api_request(method: str, endpoint: str, token: str, body: dict = None,
                use_electron_ua: bool = False) -> dict:
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": _ELECTRON_UA if use_electron_ua else _BROWSER_UA,
        "X-Super-Properties": _SUPER_PROPS if use_electron_ua else _BROWSER_SUPER_PROPS,
        "X-Discord-Locale": "en-US",
        "X-Discord-Timezone": "Europe/London",
    }
    data = json.dumps(body).encode() if body else None
    req = Request(f"{API_BASE}{endpoint}", data=data, headers=headers, method=method)
    with urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def api_get(endpoint: str, token: str) -> dict:
    return api_request("GET", endpoint, token)


def api_post(endpoint: str, token: str, body: dict, use_electron_ua: bool = False) -> dict:
    return api_request("POST", endpoint, token, body, use_electron_ua)


def get_quests(token: str) -> list:
    data = api_get("/quests/@me", token)
    if isinstance(data, dict) and "quests" in data:
        return data["quests"]
    if isinstance(data, list):
        return data
    return []


def find_play_tasks(quest: dict) -> dict:
    """Return {task_type: task_config} for supported play tasks."""
    config = quest.get("config", {})
    tc = config.get("task_config_v2") or config.get("task_config") or {}
    tasks = tc.get("tasks", {})
    supported = ("PLAY_ON_DESKTOP", "STREAM_ON_DESKTOP", "PLAY_ACTIVITY")
    result = {}
    if isinstance(tasks, dict):
        for key, val in tasks.items():
            if key in supported:
                result[key] = val
    return result


def format_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m > 0 else f"{s}s"


def enroll_quest(quest_id: str, token: str):
    """Enroll in a quest if not already enrolled."""
    try:
        api_post(f"/quests/{quest_id}/enroll", token, {})
        print("  Enrolled in quest.")
    except HTTPError as e:
        if e.code == 400:
            pass  # Already enrolled
        else:
            print(f"  Enroll warning: {e.code} (may already be enrolled)")


def send_heartbeat(quest_id: str, token: str, stream_key: str, terminal: bool = False) -> dict:
    """Send a quest heartbeat. Returns response with progress info."""
    body = {"stream_key": stream_key, "terminal": terminal}
    return api_post(f"/quests/{quest_id}/heartbeat", token, body, use_electron_ua=True)


def complete_quest_via_heartbeat(quest: dict, token: str):
    """Complete a quest by sending periodic heartbeats."""
    config = quest.get("config", {})
    quest_id = quest["id"]
    messages = config.get("messages", {})
    quest_name = messages.get("quest_name", "Unknown")
    app = config.get("application", {})

    play_tasks = find_play_tasks(quest)
    if not play_tasks:
        print("No supported play tasks found.")
        return

    task_name = list(play_tasks.keys())[0]
    task = play_tasks[task_name]
    target = task.get("target", 900)

    # Check current progress
    user_status = quest.get("userStatus", quest.get("user_status", {})) or {}
    progress_data = user_status.get("progress", {})
    current = 0
    if isinstance(progress_data, dict) and task_name in progress_data:
        val = progress_data[task_name]
        current = val.get("value", 0) if isinstance(val, dict) else val

    print(f"\n  Quest: {quest_name}")
    print(f"  Task: {task_name}")
    print(f"  Target: {format_duration(target)}")
    print(f"  Progress: {format_duration(current)}")
    print(f"  Remaining: {format_duration(max(0, target - current))}")

    if current >= target:
        print("\n  Quest already complete! Go claim your reward.")
        return

    # Always enroll (idempotent — 400 just means already enrolled)
    enroll_quest(quest_id, token)

    # Generate a fake stream key using the quest's application id
    app_id = str(app.get("id", quest_id))
    stream_key = f"call:{app_id}:1"

    print(f"\n  Sending heartbeats every 20s...")
    print(f"  Stream key: {stream_key}")
    print("  Press Ctrl+C to stop.\n")

    enrolled_retry = False
    try:
        while True:
            try:
                resp = send_heartbeat(quest_id, token, stream_key, terminal=False)
                enrolled_retry = False
            except HTTPError as e:
                err_body = e.read().decode() if hasattr(e, 'read') else ''
                print(f"\n  Heartbeat error {e.code}: {err_body[:200]}")
                if e.code == 401:
                    print("  401 = needs Electron user-agent. This should be handled.")
                    break
                if e.code == 404:
                    if not enrolled_retry:
                        print("  Retrying after re-enroll...")
                        enroll_quest(quest_id, token)
                        enrolled_retry = True
                        time.sleep(5)
                        continue
                    print("  Quest not found. It may have expired.")
                    break
                # Retry on other errors
                time.sleep(20)
                continue

            # Parse progress from response
            progress = resp.get("progress", {})
            if isinstance(progress, dict) and task_name in progress:
                val = progress[task_name]
                current = val.get("value", 0) if isinstance(val, dict) else val

            completed_at = resp.get("completed_at")

            pct = min(100, (current / target) * 100) if target > 0 else 100
            bar_len = 40
            filled = int(bar_len * pct / 100)
            bar = '█' * filled + '░' * (bar_len - filled)
            remaining = max(0, target - current)
            print(f"\r  [{bar}] {pct:.1f}% - {format_duration(remaining)} remaining  ", end="", flush=True)

            if completed_at or current >= target:
                # Send terminal heartbeat
                try:
                    send_heartbeat(quest_id, token, stream_key, terminal=True)
                except HTTPError:
                    pass
                print(f"\n\n  Quest completed! Go claim your reward in Discord.")
                return

            time.sleep(20)

    except KeyboardInterrupt:
        print(f"\n\n  Stopped at {format_duration(current)}/{format_duration(target)}")
        print("  Progress is saved - run again to continue.")


def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        if token:
            print(f"Using saved token from {TOKEN_FILE.name}")
    if not token:
        print("To get your Discord token:")
        print("  1. Open Discord (desktop or browser)")
        print("  2. Press Ctrl+Shift+I to open DevTools")
        print("  3. Go to Network tab")
        print("  4. Type in any channel, look for any request")
        print("  5. Copy the 'authorization' header value")
        print()
        token = input("Paste your Discord token: ").strip()
        if not token:
            print("No token provided.")
            sys.exit(1)
        TOKEN_FILE.write_text(token)
        print("Token saved for next time.")

    while True:
        print("\nFetching quests...")
        try:
            quests = get_quests(token)
        except HTTPError as e:
            print(f"API error {e.code}: {e.read().decode()[:200]}")
            sys.exit(1)

        if not quests:
            print("No active quests found.")
            break

        # Filter to quests with play tasks that aren't completed
        game_quests = []
        for q in quests:
            tasks = find_play_tasks(q)
            if not tasks:
                continue
            user_status = q.get("userStatus", q.get("user_status", {})) or {}
            if user_status.get("completedAt") or user_status.get("completed_at"):
                continue
            game_quests.append(q)

        if not game_quests:
            # Show all quests for debugging
            print(f"Found {len(quests)} quest(s), but none are incomplete game-play quests.")
            for q in quests:
                config = q.get("config", {})
                messages = config.get("messages", {})
                name = messages.get("quest_name", q.get("id", "?"))
                tc = config.get("task_config_v2") or config.get("task_config") or {}
                tasks = tc.get("tasks", {})
                types = list(tasks.keys()) if isinstance(tasks, dict) else "?"
                status = q.get("userStatus", q.get("user_status", {})) or {}
                completed = status.get("completedAt") or status.get("completed_at")
                print(f"  - {name} | tasks: {types} | completed: {bool(completed)}")
            break

        # Select quest
        print(f"\nFound {len(game_quests)} game quest(s):\n")
        for i, q in enumerate(game_quests):
            messages = q.get("config", {}).get("messages", {})
            name = messages.get("quest_name", q.get("id", "?"))
            print(f"  [{i+1}] {name}")
        print(f"  [q] Quit")

        if len(game_quests) == 1:
            choice = input("\nStart quest? [1/q]: ").strip().lower()
        else:
            choice = input("\nSelect quest number: ").strip().lower()

        if choice == "q":
            break

        try:
            target = game_quests[int(choice) - 1]
        except (ValueError, IndexError):
            print("Invalid selection.")
            continue

        complete_quest_via_heartbeat(target, token)

    print("\nDone.")


if __name__ == "__main__":
    main()
