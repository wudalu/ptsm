# XHS Hotspot Topic Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an agent-readable XiaoHongShu hotspot and vertical-index doc set under `docs/` that can guide future topic selection and align with the existing PTSM harness/docs map.

**Architecture:** Add a dedicated `docs/xhs-topics/` directory as the landing area for current research, capability mapping, and harness integration guidance. Keep the new docs navigable from `docs/index.md` and `docs/skills.md` without expanding `docs-sync` scope to unrelated runtime code.

**Tech Stack:** Markdown docs with YAML front matter, existing PTSM docs map, pytest doc checks, XiaoHongShu MCP ecosystem references.

### Task 1: Define the doc surface

**Files:**
- Create: `docs/xhs-topics/index.md`
- Create: `docs/xhs-topics/skills-landscape.md`
- Create: `docs/xhs-topics/verticals.md`
- Create: `docs/xhs-topics/harness-integration.md`

**Step 1: Draft the landing-page contract**

Write `docs/xhs-topics/index.md` with:

- front matter using `status`, `owner`, `last_verified`, `source_of_truth`, `related_paths`
- the purpose of the directory
- reading order for humans and agents
- links to the three supporting docs

**Step 2: Verify the doc set is scoped correctly**

Check that:

- `source_of_truth` is only used where the doc should behave as a living reference
- `related_paths` does not accidentally force unrelated code/doc updates
- the landing page explains how topic research differs from playbook or skill truth

**Step 3: Commit**

```bash
git add docs/xhs-topics/index.md docs/xhs-topics/skills-landscape.md docs/xhs-topics/verticals.md docs/xhs-topics/harness-integration.md
git commit -m "docs: add xhs hotspot topic index"
```

### Task 2: Document the current skill and tool landscape

**Files:**
- Modify: `docs/xhs-topics/skills-landscape.md`
- Reference: `src/ptsm/skills/builtin/`
- Reference: `docs/skills.md`

**Step 1: Write the failing review checklist**

Add the following checklist to the draft and ensure every item is covered:

- current repo builtin skills do not cover hotspot tracking
- official OpenAI curated skills were checked and do not include XiaoHongShu-specific skills
- external ecosystems worth reusing are named and linked
- PTSM-native skill gaps are described as concrete candidates

**Step 2: Verify the checklist against real sources**

Review each claim against:

- local repo skill files
- current OpenAI curated skill listing
- external XiaoHongShu MCP/OpenClaw repos

Expected: no unsupported claims remain in the doc.

**Step 3: Commit**

```bash
git add docs/xhs-topics/skills-landscape.md
git commit -m "docs: map xhs trend skill landscape"
```

### Task 3: Define the vertical-topic index

**Files:**
- Modify: `docs/xhs-topics/verticals.md`

**Step 1: Write the vertical selection frame**

Document a compact selection rubric:

- persistent demand
- topic reproducibility
- relevance to existing or plausible future playbooks
- ability to collect evidence via search/feed/detail workflows

**Step 2: Add current vertical candidates with evidence**

For each chosen vertical, include:

- why it matters now
- what kind of post angles fit it
- whether it is trend-chasing, evergreen, or hybrid
- which upstream source supports the choice

**Step 3: Run a doc-quality review**

Check that:

- the list is focused, not a dumping ground
- each vertical is actionable for future topic planning
- sources are dated and linked

**Step 4: Commit**

```bash
git add docs/xhs-topics/verticals.md
git commit -m "docs: add xhs vertical topic index"
```

### Task 4: Connect the docs to the harness narrative

**Files:**
- Modify: `docs/xhs-topics/harness-integration.md`
- Modify: `docs/index.md`
- Modify: `docs/skills.md`

**Step 1: Write the harness integration note**

Document:

- which MCP/tooling surfaces can supply hotspot evidence
- which artifacts should be stored for repeatable analysis
- which future PTSM skill additions would operationalize the docs

**Step 2: Update the docs map**

Link the new directory from:

- `docs/index.md`
- `docs/skills.md`

Expected: an engineer or agent starting from `docs/index.md` can discover the new topic index in one hop.

**Step 3: Commit**

```bash
git add docs/xhs-topics/harness-integration.md docs/index.md docs/skills.md
git commit -m "docs: link xhs topic index into docs map"
```

### Task 5: Verify the changes

**Files:**
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Run focused verification**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS

**Step 2: Run broader harness verification if doc links changed materially**

Run:

```bash
uv run pytest -q
```

Expected: PASS or a clearly documented unrelated failure.

**Step 3: Final commit**

```bash
git add docs/plans/2026-04-22-xhs-hotspot-topic-index.md
git commit -m "docs: add xhs hotspot topic index plan"
```
