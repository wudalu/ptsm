# Psychology Learning Editorial Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task. Use superpowers:verification-before-completion before merge.

**Goal:** Deliver psychology learning carousels in canonical order with emoji-free image copy, warmer editorial wording, and more polished local typography while preserving historical curriculum receipts.

**Architecture:** Add controlled-template v3 and a new builtin curriculum revision instead of mutating historical content. Keep emoji validation in the psychology carousel domain, keep visual changes in the existing local renderer, and preserve the immutable ordered receipt as the only relay authority. Update the repository and installed psychology wrapper together.

**Tech Stack:** Python 3.12, Pydantic, Pillow, pytest, Markdown skill contracts, PTSM CLI/harness.

## Current Source-of-Truth Summary

- `learning_series` is a strict submode of `modern_psychology_post`, not a new
  domain or playbook.
- Runtime reconstructs reader copy from a frozen catalog and controlled template;
  caller text and a second model pass cannot rewrite lessons.
- Historic template v1 is a single card; current template v2 is an exact
  seven-page `psychology_text_card_v1` carousel.
- A carousel is committed atomically, recorded in manifest order, and exposed to
  an external relay only through `carousel_delivery.status=ready` plus ordered
  attachments and hashes.
- PTSM does not own external sender acknowledgement, retry, or delivery claims.
- The repository wrapper already documents the relay boundary, but the installed
  Codex skill is an older mirror; deployment parity is part of this change.

### Task 1: Reject emoji in psychology image copy

**Files:**

- Modify: `src/ptsm/domain/psychology_carousel.py`
- Test: `tests/unit/domain/test_psychology_carousel.py`

**Step 1: Write failing tests**

Add parameterized cases for pictographs, emoji presentation selectors, flags,
skin-tone modifiers, keycap sequences, and ZWJ sequences in both `headline` and
`body_lines`. Add passing cases for ordinary Chinese punctuation, numbered text,
and safe symbols used by current lessons.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/domain/test_psychology_carousel.py -q -k emoji
```

Expected: the new cases fail because emoji is currently accepted.

**Step 3: Implement the minimal domain rule**

Add one reusable predicate for unsupported image emoji sequences and call it
from `_require_safe_visible_text`. Keep the accepted text unchanged; do not
silently strip ordinary model-authored slides.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/domain/test_psychology_carousel.py -q
```

**verify:** Every emoji-bearing image field fails before rendering, while current
safe punctuation remains valid.

**done_when:** No accepted psychology carousel plan can ask Pillow to render an
emoji glyph.

### Task 2: Add controlled-template v3 without invalidating v1/v2 custom catalogs

**Files:**

- Modify: `src/ptsm/domain/psychology_learning.py`
- Test: `tests/unit/domain/test_psychology_learning.py`
- Test: `tests/unit/application/use_cases/test_psychology_learning_series.py`
- Test: `tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py`
- Test: `tests/unit/evaluations/test_contract_evaluators.py`
- Test: `tests/unit/application/use_cases/test_eval_artifact.py`

**Step 1: Write failing version and copy tests**

Require newly confirmed catalogs to use template v3 and produce exact warm,
restrained copy. Require v3 image slides to contain no emoji even when a proposal
title contains emoji. Retain fixtures proving persisted template v1/v2 snapshots,
digests, receipts, drafts, and evals still reconstruct exactly.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py -q -k 'template_v3 or emoji_free or warm_editorial or historic'
```

Expected: v3 cases fail because the registry ends at v2.

**Step 3: Implement v3**

Register immutable template v3 with its own copy compactor, lesson builder, and
catalog digest binding. Compose the post body in four natural beats and use
short, human card headlines such as scene, explanation, one small action, and
support boundary labels. Reuse only approved catalog fields and keep the exact
200–380 character, hashtag, safety, and receipt gates.

**Step 4: Verify GREEN**

Run the complete command from Step 2 without `-k`.

**verify:** New confirmations bind v3; historic v1/v2 material remains byte- and
receipt-compatible; v3 exact draft validation rejects any rewrite.

**done_when:** Future custom learning catalogs gain improved copy without mutating
an existing immutable revision.

### Task 3: Version the builtin course and make the polished revision current

**Files:**

- Modify: `src/ptsm/domain/psychology_learning.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py` if response selection needs adjustment
- Test: `tests/unit/domain/test_psychology_learning.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**Step 1: Write failing compatibility tests**

Require explicit builtin curriculum version 1 to retain its template-v2 draft.
Require an unversioned roadmap and new selections to return builtin curriculum
version 2 using template v3. Pin the matching direction id, seven roles, title,
body, and exact image-plan order for both versions.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py -q -k 'builtin and (version or editorial)'
```

Expected: version 2 is unsupported.

**Step 3: Implement the version map**

Keep the existing builtin tuple as curriculum version 1. Add curriculum version
2 with rewritten, fact-equivalent catalog fields and a template-v3 binding.
Resolve an omitted version to version 2 while accepting explicit version 1 for
artifact reconstruction and retries.

**Step 4: Verify GREEN**

Run the full unit commands above and the psychology e2e file.

**verify:** Old builtin artifacts still audit; new roadmaps/runs use the polished
revision and publish exactly seven ordered pages.

**done_when:** The active builtin learning experience improves without changing
the meaning of a historical version identifier.

### Task 4: Polish the psychology card renderer

**Files:**

- Modify: `src/ptsm/infrastructure/images/note_card_backend.py`
- Test: `tests/unit/infrastructure/images/test_note_card_backend.py`

**Step 1: Write failing layout tests**

Capture drawn text and geometry to require stronger cover/inner hierarchy,
bounded editorial measure, calmer label treatment, visible page counter, and no
emoji. Add a rendered sample assertion for 1080×1440 and non-clipped maximum
legal content.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q -k psychology
```

Expected: the new layout invariants fail on the current renderer.

**Step 3: Implement the visual update**

Refine type sizes, line spacing, content width, vertical rhythm, label/counter
treatment, bullet styling, and restrained decorative shapes. Continue rendering
only supplied contract text; add no icons or emoji.

**Step 4: Verify and inspect**

Run the full renderer test file, generate representative cover/tool/boundary
PNGs, and inspect them visually.

**verify:** Tests prove bounds and exact drawn strings; visual inspection confirms
the warm editorial hierarchy at full resolution.

**done_when:** Cards are more readable and polished without changing dimensions,
style routing, or transaction behavior.

### Task 5: Lock ordered relay behavior and deploy the updated skills

**Files:**

- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `tests/unit/skills/test_skill_loader.py`
- Modify: `tests/unit/docs/test_openclaw_skill.py`
- Deploy mirror: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`

**Step 1: Record RED evidence and add failing checks**

Use the observed repository/installed-skill diff as the deployment baseline:
the installed skill lacks the ordered relay section. Add tests requiring image
copy to be emoji-free and requiring relay iteration by canonical attachment
order without reconstructing order from paths or filenames.

Subagent pressure tests are intentionally not used because the active session
policy forbids unrequested subagents. Existing wrapper behavior tests and the
real stale-mirror diff provide deterministic RED evidence instead.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/docs/test_openclaw_skill.py -q -k 'emoji or ordered'
```

Expected: emoji guidance fails; installed mirror comparison is nonzero.

**Step 3: Update the minimal skill contracts**

Tell the builtin style to avoid emoji in all image-plan fields and use the warm,
restrained editorial tone for learning copy. Tighten the wrapper relay wording
to iterate the exact attachments in ascending canonical order as a complete set.
Do not add sender retries or delivery claims to PTSM.

**Step 4: Deploy and verify parity**

After repository tests pass, mechanically mirror the repository wrapper into
the installed Codex skill and run:

```bash
cmp -s integrations/openclaw/ptsm-xhs-psychology/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md
```

**verify:** Skill tests pass and `cmp` exits zero.

**done_when:** The active skill used by Codex contains the same emoji and ordered
relay contract as the repository source.

### Task 6: Update source-of-truth docs and operator instructions

**Files:**

- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/observability.md` if versioned artifact interpretation changes
- Modify: `tests/unit/docs/test_docs_map.py`

**Step 1: Write failing docs-contract tests**

Require active docs to mention template v3, current builtin curriculum version,
emoji-free image copy, warm editorial renderer behavior, historic v1/v2
compatibility, canonical relay attachment order, and repository/installed skill
parity at deployment.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**Step 3: Update docs and metadata**

Update each affected source-of-truth surface and `last_verified`. Record that
Topic Radar, generic shared contracts, accounts, real-publish authorization, and
task-completion automation remain unchanged.

**Step 4: Verify GREEN**

Run the docs tests and `docs-sync` for every changed code/skill/doc path.

**verify:** Docs tests and docs-sync pass with no stale v2-only claim on the
active learning path.

**done_when:** Operators can discover the new version, rendering, no-emoji, and
relay behavior from current docs rather than a historical plan.

### Task 7: End-to-end and final verification

**Files:**

- Modify tests only if an end-to-end contract gap is discovered before production edits
- Evidence: runtime-generated temporary artifacts/images only

**Step 1: Run focused suites**

```bash
uv run pytest -q tests/unit/domain/test_psychology_carousel.py tests/unit/domain/test_psychology_learning.py tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py tests/e2e/test_modern_psychology_publish_dry_run.py
```

**Step 2: Run a deterministic dry-run**

Query the current builtin roadmap, explicitly select the returned curriculum
version and lesson, then run with `--auto-generate-image --publish-mode dry-run
--eval`. Inspect manifest `pages.order`, generated filenames, hashes, artifact
receipt, and representative PNGs. Do not perform a real XHS publish.

**Step 3: Run project gates**

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
git diff --check
```

**Step 4: Review and integrate**

Use `superpowers:requesting-code-review` and
`superpowers:verification-before-completion`, merge the feature branch back to
`main`, verify the installed skill mirror against the merged source, and remove
the worktree/branch only after success.

**verify:** Every command exits zero and the dry-run produces a complete ordered,
emoji-free seven-page carousel with a valid evaluation receipt.

**done_when:** Main contains the feature, current Codex loads the matching skill,
and the handoff reports exact tests/evidence plus any explicitly requested remote
upload result.
