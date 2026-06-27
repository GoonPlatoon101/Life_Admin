from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from agent import Agent
from config import load_config
from life_admin.scanner import EmailScanRequest, scan_email_messages
from life_admin.scanner.email_agent_runner import process_email_source_items
from llm_service import create_client
from prompts import build_system_prompt


DEFAULT_STATE_FILE = Path(".Lifeadmin") / "email_seen.json"


def main() -> None:
    config = load_config()
    args = _parse_args()
    access_token = args.access_token or os.getenv("EMAIL_ACCESS_TOKEN")
    if not access_token:
        raise SystemExit("Missing email access token. Pass --access-token or set EMAIL_ACCESS_TOKEN.")

    agent = Agent(
        config=config,
        client=create_client(config),
        system_prompt=build_system_prompt(config),
    )
    state_file = Path(args.state_file)
    seen_keys = _load_seen_keys(state_file)

    while True:
        request = EmailScanRequest(
            provider=args.provider,
            access_token=access_token,
            query=args.query,
            max_results=args.max_results,
        )
        scan = scan_email_messages(request)
        processed = process_email_source_items(agent, scan["source_items"], seen_keys=seen_keys)
        _save_seen_keys(state_file, seen_keys)

        print(
            json.dumps(
                {
                    "scanned": scan["count"],
                    "processed_new": len(processed),
                    "results": processed,
                },
                indent=2,
            )
        )

        if args.once:
            break
        time.sleep(args.interval_seconds)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll email and run new messages through LifeAdmin.")
    parser.add_argument("--provider", choices=["google", "outlook"], default=os.getenv("EMAIL_PROVIDER", "google"))
    parser.add_argument("--access-token", default=None)
    parser.add_argument("--query", default=os.getenv("EMAIL_QUERY", "newer_than:1d"))
    parser.add_argument("--max-results", type=int, default=int(os.getenv("EMAIL_MAX_RESULTS", "10")))
    parser.add_argument("--interval-seconds", type=int, default=int(os.getenv("EMAIL_POLL_SECONDS", "60")))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE))
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def _load_seen_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data}


def _save_seen_keys(path: Path, seen_keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen_keys), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
