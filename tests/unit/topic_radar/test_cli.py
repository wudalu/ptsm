from __future__ import annotations

import sys

import pytest

from topic_radar.cli import main


class TestCLIBasic:
    def test_no_args_shows_help(self, capsys):
        # Simulate no subcommand
        sys.argv = ["topic-radar"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "scan" in captured.out.lower()

    def test_scan_help(self, capsys):
        sys.argv = ["topic-radar", "scan", "--help"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "--platforms" in captured.out

    def test_teardown_help(self, capsys):
        sys.argv = ["topic-radar", "teardown", "--help"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "feed_id" in captured.out
