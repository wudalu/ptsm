from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml


TASK_HEADING_RE = re.compile(r"^###\s+(Task\b.*|里程碑\b.*)$")


@dataclass(frozen=True)
class PlanTask:
    title: str
    body: str
    prompt: str | None = None
    verify_commands: list[str] = field(default_factory=list)
    done_when: list[str] = field(default_factory=list)
    max_attempts: int | None = None


def parse_plan_tasks(plan_path: Path) -> list[PlanTask]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    tasks: list[PlanTask] = []
    current_title: str | None = None
    current_body: list[str] = []

    for line in lines:
        match = TASK_HEADING_RE.match(line)
        if match is not None:
            if current_title is not None:
                tasks.append(
                    _build_task(title=current_title, body_lines=current_body)
                )
            current_title = match.group(1).strip()
            current_body = []
            continue

        if current_title is not None:
            current_body.append(line)

    if current_title is not None:
        tasks.append(_build_task(title=current_title, body_lines=current_body))

    if not tasks:
        raise ValueError(f"No executable tasks found in plan: {plan_path}")

    return tasks


def _build_task(*, title: str, body_lines: list[str]) -> PlanTask:
    stripped_leading = list(body_lines)
    while stripped_leading and not stripped_leading[0].strip():
        stripped_leading.pop(0)

    metadata: dict[str, object] = {}
    if stripped_leading[:1] == ["```yaml"]:
        end_index = None
        for index, line in enumerate(stripped_leading[1:], start=1):
            if line.strip() == "```":
                end_index = index
                break
        if end_index is not None:
            raw_metadata = "\n".join(stripped_leading[1:end_index])
            parsed = yaml.safe_load(raw_metadata) or {}
            if not isinstance(parsed, dict):
                raise ValueError(f"Task metadata for '{title}' must be a mapping")
            metadata = parsed
            stripped_leading = stripped_leading[end_index + 1 :]

    while stripped_leading and not stripped_leading[0].strip():
        stripped_leading.pop(0)

    prompt = metadata.get("prompt")
    verify_commands = metadata.get("verify", [])
    done_when = metadata.get("done_when", [])
    max_attempts = metadata.get("max_attempts")

    return PlanTask(
        title=title,
        body="\n".join(stripped_leading).strip(),
        prompt=str(prompt) if prompt is not None else None,
        verify_commands=[str(command) for command in verify_commands],
        done_when=[str(item) for item in done_when],
        max_attempts=int(max_attempts) if max_attempts is not None else None,
    )
