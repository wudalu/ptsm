from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from collections import Counter
from uuid import uuid4


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    run_dir: Path
    events_path: Path
    summary_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "events_path": str(self.events_path),
            "summary_path": str(self.summary_path),
        }


class RunStore:
    """Persist per-run metadata and event streams on the local filesystem."""

    def __init__(self, base_dir: Path | str = ".ptsm/runs") -> None:
        self.base_dir = Path(base_dir)

    def start(
        self,
        *,
        command: str,
        account_id: str,
        platform: str,
        playbook_id: str | None = None,
    ) -> RunHandle:
        run_id = self._generate_run_id()
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        handle = RunHandle(
            run_id=run_id,
            run_dir=run_dir,
            events_path=run_dir / "events.jsonl",
            summary_path=run_dir / "summary.json",
        )
        summary = {
            **handle.to_dict(),
            "status": "running",
            "command": command,
            "account_id": account_id,
            "platform": platform,
            "playbook_id": playbook_id,
            "started_at": self._timestamp(),
        }
        handle.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.append_event(
            handle.run_id,
            event="run_started",
            payload={
                "command": command,
                "account_id": account_id,
                "platform": platform,
                "playbook_id": playbook_id,
            },
        )
        return handle

    def append_event(
        self,
        run_id: str,
        *,
        event: str,
        step: str | None = None,
        status: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        record: dict[str, object] = {
            "timestamp": self._timestamp(),
            "run_id": run_id,
            "event": event,
        }
        if step:
            record["step"] = step
        if status:
            record["status"] = status
        if payload:
            record.update(payload)

        handle = self._handle(run_id)
        with handle.events_path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def finish(
        self,
        run_id: str,
        *,
        status: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        handle = self._handle(run_id)
        summary = json.loads(handle.summary_path.read_text(encoding="utf-8"))
        summary["status"] = status
        summary["finished_at"] = self._timestamp()
        if payload:
            summary.update(payload)
        handle.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.append_event(
            run_id,
            event="run_finished",
            status=status,
            payload=payload,
        )
        return summary

    def read_summary(self, run_id: str) -> dict[str, object]:
        handle = self._handle(run_id)
        return json.loads(handle.summary_path.read_text(encoding="utf-8"))

    def read_events(self, run_id: str) -> list[dict[str, object]]:
        handle = self._handle(run_id)
        if not handle.events_path.exists():
            return []
        return [
            json.loads(line)
            for line in handle.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def list_runs(
        self,
        *,
        account_id: str | None = None,
        platform: str | None = None,
        playbook_id: str | None = None,
        status: str | None = None,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        summaries = list(
            self._iter_summaries(
                account_id=account_id,
                platform=platform,
                playbook_id=playbook_id,
                status=status,
            )
        )
        summaries.sort(key=lambda item: str(item.get("started_at", "")), reverse=True)
        if limit is None:
            return summaries
        return summaries[:limit]

    def list_events(
        self,
        *,
        account_id: str | None = None,
        platform: str | None = None,
        playbook_id: str | None = None,
        run_status: str | None = None,
        event: str | None = None,
        step: str | None = None,
        event_status: str | None = None,
        limit: int | None = 50,
    ) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        for summary in self._iter_summaries(
            account_id=account_id,
            platform=platform,
            playbook_id=playbook_id,
            status=run_status,
        ):
            for record in self.read_events(str(summary["run_id"])):
                if event is not None and record.get("event") != event:
                    continue
                if step is not None and record.get("step") != step:
                    continue
                if event_status is not None and record.get("status") != event_status:
                    continue
                events.append(
                    {
                        **record,
                        "account_id": summary.get("account_id"),
                        "platform": summary.get("platform"),
                        "playbook_id": summary.get("playbook_id"),
                        "command": summary.get("command"),
                        "run_status": summary.get("status"),
                    }
                )

        events.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
        if limit is None:
            return events
        return events[:limit]

    def aggregate_events(
        self,
        *,
        group_by: str,
        account_id: str | None = None,
        platform: str | None = None,
        playbook_id: str | None = None,
        run_status: str | None = None,
        event: str | None = None,
        step: str | None = None,
        event_status: str | None = None,
    ) -> dict[str, int]:
        counts: Counter[str] = Counter()
        events = self.list_events(
            account_id=account_id,
            platform=platform,
            playbook_id=playbook_id,
            run_status=run_status,
            event=event,
            step=step,
            event_status=event_status,
            limit=None,
        )
        for record in events:
            value = record.get(group_by)
            counts["unknown" if value in {None, ""} else str(value)] += 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def _handle(self, run_id: str) -> RunHandle:
        run_dir = self.base_dir / run_id
        return RunHandle(
            run_id=run_id,
            run_dir=run_dir,
            events_path=run_dir / "events.jsonl",
            summary_path=run_dir / "summary.json",
        )

    def _iter_summaries(
        self,
        *,
        account_id: str | None = None,
        platform: str | None = None,
        playbook_id: str | None = None,
        status: str | None = None,
    ):
        for summary_path in self.base_dir.glob("*/summary.json"):
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if account_id is not None and summary.get("account_id") != account_id:
                continue
            if platform is not None and summary.get("platform") != platform:
                continue
            if playbook_id is not None and summary.get("playbook_id") != playbook_id:
                continue
            if status is not None and summary.get("status") != status:
                continue
            yield summary

    def _generate_run_id(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{uuid4().hex[:8]}"

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
