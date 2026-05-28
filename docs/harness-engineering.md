---
title: Harness Engineering In PTSM
status: active
owner: ptsm
last_verified: 2026-05-29
source_of_truth: true
related_paths:
  - README.md
  - docs/index.md
  - docs/plans/2026-04-17-harness-engineering-first-stage.md
  - docs/plans/2026-04-20-docs-sync-gate.md
  - docs/plans/2026-04-20-harness-enforcement.md
  - src/ptsm/application/use_cases/docs_sync.py
  - src/ptsm/application/use_cases/eval_artifact.py
  - src/ptsm/application/use_cases/harness_check.py
  - src/ptsm/application/use_cases/install_git_hooks.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
  - src/ptsm/evaluations/contracts_eval.py
  - src/ptsm/playbooks/definitions
---

# Harness Engineering In PTSM

This document maps the OpenAI harness-engineering article onto the current PTSM
repository.

## What We Should Borrow

- repository knowledge as the system of record
- short, navigable docs instead of one monolithic instruction file
- agent readability as a first-class engineering concern
- observability that agents can inspect directly

## What PTSM Already Has

- a working CLI entrypoint
- local run artifacts and run logs
- playbook and skill registries
- a stable pytest-based verification loop
- a docs map with source-of-truth pointers
- freshness and ownership metadata on active docs
- a path-aware `docs-sync` gate that uses `related_paths` to block code changes that skip their most specific source-of-truth docs
- a single `harness-check` entrypoint that runs the docs gate, local harness drift checks, and deterministic pytest
- targeted docs tests for operational contracts that `docs-sync` cannot infer from docs-only prose changes
- an installable pre-push hook plus GitHub workflow so the same harness rules run locally and in CI
- a two-tier enforcement model: practical local gates by default, full `--strict` gates in CI branch protection
- mechanical architecture checks for import boundaries
- durable local runtime memory and checkpoints
- queryable run summaries and run events
- verification evidence artifacts for `run-plan` verify loops
- normalized plan-run failure reasons and evidence query CLI
- drift checks and safe garbage collection for stale harness artifacts
- local harness eval summaries over runs, events, and plan-run evidence
- skill-aware harness eval summaries over runs, including per-skill completion rate and runtime-context usage
- an operational `harness-report` snapshot that composes `doctor`, `gc`, and `harness-evals`
- threshold checks that let local automation treat harness drift or reliability regressions as warnings
- a publish diagnostic surface that classifies likely failure causes and returns next actions for a single publish attempt
- side-effect ledger for safe publish replay on the same `thread_id`
- provider-backed image generation that can fill missing publish images and persist evidence into artifacts
- a local-first evaluation system with rule evaluators, contract evaluators, and structured eval results stored under `.ptsm/evals`
- `eval-artifact` CLI command to run deterministic evaluators against any PTSM artifact
- eval result aggregation in `harness-evals` and `harness-report` with configurable failure thresholds
- scoped eval aggregation by run/account/platform/playbook metadata, so filtered harness views do not mix unrelated eval runs
- gate-aware eval accounting: `required_failed` can block local harness, while `warning_failed` remains a reporting signal
- an LLM judge adapter that requires explicit enablement in evals and fake-backend tests, keeping default harness deterministic
- a required content quality judge for XHS executor output when enabled/configured; it returns calibrated dimensions (`hook_specificity`, `save_trigger`, `comment_trigger`, `platform_native_format`, `persona_fit`, `safety`) plus a rewrite hint, and generation uses failed judge output as a retry signal before human review. Runtime judge activation is now driven by each playbook's `evaluation.yaml`, not a hard-coded playbook list.
- generic playbook node-contract constraints for final-content text and hashtag checks, so high-risk domains can gate required tags, required safety language, forbidden claims, anti-generic titles/covers, title substring bans, body length bands, comment prompts, save/tool triggers, and experiment-instruction leakage without adding runtime branches
- XHS human-voice contract coverage through generic node constraints: `title_must_include_any` requires concrete title hooks for key playbooks, `title_must_not_include_any` blocks泛标题 substrings such as `日常` / `实录` / `干货分享`, `body_min_chars` / `body_max_chars` enforce domain-specific length bands, and `combined_must_not_include_any` scans title, cover text, and body together for template markers such as `首先`、`其次`、`综上`、`本文`、`作为AI` and other non-human/meta phrasing. The same deterministic path now covers psychology-native constraints: `modern_psychology_post` titles must avoid mechanism terms and `不是你`, bodies are capped at 580 chars, and comment prompts must use role/camp/fill-in triggers rather than generic experience questions.
- World Cup domain constraints now use the same playbook-local eval contract and deterministic dry-run harness path, including required `#世界杯`, fan-readable match mechanics, save/comment triggers, and blocking betting, odds, score-prediction, and fake insider/official-source claims
- Reddit curation constraints use the same playbook-local eval contract and deterministic dry-run harness path, including Chinese topical tags, Chinese adaptation, save/comment triggers, and blocking visible Reddit/source URL/subreddit/translation-process leakage, fake first-hand claims, psychology treatment promises, investment advice, and instruction leakage
- local code-rendered social image generation for XHS covers when auto image generation is requested and external image providers are not configured, including deterministic note-card, iPhone Notes-like, and WeChat chat transcript-like layouts
- first-class XHS image strategy through `xhs_image_strategy` and `final_content.image_plan`, so deterministic dry-runs and artifacts can prove when local social screenshots are selected intentionally instead of only as provider fallback
- a deterministic, local-first XHS pattern library loop: periodic `collect-xhs-patterns` persists partial MCP samples, `analyze-xhs-patterns` distills them into local format snapshots, and ordinary generation consumes `current.json` without live XHS calls
- a deterministic, local-first cross-domain `guide-post` harness surface: domain tests cover the generic selector, including scene-keyword/lane-affinity separation, diversity-family selection, multiple open-scene candidates, and dynamic breadth reranking; application tests cover all current topic packs, larger-than-display candidate pools, scene-varying direction sets, `topic_guidance.image_recommendation`, and the `dynamic_scene_diversity_rerank` contract; CLI tests cover JSON/Markdown output with `direction_type`, `open_direction_ids`, `direction_type_counts`, and image recommendation fields; docs tests lock the generic and psychology OpenClaw wrapper contracts
- a modern psychology relationship-uncertainty regression harness: unit tests now lock `他3小时没回消息，我已经想好分手后猫归谁了` to `亲密关系 / 不确定感`, `relationship_uncertainty_waiting_message`, `iphone_notes`, and deterministic copy that uses `事实 / 脑补 / 我需要什么` rather than workplace reply wording

## New Domain Documentation Completeness

`docs-sync` is a minimum gate, not a complete domain-readiness proof. Every new
domain or playbook must update the 完整文档面 before merge:

- `architecture.md`
- `runtime.md`
- `playbooks.md`
- `skills.md`
- `harness-engineering.md`
- `docs/operations.md`
- affected `docs/operations/` runbooks

The required plan must include this checklist explicitly. If a surface does not
change, the plan or handoff must record why. This keeps operator commands,
dry-run examples, publish guidance, harness expectations, and domain contracts
discoverable from the repository rather than from memory.

## What We Should Build Next

- traces and metrics if local file observability stops being enough
- calibrated LLM judge suites after enough dry-run, pattern-library and publish examples exist; current human review stays lightweight through each artifact's `content_review` plus operator conversation, not a separate review queue or approval UI
- richer skill quality evals if completion-rate aggregation stops being enough

## Docs-Only Cleanup Gap

`docs-sync` is intentionally code-to-doc coverage, not a semantic Markdown
validator. It looks at changed code paths under `src/ptsm/**` and
`shared_contracts/**`, then checks whether the most specific source-of-truth doc
surface was also touched. A docs-only runbook edit has no relevant code path, so
`docs-sync` returns ok by design.

The previous gap was not that `harness-check` skipped pytest. It was that the
docs tests only asserted metadata and broad keywords, so stale publishing claims
such as "dry-run never generates images", "local screenshots are fallback only",
or "real-publish watermark removal is optional" had no machine-checkable
contract. For docs-only cleanup that changes operator behavior, add a focused
`tests/unit/docs/` assertion and run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap harness-check --changed-path docs/<changed-doc>.md
```

## What We Should Not Copy Blindly

- minimal merge gates on external side-effecting publish flows
- assumptions that every agent-generated pattern is worth preserving
- policies optimized for a million-line, high-throughput product without local adaptation
