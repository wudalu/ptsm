# XHS Image Generation Quality Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make PTSM-generated XHS images cleaner and more useful: local renderer images skip watermark removal, local images vary time/content details, provider images remain cleaned and more realistic, and generated assets are accumulated for future reuse.

**Architecture:** Keep image rendering and provider protocols in `src/ptsm/infrastructure/images/`. Keep publish-time orchestration in `src/ptsm/application/use_cases/run_playbook.py`, using explicit image provenance metadata to decide post-processing. Keep drafting-time image-form guidance in `xhs_image_strategy` and source-of-truth docs, not in OpenClaw wrappers.

**Tech Stack:** Python 3.12, Pillow local renderer, OpenCV watermark remover, pytest, existing PTSM artifact store and JSON metadata.

## Current Docs Summary

- `docs/architecture.md` says provider-backed generation and local social screenshot rendering belong in `infrastructure`, while `run_playbook()` composes the pre-publish image step and persists metadata.
- `docs/runtime.md` says local renderer supports `note_card`, `iphone_notes`, and `wechat_chat`, does not draw PTSM branding/footer, and writes `image_generation.watermark_policy`.
- `docs/runtime.md`, `docs/observability.md`, and `docs/operations.md` currently say real publish removes watermarks for all final image paths. This is now stale for local PTSM-rendered images and must change to provenance-aware cleanup.
- `docs/xhs-topics/image-forms-by-domain.md` and `xhs_image_strategy` already define the desired image roles: local screenshots should be low-density, with `wechat_chat` for real reply/chat assets, `iphone_notes` for save tools, `note_card` for short shareable lines, and provider images for evidence/scene visuals.

## Confirmed Assumptions

- Local generated image means PTSM code-rendered images from `NoteCardImageBackend`: `xhs_note_card_v1`, `iphone_notes_v1`, and `wechat_chat_v1`.
- Provider/LLM generated image means configured external image backends such as `bailian` or `jimeng`.
- Manual `--publish-image-path` images keep the current defensive real-publish watermark removal behavior in this change.
- Asset accumulation should be lightweight metadata-first. Do not bulk-generate or commit image files; record generated image entries in local outputs so later experiments can curate or reuse them.

### Task 1: Provenance-Aware Watermark Removal

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/infrastructure/images/note_card_backend.py`
- Modify: `src/ptsm/infrastructure/images/watermark_policy.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/infrastructure/images/test_note_card_backend.py`

**Step 1: Write failing tests**

Add unit coverage proving:

- A real publish with generated `local_note_card` images does not instantiate or call `WatermarkRemover`.
- The artifact/response records a skipped watermark cleanup policy for local generated images, including a reason such as `local_renderer_trusted_no_watermark`.
- A real publish with provider-generated `bailian` images still calls `WatermarkRemover`.
- `NoteCardImageBackend.generate()` returns provenance metadata identifying the image as `local_renderer`.

**Step 2: Run focused failing tests**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q -k "watermark or image"
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q -k "watermark or provenance"
```

Expected: new tests fail before implementation.

**Step 3: Implement provenance policy**

- Add a small metadata shape returned by local renderer, for example:

```python
"provenance": {
    "source": "ptsm_local_renderer",
    "renderer": "NoteCardImageBackend",
    "watermark_removal": "skip",
}
```

- Keep provider backends as generated provider sources and preserve `watermark_policy.requested == "no_provider_watermark"`.
- Change `_should_remove_watermark()` or its call site so it can distinguish final image paths backed by local generated provenance from provider/manual paths.
- When skipping, write a structured `watermark_removal` artifact such as:

```python
{
    "status": "skipped",
    "policy": "skipped_for_local_renderer",
    "reason": "local_renderer_trusted_no_watermark",
}
```

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q -k "watermark or image"
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q -k "watermark or provenance"
```

**done_when:** Local generated images never pass through `WatermarkRemover`; provider and manual images keep the defensive cleanup path.

### Task 2: Local Renderer Time And Content Enrichment

**Files:**
- Modify: `src/ptsm/infrastructure/images/note_card_backend.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md`
- Test: `tests/unit/infrastructure/images/test_note_card_backend.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add coverage proving:

- `iphone_notes` default date/time is not always `今天 9:41`; it deterministically varies by payload.
- `wechat_chat` default time labels are not always `9:41 AM`; they deterministically vary by payload.
- Explicit `status_time` and `chat_times` still override generated defaults.
- WeChat content with generic speakers can be enriched into plausible display labels, while explicit speaker names are preserved.
- A local notes card can surface a strong short line from `image_text`, `body`, or `image_plan.golden_line` without pulling dense body paragraphs into the image.

**Step 2: Run focused failing tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q -k "time or speaker or golden or low_density"
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q -k "note_card_image_payload or wechat"
```

Expected: new tests fail before implementation.

**Step 3: Implement deterministic variety**

- Add deterministic helpers based on payload text hash, not wall-clock time, so tests remain stable.
- For `iphone_notes`, render `今天 HH:MM` from explicit `status_time` if present, otherwise a hashed time window appropriate to the content.
- For `wechat_chat`, derive default `chat_times` from explicit plan fields first, otherwise hashed labels such as `18:57`, `19:08`, or `23:22` depending on scene/body hints.
- Add a small nickname fallback map for generic chat roles, e.g. workplace scenes use `小周`, `阿茉`, `Leader` only when explicit labels are absent; preserve explicit `同事`, `领导`, `朋友`, and user-provided names.
- Add `golden_line` / `quote_line` support in renderer payload and selection helpers so notes and cards can show one strong sentence without dense body copy.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q -k "note_card or image"
```

**done_when:** Local images remain deterministic for tests, but no longer visibly reuse fixed `9:41` defaults; chat and notes images carry plausible content details without increasing text density.

### Task 3: Provider Image Realism Prompt Policy

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add tests for `_build_image_generation_prompt()` proving provider prompts:

- Include source no-watermark constraints.
- Include human-photo realism constraints: imperfect framing, ambient light, ordinary phone-shot details, no poster typography, no plastic skin, no fake UI screenshots.
- Vary by `image_plan.role`: `evidence_or_scene` emphasizes real objects/space/process; `cover_hook` allows one short overlay; `save_tool/comment_prompt` does not ask provider to fake screenshots.

**Step 2: Run focused failing test**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q -k "image_generation_prompt"
```

Expected: new tests fail before implementation.

**Step 3: Implement prompt policy**

- Add a helper that derives provider prompt constraints from `image_plan.role`, `requested_backend`, and `content_review.image_form`.
- Keep prompt length bounded by the existing 800-char limit.
- Make provider prompts ask for real-scene aesthetics while still saying AI output is atmosphere/reference, not evidence.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q -k "image_generation_prompt or image"
```

**done_when:** Provider prompt tests prove the realism constraints are explicit and role-aware.

### Task 4: Generated Image Asset Ledger

**Files:**
- Create: `src/ptsm/infrastructure/images/asset_ledger.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/infrastructure/images/test_asset_ledger.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add coverage proving:

- A generated image run appends one JSONL ledger entry under `outputs/artifacts/generated-image-assets/assets.jsonl`.
- Ledger entries include generated path, provider, style/model, provenance source, image plan metadata, prompt hash or prompt summary, artifact path, playbook id, and created timestamp.
- Runs without generated images do not write ledger entries.

**Step 2: Run focused failing tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_asset_ledger.py tests/unit/application/use_cases/test_run_playbook.py -q -k "asset_ledger or generated_image"
```

Expected: new tests fail before implementation.

**Step 3: Implement ledger**

- Keep the ledger local and append-only.
- Do not copy image bytes; reference the generated image paths already written under `outputs/generated_images/`.
- Add the ledger path or entry summary to `image_generation.asset_ledger` in the run response/artifact.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_asset_ledger.py tests/unit/application/use_cases/test_run_playbook.py -q -k "asset_ledger or generated_image"
```

**done_when:** Every PTSM-generated image can be audited and later curated without committing image files or changing publish behavior.

### Task 5: Docs And Operator Surface

**Files:**
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/xhs-topics/image-forms-by-domain.md`
- Modify if needed: `docs/architecture.md`
- Modify if needed: `docs/skills.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Update docs**

Document:

- Provenance-aware watermark cleanup.
- Local generated images skip cleanup and record a skipped policy.
- Provider/manual images still clean on real publish.
- Local renderer time/content enrichment behavior.
- Provider image realism prompt policy.
- Asset ledger path and intended use.

**Step 2: Verify docs**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path src/ptsm/application/use_cases/run_playbook.py \
  --changed-path src/ptsm/infrastructure/images/note_card_backend.py \
  --changed-path src/ptsm/infrastructure/images/asset_ledger.py \
  --changed-path src/ptsm/infrastructure/images/watermark_policy.py \
  --changed-path src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md
```

**done_when:** Source-of-truth docs no longer claim all real-publish images must be cleaned; docs-sync accepts the code/doc surface.

### Task 6: End-To-End And Harness Verification

**Files:**
- No new files unless smoke artifacts are produced under ignored `outputs/`.

**Step 1: Run targeted test set**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/infrastructure/images/test_asset_ledger.py tests/unit/application/use_cases/test_run_playbook.py -q
```

**Step 2: Run broader tests**

Run:

```bash
uv run pytest -q --ignore=tests/e2e
```

**Step 3: Run image smoke dry-run**

Run:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "领导18:57发来一句在吗" \
  --account-id acct-fk-local \
  --auto-generate-image \
  --local-image-style wechat_chat
```

Expected: `status == completed`, `image_generation.provider == local_note_card`, local provenance present, `watermark_removal.status == skipped`, and an asset ledger entry is written.

**Step 4: Run final gate**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Targeted tests, non-e2e baseline, smoke dry-run, docs-sync, and harness-check pass from the worktree.
