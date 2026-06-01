# Title Hook Sharpening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make PTSM Xiaohongshu titles shorter, sharper, and more click-worthy by requiring compact conflict, contrast, or dramatic hook mechanics across all current XHS playbooks.

**Architecture:** Keep title quality in the asset and evaluation layers, not in new runtime orchestration branches. Tighten shared prompt guidance, DeepSeek hard requirements, deterministic dry-run examples, and playbook-local evaluation contracts so the same rule applies to all nine XHS playbooks.

**Tech Stack:** Python 3.12, pytest, YAML playbook contracts, PTSM deterministic drafting backend, DeepSeek prompt assembly, docs-sync/harness-check.

## Current Docs Summary

- `docs/architecture.md` says title appeal belongs in assets/contracts: `xhs_human_voice`, playbook-local `evaluation.yaml`, DeepSeek/deterministic drafting, and `contracts_eval.py`; runtime should not gain domain-specific orchestration branches for title quality.
- `docs/runtime.md` says drafting backends read playbook prompts, persona prompts, static skills, runtime skill contexts, and shared XHS title/body hard requirements; deterministic helpers cover offline dry-runs for all XHS content playbooks.
- `docs/playbooks.md` says all XHS playbooks share one title/body contract: title uses concrete scene/object/relationship/original quote plus conflict, contrast, identity, or tool value; body uses hook -> domain element -> saveable unit -> comment handoff.
- `docs/skills.md` says `xhs_human_voice` is the shared human-tone skill and already rejects generic titles such as `日常` / `实录` / `干货分享`, but it does not yet set a compact hard length or explicit dramatic-tension gate.
- `docs/harness-engineering.md` says generic playbook node contracts enforce title/body quality and should be extended before adding runtime branches.
- `docs/operations.md` says XHS regression should be checked through dry-run plus eval/harness; operators should inspect concrete title hooks and avoid generic titles.
- `docs/xhs-topics/index.md` positions hook research as already productized into playbook/skill assets. This change sharpens runtime title output and contracts, not topic research or domain coverage.

## Working Requirements

- Titles for every current XHS playbook should be at most 22 Python characters, with the prompt preferring 12-18 visible Chinese characters when practical.
- Titles must contain an explicit tension cue: conflict, reversal, dramatic moment, curiosity gap, or urgent contrast. Examples include `那一秒`, `不是`, `别`, `却`, `反而`, `突然`, `原来`, `为什么`, `到底`, `值不值`, `被`, `最累`, `先别`, `救`, `硬仗`, `冷场`.
- Titles must still stay domain-faithful and safe: psychology titles must not expose mechanism terms; Reddit curation must not reveal source/platform; World Cup titles must not imply betting or fake insider claims.
- Deterministic dry-runs for all nine XHS playbooks must produce titles satisfying the new compact tension rule.
- DeepSeek prompt assembly must carry the same rule so live generation is guided by the same contract.

### Task 1: Add Failing Contract Tests For Compact Dramatic Titles

**Files:**
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`
- Modify: `tests/e2e/test_xhs_title_body_quality_contracts.py`

**Step 1: Write failing tests**

- Add a contract evaluator test proving a title without any configured tension cue fails `title_must_include_tension_any`.
- Add a playbook contract test proving every XHS playbook sets `title_max_chars <= 22` and a non-empty `title_must_include_tension_any`.
- Add dry-run assertions that each generated XHS title has `len(title) <= 22` and includes one shared dramatic tension cue.

**Step 2: Verify red**

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py::TestPlaybookNodeContract::test_fails_when_title_lacks_required_tension_marker tests/unit/evaluations/test_playbook_contracts.py::TestPlaybookEvalContract::test_all_xhs_contracts_require_compact_dramatic_titles tests/e2e/test_xhs_title_body_quality_contracts.py::test_xhs_playbook_dry_runs_fit_title_body_quality_contract -q
```

Expected: FAIL because the evaluator does not support the new constraint, playbook contracts still allow longer titles, and at least human-enrichment/world-cup deterministic titles are too flat.

**done_when:** Red test failures prove missing `title_must_include_tension_any` support or current flat title output, not import/syntax errors.

### Task 2: Implement Generic Title Tension Contract Support

**Files:**
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/playbooks/definitions/*/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Implement minimal contract evaluator support**

- Read `constraints["title_must_include_tension_any"]` as a list of strings.
- If configured and title is present, fail when none of the markers appears in the title.
- Use reason text containing `title_must_include_tension_any`.

**Step 2: Tighten all XHS evaluation contracts**

- Set `title_max_chars: 22` for all nine XHS playbooks.
- Add the shared title tension cue list to executor constraints for all nine XHS playbooks.
- Preserve existing domain-specific `title_must_include_any` and safety bans.

**Step 3: Verify green**

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py::TestPlaybookNodeContract::test_fails_when_title_lacks_required_tension_marker tests/unit/evaluations/test_playbook_contracts.py::TestPlaybookEvalContract::test_all_xhs_contracts_require_compact_dramatic_titles -q
```

**done_when:** Unit tests pass and no existing contract semantics regress.

### Task 3: Sharpen Prompt Assets And DeepSeek Requirements

**Files:**
- Modify: `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/unit/skills/test_skill_loader.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`

**Step 1: Write or update tests**

- Assert `xhs_human_voice` mentions short title length, tension/conflict, and generic-title avoidance.
- Assert DeepSeek hard requirements mention the 22-character cap and dramatic tension cues.

**Step 2: Implement prompt changes**

- Update `xhs_human_voice` title guidance to prefer 12-18 chars and cap at 22.
- Update `_build_deepseek_hard_requirements()` with the same length/tension rule.

**verify:**

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/infrastructure/llm/test_factory.py -q
```

**done_when:** Prompt tests pass and hard requirements contain the new compact dramatic title rule.

### Task 4: Sharpen Deterministic Draft Titles

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/e2e/test_xhs_title_body_quality_contracts.py`
- Modify: targeted e2e files only if they assert exact older titles.

**Step 1: Update deterministic titles**

- Replace flat or generic deterministic titles with compact scene-specific titles containing a tension cue.
- Remove `实录` / `日常` from deterministic titles that can surface as final content.
- Keep all existing safety/domain requirements intact.

**Step 2: Verify dry-runs**

Run:

```bash
uv run pytest tests/e2e/test_xhs_title_body_quality_contracts.py -q
```

**done_when:** All nine deterministic XHS dry-runs produce compact dramatic titles and still satisfy body/hashtag contracts.

### Task 5: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Review: `docs/xhs-topics/index.md`

**Step 1: Update docs**

- Document the 22-character compact title cap and tension-cue contract.
- Document that the behavior remains asset/contract-driven.
- Mention dry-run/eval verification in operations and harness docs.
- If `docs/xhs-topics/index.md` remains unchanged, leave the plan note as the reason: no new topic research or domain coverage changes.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/harness-engineering.md --changed-path docs/operations.md
```

**done_when:** Docs tests and docs-sync pass, or any docs-sync limitation is captured with exact output.

### Task 6: Final Verification And Completion Audit

**Files:**
- No new source files expected.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py tests/unit/evaluations/test_playbook_contracts.py tests/unit/skills/test_skill_loader.py tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_xhs_title_body_quality_contracts.py -q
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:**

- Targeted tests pass.
- Non-e2e baseline passes.
- Harness-check passes or reports only unrelated pre-existing issues with exact evidence.
- `git diff` shows no unrelated edits from the dirty main workspace.
