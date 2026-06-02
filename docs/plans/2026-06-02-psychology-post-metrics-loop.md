# Psychology Post Metrics Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a local post-performance recording and reporting loop so psychology XHS experiments can be judged by actual views, likes, saves, comments, and shares instead of dry-run quality alone.

**Architecture:** Keep this as a local observability/operator surface. Add one application use case that reads an existing run artifact, appends manual platform metrics to a JSONL store, and aggregates records by playbook, account, topic direction, checkpoint, or image style. The command is read/write only to local files and never publishes, logs in, opens a browser, or calls XHS MCP.

**Tech Stack:** Python 3.12, argparse CLI, JSON/JSONL under `outputs/artifacts/xhs-post-metrics/`, pytest, existing PTSM artifact metadata.

## Current Docs Summary

- `docs/development-workflow.md` treats new observability/operator surfaces as major work: use an isolated worktree, read source-of-truth docs, write a plan, define verification before implementation, update docs, and run `harness-check`.
- `docs/observability.md` says PTSM observability is local filesystem based: run summaries, artifacts, eval results, pattern snapshots, and harness reports. It explicitly lacks cross-account metrics reports and dashboards.
- `docs/operations/content-experiment-runbook.md` already defines the metrics operators should record at `2h`, `24h`, and `72h`: views, likes, collects, comments, shares, image format, comment quality notes, and rewrite decision. It also defines `interaction_score = likes + collects*2 + comments*4 + shares*6` and `interaction_rate = interaction_score / views`.
- `docs/operations.md` lists stable operator commands and says modern psychology experiments should use dry-run + eval first. It has no stable command for recording post-publish metrics.
- Existing artifacts persist useful grouping metadata: `playbook_id`, `account`, `scene`, `final_content.title`, `final_content.image_text`, `topic_selection.topic_direction_id`, `content_review.image_plan`, `publish_result`, and `run`.

## Task 1: Add failing use-case tests for metric recording

**Files:**
- Create: `tests/unit/application/use_cases/test_xhs_post_metrics.py`
- Create later: `src/ptsm/application/use_cases/xhs_post_metrics.py`

**Step 1: Write the failing tests**

Create a temp artifact with:

```python
artifact = {
    "playbook_id": "modern_psychology_post",
    "scene": "办公室下班后还是很紧绷",
    "account": {"account_id": "acct-psychology-local", "platform": "xiaohongshu"},
    "topic_selection": {"topic_direction_id": "sleep_recovery_shutdown_card"},
    "final_content": {
        "title": "下班后身体被拖回工位",
        "image_text": "5分钟给身体下班信号",
        "hashtags": ["#心理学", "#睡眠恢复"],
    },
    "content_review": {
        "image_plan": {"style": "iphone_notes", "role": "save_tool"}
    },
    "publish_result": {"status": "published", "post_id": "xhs-1"},
}
```

Assert `record_xhs_post_metrics(...)`:

- returns `status == "recorded"`
- writes one JSONL row to the requested store path
- includes `playbook_id`, `account_id`, `topic_direction_id`, `title`, `image_style`, `checkpoint`
- computes `interaction_score = likes + collects*2 + comments*4 + shares*6`
- computes `interaction_rate` and `like_rate` from `views`
- records `decision` and `notes`

Add validation tests:

- missing artifact returns `status == "error"` and does not create the store
- negative metrics raise or return a validation error
- unsupported checkpoint is rejected

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_xhs_post_metrics.py -q
```

Expected: FAIL because the module does not exist.

**Step 3: Implement minimal recording use case**

Create `src/ptsm/application/use_cases/xhs_post_metrics.py` with:

- `DEFAULT_POST_METRICS_PATH = Path("outputs/artifacts/xhs-post-metrics/metrics.jsonl")`
- `VALID_CHECKPOINTS = {"2h", "24h", "72h"}`
- `record_xhs_post_metrics(...) -> dict[str, object]`
- helper functions for artifact extraction, non-negative int validation, score/rate calculation, and JSONL append.

Do not mutate the original artifact. Use stable, serializable dictionaries.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_xhs_post_metrics.py -q
```

Expected: PASS.

`done_when:` A real artifact path plus manually entered XHS metrics can produce a durable, queryable local record with score/rate fields.

## Task 2: Add failing report tests

**Files:**
- Modify: `tests/unit/application/use_cases/test_xhs_post_metrics.py`
- Modify later: `src/ptsm/application/use_cases/xhs_post_metrics.py`

**Step 1: Write failing report tests**

Append three records to a temp metrics store:

- two `modern_psychology_post` rows at `24h` with `topic_direction_id = sleep_recovery_shutdown_card`
- one different psychology direction
- one non-psychology row that should be filtered out

Assert `summarize_xhs_post_metrics(...)` with `playbook_id="modern_psychology_post"`, `checkpoint="24h"`, and `group_by="topic_direction_id"`:

- returns `status == "ok"`
- filters to the expected rows
- groups by `sleep_recovery_shutdown_card`
- includes total/average views, likes, collects, comments, shares
- includes `avg_like_rate`, `avg_interaction_rate`, `avg_interaction_score`
- sorts the strongest group first
- marks groups with fewer than 3 rows as `sample_status == "needs_more_data"`

Add one test for `group_by="image_style"`.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_xhs_post_metrics.py::test_summarize_xhs_post_metrics_groups_psychology_direction_performance -q
```

Expected: FAIL because the summary function does not exist.

**Step 3: Implement summary use case**

Add:

- `summarize_xhs_post_metrics(input_path=..., playbook_id=None, account_id=None, checkpoint=None, group_by="topic_direction_id")`
- JSONL reader that skips blank lines
- filters for optional `playbook_id`, `account_id`, and `checkpoint`
- group keys from a conservative allowlist: `topic_direction_id`, `image_style`, `checkpoint`, `account_id`, `playbook_id`
- group aggregates and sorting by `avg_interaction_rate`, then `avg_views`

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_xhs_post_metrics.py -q
```

Expected: PASS.

`done_when:` Operators can answer which psychology topic direction or image style is performing better, while clearly seeing when sample size is still too small.

## Task 3: Add CLI commands

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write failing CLI tests**

In `tests/unit/interfaces/cli/test_main.py`, monkeypatch the new use-case functions and assert:

```bash
ptsm xhs-record-metrics --artifact artifact.json --checkpoint 24h --views 1000 --likes 80 --collects 30 --comments 5 --shares 2 --decision keep --notes "collects close to likes"
```

passes the parsed values to `record_xhs_post_metrics`.

Also assert:

```bash
ptsm xhs-metrics-report --playbook-id modern_psychology_post --checkpoint 24h --group-by topic_direction_id
```

calls `summarize_xhs_post_metrics`.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py::test_xhs_record_metrics_cli_passes_fields -q
```

Expected: FAIL because the command is not registered.

**Step 3: Implement CLI parser and dispatch**

Add imports and two subcommands:

- `xhs-record-metrics`
- `xhs-metrics-report`

Keep output as pretty JSON like other operator commands.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py::test_xhs_record_metrics_cli_passes_fields tests/unit/interfaces/cli/test_main.py::test_xhs_metrics_report_cli_passes_filters -q
```

Expected: PASS.

`done_when:` The metrics loop is reachable through stable CLI commands without XHS side effects.

## Task 4: Update source-of-truth docs

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/content-experiment-runbook.md`
- Modify: `docs/harness-engineering.md` if tests or gates are documented there
- Modify: `docs/skills.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Update external operator skill: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`

**Step 1: Update docs**

Document:

- metrics records live in `outputs/artifacts/xhs-post-metrics/metrics.jsonl`
- `xhs-record-metrics` records manual post metrics for an artifact
- `xhs-metrics-report` aggregates records by topic direction, image style, checkpoint, account, or playbook
- reports are local evidence and do not prove a strategy until enough comparable posts exist
- for psychology, use `--playbook-id modern_psychology_post --checkpoint 24h --group-by topic_direction_id` to compare directions such as `sleep_recovery_shutdown_card`
- the repo OpenClaw skill and local Codex psychology skill should route "提高浏览量/点赞" and post-publish review requests to the metrics loop instead of inventing performance claims

**Step 2: Run docs checks**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/xhs_post_metrics.py --changed-path src/ptsm/interfaces/cli/main.py --changed-path docs/observability.md --changed-path docs/operations.md --changed-path docs/operations/content-experiment-runbook.md
```

Expected: PASS / status ok.

`done_when:` Operator and observability docs explain how to collect real performance evidence for psychology experiments.

## Task 5: End-to-end verification

**Files:**
- No production edits expected.

**Step 1: Run targeted tests**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_xhs_post_metrics.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS.

**Step 2: Run CLI smoke with a generated temp fixture**

Use a temp artifact under `/tmp` or `outputs/artifacts/xhs-post-metrics-smoke/` and run:

```bash
uv run python -m ptsm.bootstrap xhs-record-metrics --artifact <artifact.json> --checkpoint 24h --views 1000 --likes 80 --collects 60 --comments 8 --shares 2 --output-path <metrics.jsonl>
uv run python -m ptsm.bootstrap xhs-metrics-report --playbook-id modern_psychology_post --checkpoint 24h --group-by topic_direction_id --input-path <metrics.jsonl>
```

Expected: first command returns `status == "recorded"` and second returns `status == "ok"` with `sleep_recovery_shutdown_card`.

**Step 3: Run harness gate**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Expected: status ok. If warnings appear from stale historical run artifacts, confirm docs-sync, pytest, and eval required failures are still ok.

`done_when:` The local metric loop is tested, documented, smoke-tested through CLI, and harness-checked. This does not complete the overall growth objective until real posts have been published and enough metrics have been recorded.
