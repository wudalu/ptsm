from __future__ import annotations

from pathlib import Path

from ptsm.infrastructure.memory.store import FileExecutionMemory


def test_file_execution_memory_persists_records_across_instances(
    tmp_path: Path,
) -> None:
    memory_path = tmp_path / "execution-memory.json"
    namespace = ("accounts", "acct-fk-local", "lessons")
    lesson = {
        "playbook_id": "fengkuang_daily_post",
        "scene": "周一早高峰地铁通勤",
        "attempt_count": 2,
    }

    store = FileExecutionMemory(path=memory_path)
    store.record(namespace=namespace, item=lesson)

    reloaded = FileExecutionMemory(path=memory_path)

    assert memory_path.exists()
    assert reloaded.search(namespace=namespace) == [lesson]
