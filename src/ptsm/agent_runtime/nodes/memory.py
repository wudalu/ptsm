from __future__ import annotations

from typing import Any

from ptsm.agent_runtime.state import ExecutionState
from ptsm.infrastructure.memory.store import ExecutionMemoryStore


def build_memory_node(
    *, execution_memory: ExecutionMemoryStore, max_lessons: int = 3
):
    def memory(state: ExecutionState) -> ExecutionState:
        namespace = ("accounts", state["account_id"], "lessons")
        lessons = execution_memory.search(namespace=namespace)
        playbook_id = state["playbook_id"]
        hits = [
            _compact_lesson(item)
            for item in lessons
            if item.get("playbook_id") == playbook_id
        ][-max_lessons:]
        if not hits:
            return {
                "memory_hits": [],
                "runtime_skill_contents": list(state.get("runtime_skill_contents", [])),
                "runtime_skill_details": list(state.get("runtime_skill_details", [])),
            }

        return {
            "memory_hits": hits,
            "runtime_skill_contents": [
                *list(state.get("runtime_skill_contents", [])),
                _render_memory_context(hits),
            ],
            "runtime_skill_details": [
                *list(state.get("runtime_skill_details", [])),
                {
                    "skill_name": "recent_account_memory",
                    "resource_type": "runtime_context",
                    "resource_id": "recent_account_memory:runtime_context",
                    "source_path": None,
                    "content_preview": "# Recent Account Memory",
                },
            ],
        }

    return memory


def _compact_lesson(item: dict[str, object]) -> dict[str, Any]:
    return {
        "playbook_id": str(item.get("playbook_id", "")),
        "scene": _clip(item.get("scene"), limit=80),
        "title": _clip(item.get("title"), limit=60),
        "image_text": _clip(item.get("image_text"), limit=40),
        "hashtags": list(item.get("hashtags", []))
        if isinstance(item.get("hashtags"), list)
        else [],
        "final_body": _clip(item.get("final_body"), limit=120),
    }


def _render_memory_context(hits: list[dict[str, Any]]) -> str:
    lines = [
        "# Recent Account Memory",
        "Avoid repeating recent account posts:",
    ]
    for index, hit in enumerate(hits, start=1):
        lines.extend(
            [
                f"- recent_{index}_scene: {hit['scene'] or '(unknown)'}",
                f"  title: {hit['title'] or '(unknown)'}",
                f"  image_text: {hit['image_text'] or '(unknown)'}",
                f"  body_preview: {hit['final_body'] or '(empty)'}",
            ]
        )
    lines.append(
        "Use a different concrete object, opening sentence, repeated hotwords, and closing turn."
    )
    return "\n".join(lines)


def _clip(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
