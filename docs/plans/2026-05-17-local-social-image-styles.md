# Local Social Image Styles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add high-quality local screenshot-style image generation for XHS posts,
starting with iPhone Notes-like covers and WeChat chat transcript-like covers.

**Architecture:** Keep rendering inside `src/ptsm/infrastructure/images`, using
Pillow and the existing local fallback image backend. `run-playbook` should pass
a local image style into the backend only when external image providers are not
configured, while artifacts record the chosen style for review and replay.

**Tech Stack:** Python 3.12, Pillow, OpenCV-based image tests, existing
`run-playbook` CLI and artifact metadata.

## Current Docs Summary

- `AGENTS.md` and `docs/development-workflow.md` require major runtime-visible
  work to happen in an isolated branch/worktree, with a plan, task-level
  verification, source-of-truth docs updates, and final `harness-check`.
- `docs/harness-engineering.md` says local generated images are part of the
  deterministic harness surface; verification must be machine-checkable, not
  only visually asserted by an operator.
- `docs/architecture.md` keeps provider-backed or local image generation in
  `infrastructure/images`, with `application/use_cases/run_playbook.py`
  orchestrating image creation before publish. Runtime graph nodes should not
  own image rendering details.
- `docs/runtime.md` and `docs/observability.md` already describe a local
  `local_note_card` fallback that writes image metadata into artifacts.

## Design

The current `NoteCardImageBackend` remains the local provider. It will accept
`style` from its JSON prompt and route rendering to one of three deterministic
layouts:

- `xhs_note_card_v1`: existing warm notes-card cover, kept as default.
- `iphone_notes_v1`: iPhone Notes-like screenshot with status bar, yellow
  notes accent, timestamp, clean note body, and no hashtags/watermarks.
- `wechat_chat_v1`: WeChat chat transcript-like screenshot with status bar,
  conversation header, incoming/outgoing bubbles, and a final prompt bubble.

The new layouts are intentionally "inspired by" familiar interfaces rather than
pixel-copying official UI. They must be clean, high-resolution, nonblank,
3:4-friendly, and readable with Chinese text.

`PlaybookRequest` gets `local_image_style`, exposed by CLI as
`--local-image-style {note_card,iphone_notes,wechat_chat}`. The field is only
used by the local fallback renderer. External Jimeng/Bailian image providers
continue receiving the existing prompt path.

## Task 1: Add Local Renderer Styles

**Files:**

- Modify: `src/ptsm/infrastructure/images/note_card_backend.py`
- Modify: `tests/unit/infrastructure/images/test_note_card_backend.py`

**Step 1: Write failing tests**

Add tests for:

- `style: "iphone_notes_v1"` returns `style == "iphone_notes_v1"`, writes a
  nonblank `1080x1440` PNG, and contains varied visual regions.
- `style: "wechat_chat_v1"` returns `style == "wechat_chat_v1"`, writes a
  nonblank `1080x1440` PNG, and contains varied visual regions.
- Unknown styles fall back to `xhs_note_card_v1` so old callers remain safe.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q
```

Expected: tests fail because only `xhs_note_card_v1` is implemented.

**Step 3: Implement styles**

In `NoteCardImageBackend.generate()`:

- parse `payload["style"]`
- normalize aliases:
  - `note_card` -> `xhs_note_card_v1`
  - `iphone_notes` -> `iphone_notes_v1`
  - `wechat_chat` -> `wechat_chat_v1`
- dispatch to private renderers:
  - `_render_note_card()`
  - `_render_iphone_notes()`
  - `_render_wechat_chat()`
- return the effective style in metadata.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q
```

Expected: pass.

**done_when:** Local image backend can render all three styles with deterministic
metadata and nonblank 3:4 PNG output.

## Task 2: Wire Style Through Run Playbook And CLI

**Files:**

- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add tests that:

- CLI parses `--local-image-style iphone_notes` into
  `PlaybookRequest.local_image_style`.
- `run_fengkuang_playbook(... auto_generate_images=True,
  local_image_style="wechat_chat")` uses the local fallback and records
  `image_generation.style == "wechat_chat_v1"`.
- `_build_note_card_image_payload()` includes the requested local image style.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py -q
```

Expected: fail because the request and CLI do not expose this field.

**Step 3: Implement wiring**

- Add `local_image_style: str | None = None` to `PlaybookRequest`.
- Add `--local-image-style` to both `run-fengkuang` and `run-playbook`.
- Pass the field into `_build_note_card_image_payload()`.
- Keep external image provider flow unchanged.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py -q
```

Expected: pass.

**done_when:** Operators can request iPhone Notes or WeChat chat-style local
covers from the normal CLI path, and artifacts record the effective renderer
style.

## Task 3: Docs And Smoke Verification

**Files:**

- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/harness-engineering.md`

**Step 1: Update docs**

Document:

- `--local-image-style note_card|iphone_notes|wechat_chat`
- local renderer style metadata values
- external providers remain preferred when configured
- local styles are deterministic and safe for dry-runs

**Step 2: Generate sample artifacts**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "周一早上刚坐到工位，领导连发三个在吗" \
  --account-id acct-fk-local \
  --playbook-id fengkuang_daily_post \
  --publish-mode dry-run \
  --auto-generate-image \
  --local-image-style iphone_notes

uv run python -m ptsm.bootstrap run-playbook \
  --scene "周一早上刚坐到工位，领导连发三个在吗" \
  --account-id acct-fk-local \
  --playbook-id fengkuang_daily_post \
  --publish-mode dry-run \
  --auto-generate-image \
  --local-image-style wechat_chat
```

Expected: both return `status == completed`, `image_generation.provider ==
"local_note_card"`, and `image_generation.style` matches the requested style.

**Step 3: Final gates**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py -q
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict
```

Expected: all pass.

**done_when:** Source-of-truth docs describe the new styles, smoke runs produce
real local PNGs, docs-sync reports `status=ok`, and strict harness reports
`status=ok`.

## Execution Evidence

- Task 1 RED: `uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q`
  failed before style dispatch existed.
- Task 1 GREEN: `uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q`
  passed after adding `xhs_note_card_v1`, `iphone_notes_v1`, and
  `wechat_chat_v1` local renderers.
- Task 2 RED: `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py -q`
  failed before `--local-image-style` and `PlaybookRequest.local_image_style`
  existed.
- Task 2 GREEN: the same CLI/use-case test command passed after wiring the
  request field into local fallback payload generation.
- Visual smoke: deterministic dry-runs generated
  `outputs/generated_images/acct-fk-local-fengkuang_daily_post-1-7-cover.png`
  with `style=iphone_notes_v1` and
  `outputs/generated_images/acct-fk-local-fengkuang_daily_post-1-3-cover.png`
  with `style=wechat_chat_v1`; both are 1080x1440 nonblank PNGs.
