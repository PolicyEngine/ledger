"""Ledger CLI entry point."""

from __future__ import annotations

import sys

__all__ = ["main"]


def main() -> None:
    """Dispatch Ledger commands without eager-loading legacy DB clients."""
    if sys.argv[1:2] in ([], ["-h"], ["--help"]):
        print(
            "Usage: ledger <command> [options]\n\n"
            "Common commands:\n"
            "  init\n"
            "  load\n"
            "  stats\n"
            "  validate-facts\n"
            "  validate-source-cells\n"
            "  export-consumer-facts\n\n"
            "Run `ledger <command> --help` for command-specific help."
        )
        return

    from ledger.cli import main as legacy_main

    legacy_main()


if __name__ == "__main__":
    main()
