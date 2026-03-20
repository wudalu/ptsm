from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ptsm.playbooks.registry import PlaybookDefinition, PlaybookRegistry


@dataclass(frozen=True)
class LoadedPlaybook:
    """Playbook definition plus referenced markdown assets."""

    definition: PlaybookDefinition
    planner_prompt: str
    reflection_prompt: str
    playbook_dir: Path


class PlaybookLoader:
    """Load playbook markdown assets alongside the YAML definition."""

    def __init__(self, playbook_root: Path):
        self._registry = PlaybookRegistry(playbook_root=playbook_root)

    def load(self, playbook_id: str) -> LoadedPlaybook:
        for definition in self._registry.list_playbooks():
            if definition.playbook_id == playbook_id:
                assert definition.source_path is not None
                playbook_dir = definition.source_path.parent
                return LoadedPlaybook(
                    definition=definition,
                    planner_prompt=(playbook_dir / "planner.md").read_text(encoding="utf-8"),
                    reflection_prompt=(playbook_dir / "reflection.md").read_text(encoding="utf-8"),
                    playbook_dir=playbook_dir,
                )
        raise LookupError(f"Unknown playbook: {playbook_id}")
