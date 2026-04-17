from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.application.models import FengkuangRequest
from ptsm.application.use_cases.run_playbook import run_fengkuang_playbook
from ptsm.infrastructure.observability.run_store import RunStore


class FakeWorkflow:
    def __init__(self, artifact_path: Path):
        self.artifact_path = artifact_path

    def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None):
        return {
            "status": "completed",
            "artifact_path": str(self.artifact_path),
            "final_content": {
                "title": "打工人地铁生存实录",
                "image_text": "今日已疯",
                "body": f"{payload['scene']}，今天开会开到灵魂出窍，也算活着下班了。",
                "hashtags": ["#发疯文学", "#打工人日常"],
            },
        }


class CountingPublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish(self, **kwargs: object) -> dict[str, object]:
        self.calls += 1
        return {
            "status": "published",
            "platform": "xiaohongshu",
            "provider": "xiaohongshu_mcp",
            "artifact_path": kwargs["artifact_path"],
            "post_id": "post-123",
        }


def test_thread_memory_resume_reuses_publish_side_effect_across_invocations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )

    first_publisher = CountingPublisher()
    first = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周四晚上加班后回家",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-resume-001",
        publisher=first_publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    second_publisher = CountingPublisher()
    second = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周四晚上加班后回家",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-resume-001",
        publisher=second_publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert first_publisher.calls == 1
    assert second_publisher.calls == 0
    assert first["publish_result"] == second["publish_result"]
