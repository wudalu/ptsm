from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PlaybookDefinition:
    """Structured playbook definition loaded from YAML."""

    playbook_id: str
    version: str
    domain: str
    platforms: list[str]
    required_skills: list[str]
    optional_skills: list[str] = field(default_factory=list)
    reflection: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None


class PlaybookRegistry:
    """Discover and select playbooks based on domain and platform."""

    def __init__(self, playbook_root: Path):
        self.playbook_root = playbook_root
        self._playbooks = self._load_playbooks()

    def select(self, domain: str, platform: str) -> PlaybookDefinition:
        for playbook in self._playbooks:
            if playbook.domain == domain and platform in playbook.platforms:
                return playbook
        raise LookupError(f"No playbook for domain={domain!r}, platform={platform!r}")

    def list_playbooks(self) -> list[PlaybookDefinition]:
        return list(self._playbooks)

    def _load_playbooks(self) -> list[PlaybookDefinition]:
        playbooks: list[PlaybookDefinition] = []
        for path in sorted(self.playbook_root.rglob("playbook.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            playbooks.append(
                PlaybookDefinition(
                    playbook_id=payload["playbook_id"],
                    version=str(payload["version"]),
                    domain=payload["domain"],
                    platforms=list(payload["platforms"]),
                    required_skills=list(payload["required_skills"]),
                    optional_skills=list(payload.get("optional_skills", [])),
                    reflection=dict(payload.get("reflection", {})),
                    source_path=path,
                )
            )
        return playbooks

