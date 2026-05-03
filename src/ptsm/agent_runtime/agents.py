from __future__ import annotations

from typing import Any

from ptsm.infrastructure.llm.factory import DeterministicDraftBackend


class FengkuangDraftingAgent:
    """Drafting agent wrapper around a pluggable backend."""

    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend or DeterministicDraftBackend()
        self.provider_name = getattr(self._backend, "provider_name", "unknown")

    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        persona_prompt: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
        runtime_skill_contents: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._backend.generate(
            scene=scene,
            reflection_feedback=reflection_feedback,
            persona_prompt=persona_prompt,
            planner_prompt=planner_prompt,
            skill_contents=skill_contents,
            runtime_skill_contents=runtime_skill_contents,
        )
