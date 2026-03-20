from __future__ import annotations

from pathlib import Path

from codex_plan_runner.parser import parse_plan_tasks


def test_parse_plan_tasks_supports_task_and_milestone_headings(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "# Demo Plan",
                "",
                "### Task 1: Build parser",
                "",
                "- create parser",
                "",
                "### 里程碑 M1：Runtime Kernel",
                "",
                "- build runtime",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tasks = parse_plan_tasks(plan_path)

    assert [task.title for task in tasks] == [
        "Task 1: Build parser",
        "里程碑 M1：Runtime Kernel",
    ]
    assert "- create parser" in tasks[0].body
    assert "- build runtime" in tasks[1].body


def test_parse_plan_tasks_extracts_yaml_metadata(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "# Demo Plan",
                "",
                "### Task 1: Build parser",
                "",
                "```yaml",
                "prompt: |",
                "  Implement parser carefully.",
                "verify:",
                "  - uv run pytest tests/test_parser.py -q",
                "done_when:",
                "  - parser handles metadata",
                "max_attempts: 5",
                "```",
                "",
                "Implementation notes stay here.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tasks = parse_plan_tasks(plan_path)

    assert len(tasks) == 1
    assert tasks[0].prompt == "Implement parser carefully.\n"
    assert tasks[0].verify_commands == ["uv run pytest tests/test_parser.py -q"]
    assert tasks[0].done_when == ["parser handles metadata"]
    assert tasks[0].max_attempts == 5
    assert "Implementation notes stay here." in tasks[0].body
    assert "prompt:" not in tasks[0].body
