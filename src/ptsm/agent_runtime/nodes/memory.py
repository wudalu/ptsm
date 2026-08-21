from __future__ import annotations

import re
from typing import Any

from ptsm.agent_runtime.state import ExecutionState
from ptsm.infrastructure.memory.store import ExecutionMemoryStore


_MODERN_PSYCHOLOGY_PLAYBOOK_ID = "modern_psychology_post"
_MODERN_PSYCHOLOGY_MEMORY_LESSONS = 12
_INNER_CAROUSEL_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def build_memory_node(
    *,
    execution_memory: ExecutionMemoryStore,
    max_lessons: int = 3,
    evidence_gated: bool = False,
):
    def memory(state: ExecutionState) -> ExecutionState:
        if evidence_gated:
            # AI-tech evidence contracts are intentionally self-contained.
            # A historical title/body can contain unverified claims or raw
            # provenance, so it must never become drafting context for this run.
            return {
                "memory_hits": [],
                "runtime_skill_contents": list(state.get("runtime_skill_contents", [])),
                "runtime_skill_details": list(state.get("runtime_skill_details", [])),
            }
        namespace = ("accounts", state["account_id"], "lessons")
        lessons = execution_memory.search(namespace=namespace)
        playbook_id = state["playbook_id"]
        matching_lessons = [
            item for item in lessons if item.get("playbook_id") == playbook_id
        ]
        hits = [
            _compact_lesson(item)
            for item in matching_lessons
        ][-max_lessons:]
        recent_inner_fingerprints = (
            _recent_modern_psychology_inner_fingerprints(matching_lessons)
            if playbook_id == _MODERN_PSYCHOLOGY_PLAYBOOK_ID
            else []
        )
        if not hits and not recent_inner_fingerprints:
            return {
                "memory_hits": [],
                "runtime_skill_contents": list(state.get("runtime_skill_contents", [])),
                "runtime_skill_details": list(state.get("runtime_skill_details", [])),
                **_psychology_fingerprint_state(recent_inner_fingerprints),
            }

        runtime_skill_contents = list(state.get("runtime_skill_contents", []))
        runtime_skill_details = list(state.get("runtime_skill_details", []))
        if hits:
            runtime_skill_contents.append(_render_memory_context(hits))
            runtime_skill_details.append(
                {
                    "skill_name": "recent_account_memory",
                    "resource_type": "runtime_context",
                    "resource_id": "recent_account_memory:runtime_context",
                    "source_path": None,
                    "content_preview": "# Recent Account Memory",
                }
            )
        if recent_inner_fingerprints:
            runtime_skill_contents.append(
                _render_psychology_carousel_fingerprint_context(
                    recent_inner_fingerprints
                )
            )
            runtime_skill_details.append(
                {
                    "skill_name": "recent_psychology_carousel_fingerprints",
                    "resource_type": "runtime_context",
                    "resource_id": "recent_psychology_carousel_fingerprints:runtime_context",
                    "source_path": None,
                    "content_preview": "# Recent Psychology Carousel Fingerprints",
                }
            )
        return {
            "memory_hits": hits,
            "runtime_skill_contents": runtime_skill_contents,
            "runtime_skill_details": runtime_skill_details,
            **_psychology_fingerprint_state(recent_inner_fingerprints),
        }

    return memory


def _compact_lesson(item: dict[str, object]) -> dict[str, Any]:
    compact = {
        "playbook_id": str(item.get("playbook_id", "")),
        "scene": _clip(item.get("scene"), limit=80),
        "title": _clip(item.get("title"), limit=60),
        "image_text": _clip(item.get("image_text"), limit=40),
        "hashtags": list(item.get("hashtags", []))
        if isinstance(item.get("hashtags"), list)
        else [],
        "final_body": _clip(item.get("final_body"), limit=120),
    }
    fingerprint = _valid_inner_carousel_fingerprint(
        item.get("psychology_carousel_inner_fingerprint")
    )
    if fingerprint:
        compact["psychology_carousel_inner_fingerprint"] = fingerprint
    return compact


def _render_memory_context(hits: list[dict[str, Any]]) -> str:
    lines = [
        "# Recent Account Memory",
        "Avoid repeating recent account posts:",
    ]
    for index, hit in enumerate(hits, start=1):
        rendered_hit = _memory_prompt_hit(hit)
        lines.extend(
            [
                f"- recent_{index}_scene: {rendered_hit['scene'] or '(unknown)'}",
                f"  title: {rendered_hit['title'] or '(unknown)'}",
                f"  image_text: {rendered_hit['image_text'] or '(unknown)'}",
                f"  body_preview: {rendered_hit['final_body'] or '(empty)'}",
            ]
        )
    lines.append(
        "Use a different concrete object, opening sentence, repeated hotwords, and closing turn."
    )
    return "\n".join(lines)


def _memory_prompt_hit(hit: dict[str, Any]) -> dict[str, str]:
    if hit.get("playbook_id") != "reddit_curation_daily_post":
        return {
            "scene": str(hit.get("scene", "")),
            "title": str(hit.get("title", "")),
            "image_text": str(hit.get("image_text", "")),
            "final_body": str(hit.get("final_body", "")),
        }
    return {
        "scene": "same internal-source curation scene",
        "title": _strip_reddit_source_markers(hit.get("title", "")),
        "image_text": _strip_reddit_source_markers(hit.get("image_text", "")),
        "final_body": _strip_reddit_source_markers(hit.get("final_body", "")),
    }


def _recent_modern_psychology_inner_fingerprints(
    lessons: list[dict[str, object]],
) -> list[str]:
    fingerprints: list[str] = []
    for lesson in reversed(lessons):
        fingerprint = _valid_inner_carousel_fingerprint(
            lesson.get("psychology_carousel_inner_fingerprint")
        )
        if not fingerprint:
            continue
        fingerprints.append(fingerprint)
        if len(fingerprints) == _MODERN_PSYCHOLOGY_MEMORY_LESSONS:
            break
    return list(reversed(fingerprints))


def _render_psychology_carousel_fingerprint_context(
    fingerprints: list[str],
) -> str:
    lines = [
        "# Recent Psychology Carousel Fingerprints",
        "Avoid reusing these rendered inner-card identities:",
        *(f"- inner_fingerprint: {fingerprint}" for fingerprint in fingerprints),
    ]
    return "\n".join(lines)


def _psychology_fingerprint_state(fingerprints: list[str]) -> dict[str, object]:
    if not fingerprints:
        return {}
    return {"recent_psychology_carousel_inner_fingerprints": fingerprints}


def _strip_reddit_source_markers(value: object) -> str:
    text = str(value or "")
    replacements = {
        "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度": "同一选题方向",
        "从Reddit上AI英文讨论里选一个适合中文读者的角度": "同一选题方向",
        "这个Reddit讨论": "这个热点",
        "Reddit英文讨论里": "",
        "Reddit 英文讨论里": "",
        "Reddit 上": "",
        "Reddit上": "",
        "#Reddit": "",
        "Reddit": "",
        "reddit": "",
        "英文讨论": "热点讨论",
        "翻成中文": "换个说法",
        "这次选的是": "",
        "source_url": "",
        "reddit.com": "",
        "r/": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split()).strip()


def _clip(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _valid_inner_carousel_fingerprint(value: object) -> str:
    fingerprint = value.strip() if isinstance(value, str) else ""
    if _INNER_CAROUSEL_FINGERPRINT_PATTERN.fullmatch(fingerprint) is None:
        return ""
    return fingerprint
