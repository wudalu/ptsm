from __future__ import annotations

from pathlib import Path
import re

from ptsm.skills.contracts import SkillSpec


class SkillRegistry:
    """Discover `SKILL.md` files under the configured skill root."""

    def __init__(self, skill_root: Path):
        self.skill_root = skill_root

    def list_skills(self) -> list[SkillSpec]:
        specs = [
            _parse_skill_markdown(path)
            for path in sorted(self.skill_root.rglob("SKILL.md"))
        ]
        return sorted(specs, key=lambda item: (item.display_order, item.skill_name))


def _parse_skill_markdown(path: Path) -> SkillSpec:
    text = path.read_text(encoding="utf-8")
    front_matter, body = _split_front_matter(text)
    skill_name = _normalize_skill_name(front_matter.get("skill_name", path.parent.name))
    display_name = front_matter.get("display_name", skill_name.replace("_", " ").title())
    description = front_matter.get("description", _extract_body_description(body))
    display_order = int(front_matter.get("display_order", "1000"))
    return SkillSpec(
        skill_name=skill_name,
        display_name=display_name,
        short_description=description,
        display_order=display_order,
        source_path=path,
        metadata=front_matter,
    )


def _split_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, text

    front_lines = lines[1:end_index]
    body_lines = lines[end_index + 1 :]
    return _parse_front_matter(front_lines), "\n".join(body_lines)


def _parse_front_matter(lines: list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def _extract_body_description(body: str) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def _normalize_skill_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")

