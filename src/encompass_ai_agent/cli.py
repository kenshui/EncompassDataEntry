from __future__ import annotations

import argparse
from dataclasses import replace
import sys

from .agent import EncompassAIAgent
from .config import load_config
from .logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Encompass AI document extraction agent."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Override the number of days to scan for created or modified loans.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and log results without updating Encompass loan fields.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging()

    try:
        config = load_config()
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    config = replace(
        config,
        lookback_days=args.lookback_days if args.lookback_days is not None else config.lookback_days,
        dry_run=True if args.dry_run else config.dry_run,
    )

    agent = EncompassAIAgent(config)
    result = agent.run()
    print(
        "Agent completed: "
        f"{result.loans_scanned} loans, "
        f"{result.attachments_seen} attachments, "
        f"{result.attachments_processed} documents processed, "
        f"{result.field_updates_failed} failed."
    )
    return 0 if result.field_updates_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
