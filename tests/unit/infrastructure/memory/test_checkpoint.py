from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.base import empty_checkpoint

from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver


def test_file_checkpoint_saver_persists_checkpoints_and_writes(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "checkpoints.pkl"
    saver = FileCheckpointSaver(path=checkpoint_path)
    version = saver.get_next_version(None, None)
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"draft": {"scene": "周二工位开会"}}
    checkpoint["channel_versions"] = {"draft": version}
    config = {"configurable": {"thread_id": "thread-fk-001", "checkpoint_ns": ""}}

    saved_config = saver.put(
        config,
        checkpoint,
        {"source": "unit-test"},
        {"draft": version},
    )
    saver.put_writes(
        saved_config,
        [("draft", {"body": "今天开会开到灵魂出窍。"})],
        task_id="task-1",
    )

    reloaded = FileCheckpointSaver(path=checkpoint_path)
    saved = reloaded.get_tuple(saved_config)

    assert checkpoint_path.exists()
    assert saved is not None
    assert saved.metadata["source"] == "unit-test"
    assert saved.checkpoint["channel_values"]["draft"]["scene"] == "周二工位开会"
    assert saved.pending_writes == [
        ("task-1", "draft", {"body": "今天开会开到灵魂出窍。"}),
    ]
