from __future__ import annotations

from pathlib import Path

from ptsm.plan_runner.parser import parse_plan_tasks


def test_parse_plan_tasks_supports_task_headings(tmp_path: Path) -> None:
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
                "### Task 2: Build runner",
                "",
                "- create runner",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tasks = parse_plan_tasks(plan_path)

    assert [task.title for task in tasks] == [
        "Task 1: Build parser",
        "Task 2: Build runner",
    ]
    assert "- create parser" in tasks[0].body
    assert "- create runner" in tasks[1].body


def test_parse_plan_tasks_supports_milestone_headings(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "# Demo Plan",
                "",
                "### 里程碑 M0：工程脚手架",
                "",
                "- bootstrap project",
                "",
                "#### 子说明",
                "",
                "- keep nested content",
                "",
                "### 里程碑 M1：Runtime Kernel",
                "",
                "- add runtime loop",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tasks = parse_plan_tasks(plan_path)

    assert [task.title for task in tasks] == [
        "里程碑 M0：工程脚手架",
        "里程碑 M1：Runtime Kernel",
    ]
    assert "#### 子说明" in tasks[0].body
    assert "- add runtime loop" in tasks[1].body


def test_parse_plan_tasks_extracts_structured_task_metadata(tmp_path: Path) -> None:
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
                "  - uv run pytest tests/unit/plan_runner/test_parser.py -q",
                "done_when:",
                "  - metadata block is parsed",
                "max_attempts: 5",
                "```",
                "",
                "Implementation notes stay in the task body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tasks = parse_plan_tasks(plan_path)

    assert len(tasks) == 1
    assert tasks[0].prompt == "Implement parser carefully.\n"
    assert tasks[0].verify_commands == [
        "uv run pytest tests/unit/plan_runner/test_parser.py -q"
    ]
    assert tasks[0].done_when == ["metadata block is parsed"]
    assert tasks[0].max_attempts == 5
    assert "Implementation notes stay in the task body." in tasks[0].body
    assert "prompt:" not in tasks[0].body
