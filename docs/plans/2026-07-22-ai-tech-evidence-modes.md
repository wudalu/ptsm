# AI Tech Evidence Modes Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Make every `ai_tech_daily_post` dry-run choose one evidence-grounded
content mode—multi-item news brief, single-topic hands-on, or single-topic fact
translation—and fail closed before drafting when its required evidence is absent.

**Architecture:** Add a pure AI-tech domain contract that validates operator
evidence bundles and generated drafts. `run-playbook` becomes the authoritative
preflight and pre-publish gate; the runtime only receives a provenance-safe
mode contract and safe facts. Mode-specific drafting assets, guide-post
directions, an OpenClaw wrapper, artifact metadata, evaluator coverage, and
operator docs complete the end-to-end path.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph runtime, YAML playbook
assets, pytest, existing PTSM artifact/evaluation/harness tooling.

## Requirement Summary

- `news_brief`: 3–5 independent AI events; every item has a safe display
  label, one or more approved facts, and opaque source references. It is a
  multi-item briefing, never a first-person test.
- `hands_on`: exactly one selected topic plus a reproducible test record:
  product/model and version, date, task, input summary, observation/output,
  limitation, and a test-evidence reference. It is the only mode allowed to
  say the author tested or observed a result.
- `fact_translation`: exactly one selected topic plus at least two approved
  facts and explicit `who_should_care` / `who_can_wait` decisions. It explains
  a current fact without pretending to be a hands-on experience.
- Generic AI opinions, scene-only fallbacks, and invented personal tests are
  invalid. Existing prompt/tool directions may only run as `hands_on` with the
  same test evidence; they do not remain a hidden fourth mode.
- Topic Radar / hotspot discovery contributes `trend_support` only. A cluster
  or raw trending headline alone cannot satisfy product-fact or hands-on
  evidence requirements.
- Raw source URLs, authors, feed identifiers, and raw source titles remain out
  of drafting context and reader-visible content. Artifacts retain only an
  opaque evidence manifest.

## Current Docs Summary

- `docs/architecture.md`: `topic_radar` owns collection and canonical source
  evidence; PTSM may consume only the public scan API and provenance-safe
  traceability. The existing discovery-first artifact is operator-only and
  deliberately does not hand raw headlines into drafting.
- `docs/runtime.md`: `run-playbook` is the application orchestration boundary;
  the graph is `ingest -> planner -> memory -> executor -> reflector ->
  finalize`. Required runtime quality gates can retry before finalization,
  whereas offline eval is not a publish blocker.
- `docs/playbooks.md` / `docs/skills.md`: `ai_tech_daily_post` is the current
  AI account/playbook and still contains a prompt-building sublane. Its
  content assets, rather than generic orchestration branches, own editorial
  voice and shape.
- `docs/topic-radar.md`, `docs/operations.md`, and
  `docs/operations/local-runbook.md`: generic hotspot discovery is first,
  followed by an explicit account/playbook choice; normal AI dry-runs currently
  accept a free-text scene and therefore need a new operator evidence contract.
- `docs/harness-engineering.md` and `docs/observability.md`: artifact fields,
  deterministic tests, docs-sync mappings, and strict harness evidence are
  required for a new runtime gate.

## Scope and Non-goals

**In scope**

- The AI-tech playbook and its generic CLI/OpenClaw guidance path.
- A JSON evidence-bundle file passed explicitly to `guide-post` / `run-playbook`.
- Runtime preflight, drafting-context, draft, and pre-publish evidence gates.
- Deterministic, unit, CLI, artifact/eval, docs, and dry-run coverage.

**Out of scope**

- Automatically crawling official product release notes or fabricating a test.
- Publishing a real Xiaohongshu post.
- Creating a new account or playbook.
- Relaxing Topic Radar provenance safeguards or sending raw source data to the
  model.

## Evidence Bundle Contract

Create `AiTechEvidenceBundle` in the domain layer. The JSON file is an
operator-supplied input; only its normalized drafting-safe fields travel into
the runtime.

```json
{
  "mode": "news_brief",
  "news_items": [
    {
      "label": "模型发布",
      "event_fingerprint": "event:model-release-1",
      "facts": ["可公开陈述的已核验事实"],
      "source_refs": ["source:official-1"],
      "trend_support": {
        "cluster_id": "cluster:...",
        "evidence_ids": ["evidence:..."]
      }
    },
    {
      "label": "开发者工具",
      "event_fingerprint": "event:developer-tools-2",
      "facts": ["另一条可公开陈述的已核验事实"],
      "source_refs": ["source:official-2"]
    },
    {
      "label": "行业应用",
      "event_fingerprint": "event:industry-use-3",
      "facts": ["第三条可公开陈述的已核验事实"],
      "source_refs": ["source:official-3"]
    }
  ]
}
```

The production schema has separate typed variants rather than accepting every
field in every mode. It validates labels, distinct event fingerprints, facts,
opaque refs, mode-specific counts, and rejects raw provenance keys before the
LLM can see them. Opaque identifiers intentionally exclude `.` so a bare
source domain cannot enter the evidence contract as an identifier. Any
drafting-safe text field also rejects raw URLs, domains, and URI locators.
For Chinese and code-heavy AI facts, the locator detector treats schemes,
UNC/IP forms, common bare public domains, and any domain with a URL suffix as
unsafe. An unqualified non-common dotted identifier (for example
`torch.compile`) remains allowed because it is ambiguous with ordinary source
provenance; source evidence must therefore stay in opaque refs rather than in
free text.

## Task 1: Establish the domain contract and failing tests

**Files:**

- Create: `src/ptsm/domain/ai_tech_content.py`
- Create: `tests/unit/domain/test_ai_tech_content.py`
- Modify: `src/ptsm/domain/__init__.py` only if the package requires exports

**Step 1: Write failing tests**

Cover valid bundles for all three modes and fail cases for: no mode; a
two-item news brief; a hands-on case without version, limitation, or test ref;
a fact-translation case without two facts; raw URL/author/feed fields; and
trend-support-only input.

**Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_ai_tech_content.py -q`

Expected: failure because the domain module/contract does not exist.

**Step 3: Implement the smallest pure contract**

Use Pydantic models or frozen dataclasses with one public normalizer:
`parse_ai_tech_evidence_bundle(...)`. Return a provenance-safe drafting payload,
an opaque manifest, and mode requirements. Keep no imports from application,
runtime, or Topic Radar.

**Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/domain/test_ai_tech_content.py -q`

**verify:** domain tests pass with invalid bundles rejected deterministically.

**done_when:** all three modes have a typed contract and hotspot trend support
cannot impersonate facts or test evidence.

## Task 2: Add request/CLI evidence intake and preflight gate

**Files:**

- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Create: `tests/fixtures/ai_tech_evidence/` mode-specific JSON fixtures if
  existing fixture conventions permit it

**Step 1: Write failing tests**

Specify `--ai-content-mode` and `--ai-evidence-file`. Test a malformed JSON
file, explicit mode/file mismatch, missing AI mode/evidence, and a successful
AI preflight. Assert rejected requests return a stable diagnostic before
`RunStore.start`, workflow invocation, artifact creation, image generation, or
publisher calls.

**Step 2: Verify RED**

Run the focused CLI/use-case tests and observe missing argument/unknown status
failures.

**Step 3: Implement the boundary**

Add optional request fields for a parsed evidence bundle and mode. The CLI loads
the JSON file at the interface boundary and reports parser errors cleanly.
Immediately after `run_playbook()` resolves `ai_tech_daily_post`, call the
domain parser. Missing/invalid inputs return explicit statuses such as
`ai_tech_evidence_required` / `ai_tech_evidence_invalid`; they never fall back
to a scene-only AI draft. Preserve existing behavior for the other eight
playbooks.

**Step 4: Verify GREEN**

Run the focused test files and a CLI `--help` smoke check.

**verify:** `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py -q`

**done_when:** the only AI playbook entry path that reaches the runtime has a
validated mode + bundle; a normal free-text AI scene is fail-closed.

## Task 3: Carry the evidence contract through the runtime and block unsafe drafts

**Files:**

- Modify: `src/ptsm/agent_runtime/state.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/agent_runtime/nodes/planner.py`
- Modify: `src/ptsm/agent_runtime/nodes/reflector.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/agent_runtime/test_planner_node.py`
- Modify: `tests/unit/agent_runtime/test_reflector_node.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Assert planner context contains only the selected mode, safe facts, structure,
and prohibitions—never raw source URL/title/author/feed data. Assert a news or
fact-translation draft with `我实测` / `速度提升明显` retries then fails; assert a
hands-on draft missing test task/result/limitation retries then fails; assert a
valid draft finalizes. Add a direct pre-publish revalidation test that prevents
publisher invocation if a custom workflow returns an unsafe draft.

**Step 2: Verify RED**

Run the focused planner/reflector/use-case tests and confirm they fail because
there is no AI content gate/context.

**Step 3: Implement the gate**

Extend execution state with the normalized AI content contract. Build an
`# AI Tech Evidence Contract` runtime context in the planner. Inject a pure
mode-aware draft validator into the reflector before the existing LLM quality
judge, so failures use the current retry loop. Revalidate completed content in
`run_playbook()` before any image or publisher operation to protect custom
workflows and future bypasses.

**Step 4: Verify GREEN**

Run the focused tests.

**verify:** `uv run pytest tests/unit/agent_runtime/test_planner_node.py tests/unit/agent_runtime/test_reflector_node.py tests/unit/application/use_cases/test_run_playbook.py -q`

**done_when:** unsafe AI drafts cannot finalize or publish, and a valid
mode-specific draft retains an opaque evidence manifest in the result/artifact.

## Task 4: Make AI guidance and writing assets mode-specific

**Files:**

- Modify: `src/ptsm/domain/topic_guidance.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `src/ptsm/application/use_cases/topic_guidance_packs.py`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/playbook.yaml`
- Modify: `src/ptsm/skills/builtin/ai_tech_style/SKILL.md`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`

**Step 1: Write failing tests**

Guide-post must expose only directions matching the requested AI mode and
describe required evidence. A stale/unknown AI `topic_direction_id` must not
silently fall back. The deterministic drafting backend must produce a
numbered 3–5 item brief, a reproducible hands-on structure, or a fact
translation structure, respectively; it must no longer produce a generic
first-person AI feeling draft.

**Step 2: Verify RED**

Run the focused tests and confirm existing generic/prompt behavior fails the
new expected contract.

**Step 3: Implement the smallest assets and behavior**

Add `content_mode` metadata to topic directions, filter AI directions by the
selected mode, and preserve the prompt direction only as a hands-on direction.
Put editable thresholds in `ai_content_policy` metadata in the AI playbook
YAML; the domain gate remains the enforcement authority. Rewrite planner,
persona, reflection, and AI style instructions around verifiable facts,
test protocol, limitations, and reader decisions. Update deterministic drafts
to honor the same contract for dry-run tests.

**Step 4: Verify GREEN**

Run the focused topic-guidance, registry, and deterministic backend tests.

**verify:** `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/infrastructure/llm/test_factory.py tests/unit/playbooks/test_playbook_registry.py -q`

**done_when:** guide-post, deterministic dry-runs, and LLM-facing assets all
select a mode explicitly; no legacy generic AI direction can bypass the gate.

## Task 5: Record and evaluate evidence-aware artifacts

**Files:**

- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/evaluation.yaml`
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/application/use_cases/eval_artifact.py` if evaluator
  registration requires it
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`
- Modify: `tests/unit/application/use_cases/test_eval_artifact.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Write failing tests**

Assert completed AI artifacts carry the mode, safe evidence manifest, and gate
result; assert offline eval reports a required failure for a missing manifest,
wrong item count, or non-hands-on experiential language.

**Step 2: Verify RED**

Run the focused evaluation tests and confirm the current evaluator cannot
recognize the AI evidence contract.

**Step 3: Implement evaluator support**

Write the safe manifest in finalize. Add a dedicated AI evidence contract
evaluator rather than overloading generic string constraints. Keep it as an
audit/regression layer; runtime gates remain publish blockers.

**Step 4: Verify GREEN**

Run focused eval tests.

**verify:** `uv run pytest tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py tests/unit/evaluations/test_playbook_contracts.py -q`

**done_when:** dry-run artifacts and offline evaluation make the selected mode
and evidence contract independently auditable without exposing raw provenance.

## Task 6: Update the OpenClaw wrapper and complete the documentation surface

**Files:**

- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/topic-radar.md`
- Modify: `docs/xhs-topics/index.md`
- Modify: `docs/xhs-topics/skills-landscape.md`
- Modify: `docs/xhs-topics/harness-integration.md`
- Modify: `docs/index.md` if `related_paths` changes
- Modify/add: focused docs/skill tests under `tests/unit/docs/`

**Step 1: Write failing docs/skill tests**

Lock the wrapper behavior: generic AI news starts discovery; drafting requires
one of the three modes plus evidence; it must never invent a test. Lock the
operator command examples and the source-of-truth documentation claims.

**Step 2: Verify RED**

Run the focused docs tests and confirm current free-scene AI examples fail the
new operational contract.

**Step 3: Update docs and skills**

Document evidence-file formats, safe dry-run examples, artifact fields,
diagnostics, and the separation between trend support, facts, and tests. Sync
the installed OpenClaw skill byte-for-byte with the repository skill. Update
`last_verified` only for docs revalidated by the new tests.

Review notes for intentionally unchanged surfaces:

- `docs/xhs-topics/verticals.md`: no domain count or target vertical changes.
- `docs/xhs-topics/image-forms-by-domain.md`: the image backend choices are
  unchanged; only AI text/evidence policy changes.

**Step 4: Verify GREEN**

Run focused docs tests, skill diff, and docs-sync for every changed path.

**verify:** `uv run pytest tests/unit/docs -q`; `diff -u integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-topic-guide/SKILL.md`; `uv run python -m ptsm.bootstrap docs-sync --changed-path ...`

**done_when:** a future operator or OpenClaw caller sees the evidence gate
before drafting and can run a documented dry-run without reading source code.

## Task 7: End-to-end verification and integration

**Files:**

- Modify only if verification reveals a defect.

**Step 1: Add/execute a deterministic CLI smoke fixture**

Run `run-playbook` in dry-run mode with a valid hands-on or fact-translation
fixture. Assert `status == completed`, `publish_result.status == dry_run`, and
the artifact has the safe AI evidence manifest. Run a missing-evidence CLI call
and assert it returns the required diagnostic with no publish attempt.

**Step 2: Run full validation**

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --base-ref main --strict
git diff --check
```

**Step 3: Independent review and integration**

Request a spec review and code-quality review. Address actionable findings,
re-run the affected tests, commit the feature branch, run strict harness against
the committed diff, then merge and push only after successful verification.

**verify:** all commands exit 0; real publishing is never invoked.

**done_when:** three evidence-backed modes are enforced end-to-end, docs and
installed skill are synchronized, and a clean dry-run demonstrates the
operator-facing contract.
