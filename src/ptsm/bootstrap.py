from __future__ import annotations

from typing import Sequence

from ptsm.config.logging import configure_logging
from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import build_parser, main as cli_main


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run the CLI after bootstrap initialization."""
    return cli_main(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize settings and logging before dispatching to the CLI."""
    settings = get_settings()
    configure_logging(settings)
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
