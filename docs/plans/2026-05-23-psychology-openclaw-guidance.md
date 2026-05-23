# Psychology OpenClaw Guidance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When OpenClaw invokes PTSM for a modern psychology Xiaohongshu post, PTSM first returns productized topic directions derived from internal XHS hook research, without exposing research document paths or raw source notes to the user.

**Architecture:** Keep PTSM as the source of truth for psychology topic guidance and safety boundaries. Add a machine-readable guidance payload to `guide-post`, add a caller-aware preflight gate to `run-playbook`, and provide a thin OpenClaw skill wrapper that enforces the call order. Real generation and publishing continue through existing `run-playbook`.

**Tech Stack:** Python 3.12, Pydantic request models, argparse CLI, pytest, Markdown source-of-truth docs, OpenClaw `SKILL.md` wrapper instructions.

## Current Docs Summary

- `docs/index.md` says current source-of-truth docs must be read first; historical plans and research notes are context, not runtime truth.
- `docs/development-workflow.md` classifies this as major runtime/operator work because it changes a publish-adjacent caller protocol; it requires an isolated worktree, plan, task-level verification, source-of-truth docs updates, and a final harness gate.
- `docs/operations.md` currently defines `guide-post` as the read-only psychology pre-post guide and `run-playbook` as the generation/publish entry point.
- `docs/playbooks.md` and `docs/skills.md` already say `modern_psychology_post` has absorbed the 2026-05-23 hook research into domain-safe concepts such as 爱你老己、三明治拒绝法、丝瓜汤式沟通, and AI 陪伴边界.
- `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md` should remain internal research context. The OpenClaw-facing output must be summarized topic directions, not file paths or raw citations.

## Scope

- Add structured psychology topic directions to `guide-post` JSON and Markdown output.
- Add a `--caller openclaw` and `--guidance-ack` protocol for `run-playbook`.
- Gate OpenClaw calls to `modern_psychology_post` unless guidance has been acknowledged.
- Add a thin OpenClaw skill file that tells OpenClaw to call `guide-post` first, show directions, then call `run-playbook --guidance-ack`.
- Update source-of-truth docs for CLI/operator behavior and runtime/playbook implications.

## Non-Goals

- Do not add a new psychology playbook or domain.
- Do not perform live Xiaohongshu research on every OpenClaw call.
- Do not expose `docs/research/...` paths, source URLs, or research provenance in user-facing guidance.
- Do not change normal local CLI behavior for non-OpenClaw callers.
- Do not perform real publishing in tests or verification.

### Task 1: Guidance Payload

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write the failing test**

Add a test proving `run_guide_post()` returns `topic_guidance.status == "available"`, includes directions `boundary_sandwich_refusal`, `self_compassion_laoji`, `loofah_soup_communication`, and `ai_companion_boundary`, and does not serialize `docs/research`, `2026-05-23-xhs-viral-meme-product-hooks.md`, or `"source"`.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_run_guide_post_returns_productized_topic_directions_without_internal_sources -q
```

Expected: FAIL because `topic_guidance` does not exist yet.

**Step 3: Write minimal implementation**

In `guide_post.py`, add a small internal `PsychologyTopicDirection` model or constant list for four directions:

- `boundary_sandwich_refusal`
- `self_compassion_laoji`
- `loofah_soup_communication`
- `ai_companion_boundary`

Attach them to the `run_guide_post()` result under `topic_guidance`. Keep the payload user-facing and omit any research path or source field.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py -q
```

**done_when:** `guide-post` exposes user-facing topic directions and does not leak internal research paths or source labels.

### Task 2: OpenClaw Caller Gate

**Files:**
- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/interfaces/cli/test_main.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing tests**

Add tests proving parser and CLI pass `--caller openclaw --guidance-ack`, and `run_playbook()` returns `status == "topic_guidance_required"` for OpenClaw + `modern_psychology_post` when ack is missing. The gate result must contain topic directions and must not expose research paths.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest \
  tests/unit/application/use_cases/test_run_playbook.py::test_run_playbook_requires_topic_guidance_for_openclaw_psychology \
  tests/unit/interfaces/cli/test_main.py::test_run_playbook_cli_passes_openclaw_guidance_fields \
  tests/unit/test_bootstrap.py::test_build_parser_supports_run_playbook_openclaw_guidance_flags \
  -q
```

Expected: FAIL because the model, parser, and gate do not exist yet.

**Step 3: Write minimal implementation**

- Add `caller: str | None = None` and `guidance_ack: bool = False` to `PlaybookRequest`.
- Add `--caller` and `--guidance-ack` to `run-playbook`.
- Pass those fields from CLI into `PlaybookRequest`.
- In `run_playbook()`, after account/playbook resolution and before `run_store.start()`, if `caller == "openclaw"` and resolved playbook is `modern_psychology_post` and `guidance_ack` is false, return a read-only `topic_guidance_required` payload reusing the guidance builder from `guide_post.py`.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest \
  tests/unit/application/use_cases/test_run_playbook.py \
  tests/unit/interfaces/cli/test_main.py \
  tests/unit/test_bootstrap.py \
  -q
```

**done_when:** OpenClaw psychology generation is blocked until guidance is acknowledged, while normal CLI and non-psychology runs keep current behavior.

### Task 3: Thin OpenClaw Skill Wrapper

**Files:**
- Create: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Test: `tests/unit/docs/test_openclaw_skill.py`

**Step 1: Write the failing docs test**

Add a test asserting the skill file exists, instructs OpenClaw to call `guide-post` before `run-playbook`, includes `--caller openclaw` and `--guidance-ack`, and says not to show internal research paths or raw notes to users.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py -q
```

Expected: FAIL because the file does not exist.

**Step 3: Create the skill file**

Create a concise `SKILL.md` with front matter and operational instructions. The skill must stay thin: it calls PTSM and displays returned directions; it does not duplicate hook logic.

**Step 4: Run docs test**

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py -q
```

**done_when:** OpenClaw has an agent-readable wrapper that enforces the two-step flow without owning PTSM's psychology guidance logic.

### Task 4: Source-Of-Truth Docs

**Files:**
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/plans/2026-05-23-psychology-openclaw-guidance.md`

**Step 1: Update docs**

Document that `guide-post` returns productized psychology directions, OpenClaw callers must show directions first and then pass `--guidance-ack`, and `run-playbook --caller openclaw` returns `topic_guidance_required` if ack is missing.

**Step 2: Run docs tests**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_skill.py -q
```

**Step 3: Run docs-sync changed-path check**

Run:

```bash
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path src/ptsm/application/use_cases/guide_post.py \
  --changed-path src/ptsm/application/use_cases/run_playbook.py \
  --changed-path src/ptsm/application/models.py \
  --changed-path src/ptsm/interfaces/cli/main.py \
  --changed-path docs/runtime.md \
  --changed-path docs/playbooks.md \
  --changed-path docs/skills.md \
  --changed-path docs/operations.md
```

Expected: `status == "ok"`.

**done_when:** Source-of-truth docs match the new runtime/operator behavior.

### Task 5: End-To-End Verification

**Files:**
- No code changes.

**Step 1: Run targeted unit suite**

```bash
uv run pytest \
  tests/unit/application/use_cases/test_guide_post.py \
  tests/unit/application/use_cases/test_run_playbook.py \
  tests/unit/interfaces/cli/test_main.py \
  tests/unit/test_bootstrap.py \
  tests/unit/docs/test_openclaw_skill.py \
  -q
```

**Step 2: Smoke CLI guidance**

```bash
uv run python -m ptsm.bootstrap guide-post --scene "同事临时加需求，想练一版边界句" --non-interactive --format json
```

Expected: JSON contains `topic_guidance.directions` and no internal research path.

**Step 3: Smoke OpenClaw gate**

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --scene "同事临时加需求，想练一版边界句" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --publish-mode dry-run
```

Expected: JSON status is `topic_guidance_required`.

**Step 4: Smoke acknowledged dry-run**

```bash
DEFAULT_LLM_PROVIDER=deterministic uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --guidance-ack \
  --scene "同事临时加需求，想练一版三明治拒绝法边界句" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --publish-mode dry-run
```

Expected: JSON status is `completed` and publish result is dry-run.

**Step 5: Final gate**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** The two-step OpenClaw psychology flow works from CLI, tests pass, docs-sync passes, and harness-check passes.

## Implementation Evidence

- Baseline: `uv run pytest -q --ignore=tests/e2e` passed before implementation.
- Task 1 red: `test_run_guide_post_returns_productized_topic_directions_without_internal_sources` failed with `KeyError: 'topic_guidance'`.
- Task 1 green: `uv run pytest tests/unit/application/use_cases/test_guide_post.py -q` passed.
- Task 2 red: OpenClaw gate/parser tests failed because `--caller` / `--guidance-ack` and preflight gate did not exist.
- Task 2 green: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py -q` passed.
- Task 3 red: `uv run pytest tests/unit/docs/test_openclaw_skill.py -q` failed because `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` did not exist.
- Task 3 green: `uv run pytest tests/unit/docs/test_openclaw_skill.py -q` passed.
- Docs: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_skill.py -q` passed.
- Docs sync: explicit changed-path `uv run python -m ptsm.bootstrap docs-sync ...` returned `status: ok`.
- Targeted final tests: `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py tests/unit/docs/test_openclaw_skill.py -q` passed.
- CLI smoke: `guide-post --non-interactive --format json` returned `topic_guidance.directions` without internal research paths.
- CLI smoke: `run-playbook --caller openclaw` returned `topic_guidance_required` before workflow/publish.
- CLI smoke: `DEFAULT_LLM_PROVIDER=deterministic run-playbook --caller openclaw --guidance-ack ... --publish-mode dry-run` completed with dry-run publish result.
- Final gate: `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main` returned `status: ok`; its internal pytest command returned `0`.
