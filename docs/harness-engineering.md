---
title: Harness Engineering In PTSM
status: active
owner: ptsm
last_verified: 2026-08-14
source_of_truth: true
related_paths:
  - README.md
  - docs/index.md
  - docs/plans/2026-04-17-harness-engineering-first-stage.md
  - docs/plans/2026-04-20-docs-sync-gate.md
  - docs/plans/2026-04-20-harness-enforcement.md
  - src/ptsm/application/use_cases/docs_sync.py
  - src/ptsm/application/use_cases/eval_artifact.py
  - src/ptsm/application/use_cases/xhs_post_metrics.py
  - src/ptsm/application/use_cases/harness_check.py
  - src/ptsm/application/use_cases/install_git_hooks.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/psychology_learning_series.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/psychology_carousel.py
  - src/ptsm/application/services/image_carousel_transaction.py
  - integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
  - integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md
  - integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/evaluations/contracts_eval.py
  - src/ptsm/playbooks/definitions
  - src/topic_radar/analysis/evidence.py
  - src/topic_radar/cli.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/application/use_cases/run_playbook.py
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
- XHS human-voice contract coverage through generic node constraints: `title_max_chars` caps every XHS playbook title at 22 chars; domain-specific concrete-entry and forbidden-title constraints replace the old universal tension-keyword gate; `title_must_not_include_any` blocks泛标题 substrings such as `日常` / `实录` / `干货分享`; `body_min_chars` / `body_max_chars` enforce compact domain bands; `body_must_include_scene_signal` with `body_scene_signal_any` requires body-specific scene/object/relationship/action terms; `body_human_anchor_any` requires first-person/direct-reader/time/place anchors; and `combined_must_not_include_any` scans title, cover text, and body together for template markers such as `首先`、`其次`、`综上`、`本文`、`作为AI` and other non-human/meta phrasing. Prompt/contract/e2e tests lock `xhs_compact_native_v1`: 2–4 short beats, one usable domain detail, a natural combined save/reply opening, shorter body bands, no generic minimum-character padding, and preserved safety/tag/source gates. The same deterministic path covers psychology-native constraints: `modern_psychology_post` titles must avoid mechanism terms and `不是你`, bodies are capped at 380 chars, and comment prompts must use role/camp/fill-in triggers rather than generic experience questions.
- World Cup domain constraints now use the same playbook-local eval contract and deterministic dry-run harness path, including required `#世界杯`, fan-readable match mechanics, save/comment triggers, and blocking betting, odds, score-prediction, and fake insider/official-source claims
- Reddit curation constraints use the same playbook-local eval contract and deterministic dry-run harness path, including Chinese topical tags, Chinese adaptation, save/comment triggers, and blocking visible Reddit/source URL/subreddit/translation-process leakage, fake first-hand claims, psychology treatment promises, investment advice, and instruction leakage
- local code-rendered social image generation for XHS covers when auto image generation is requested and external image providers are not configured, including deterministic note-card, iPhone Notes-like, and WeChat chat transcript-like layouts
- first-class XHS image strategy through `xhs_image_strategy` and `final_content.image_plan`, so deterministic dry-runs and artifacts can prove when local social screenshots are selected intentionally instead of only as provider fallback
- a deterministic, local-first XHS pattern library loop: periodic `collect-xhs-patterns` persists partial MCP samples, `analyze-xhs-patterns` distills them into local format snapshots, and ordinary generation consumes `current.json` without live XHS calls
- a Topic Radar evidence/novelty harness: unit tests cover aliases and all eight requested collectors, server-isolated MCP failures and hanging tool discovery, empty-result diagnostics, XHS feed/source de-duplication with one-time ID-less bridge consumption and unresolved ambiguity after multiple real IDs, query provenance, platform-local heat normalization, `completed` / `partial` / `insufficient_evidence`, conservative event clustering with incompatible weather and AI content slots, real-platform-only cross-platform signals without fabricated temporal velocity, balanced LLM prompt caps whose clusters only cite visible evidence, LLM evidence-reference/template validation before rules fallback, concrete rules fallback angles without template placeholders, ASCII/full-width keyword separators with safe defaults, same-scan one-event diversity, paired artifact suffixes, and the 14-day append-only event+angle cooldown
- a PTSM fresh-research boundary harness: tests prove `run-playbook --fresh-topic-research` calls public `topic_radar.cli.run_scan()` once without replacing its platform default, blocks before workflow on insufficient evidence, preserves partial diagnostics/opaque selection metadata without `scan_summary`, does not leak source title/author/URL/feed/token into drafting, never lets ordinary/local-only builders reuse an old Topic Radar artifact, fails closed when the exact fresh receipt lacks a readable artifact, and prevents a second live scan or competing topic-research context. Compact-copy tests additionally exercise minimum-length short-scene branches, the enrichment fallback scene anchor, the Wuxia short-scene band, and memory-triggered alternate psychology drafts against their real executor contracts.
- a deterministic, local-first cross-domain `guide-post` harness surface: domain tests cover the generic selector, including scene-keyword/lane-affinity separation, diversity-family selection, multiple open-scene candidates, dynamic breadth reranking, and public `format_recommendation` serialization; application tests cover all current topic packs, larger-than-display candidate pools, scene-varying direction sets, `topic_guidance.image_recommendation`, direction-level format recommendations, and the `dynamic_scene_diversity_rerank` contract; CLI tests cover JSON/Markdown output with `direction_type`, `open_direction_ids`, `direction_type_counts`, format recommendation, and image recommendation fields; run-playbook and agent-runtime tests cover `topic_direction_id` resolution into response/artifact metadata and `# XHS Topic Direction Guidance` runtime context before drafting; docs tests lock the generic, psychology, and domain-opportunity OpenClaw wrapper contracts
- an AI-tech evidence-mode harness: domain tests lock three typed bundles—`news_brief` has 3–5 distinct events and opaque source refs, `hands_on` has one reproducible product/version/date/task/input/output/limitation record plus opaque test evidence, and `fact_translation` has one topic, two facts and explicit audience decisions. CLI/use-case tests require `--ai-content-mode` + `--ai-evidence-file` before a run, reject malformed/mismatched bundles before RunStore/workflow/artifact/image/publish, and reject stale or cross-mode `topic_direction_id`. Runtime boundary tests prove that only the provenance-safe contract reaches planner/executor and that arbitrary direct workflow input or unsafe model draft cannot enter LangGraph checkpoints. Draft, artifact and publish guards reject raw locators, non-hands-on fake experience, incomplete tests and foreign/provenance-bearing artifacts. `guide-post` exposes only exact-mode authored directions; prompt directions remain `hands_on` test records, not a generic copyable-prompt fourth mode. Finalize writes a safe receipt and the offline `ai_tech.evidence_receipt` evaluator audits mode, manifest, gate and visible draft without making eval the publish authority. AI `--fresh-topic-research` is locked to a separate discovery response so Topic Radar can contribute only opaque `trend_support`, never publishable facts or tests.
- a psychology learning-series harness: domain tests lock builtin `after_work_rumination` plus safe 2–6 lesson custom proposals, deterministic publication order, immutable `user_confirmed` revision snapshots and failed closed resolution after any tamper/missing snapshot. CLI tests require proposal `series.lessons` plus top-level `publication_plan`, exact `proposal_fingerprint` + `confirm-psychology-series --confirm`; guide tests require a `selection_required` roadmap rather than silently choosing lesson one, and a user-selected explicit frozen version/direction even when the choice is non-recommended. Custom-only guide tests lock `series.publication_plan`, `series.recommended_next_lesson`, and `series.production_progress.kind == operator_content_production`; builtin roadmaps omit those fields. Runtime/eval/metrics tests prove that custom artifacts carry a strict `psychology_learning_catalog_receipt` (`schema_version`, `origin`, controlled template version, catalog digest, approval id, proposal fingerprint and publication plan); builtin artifacts omit it. Missing/tampered catalog or receipt fails closed without raw topic/outline/source/path leaks to state, checkpoints, prompt, memory, response or artifact. The same exact `psychology_learning_draft_contract` gates deterministic/model drafts at executor, reflector, finalize and pre-publish layers; free-scene reflection/judge rules cannot retry a catalog-valid lesson. Progress updates occur only after a safe completed artifact/receipt (including dry-run or publish failure after content success), never after preflight/workflow/eval/final-artifact failure, and tests verify idempotent concurrent updates. `psychology.learning_receipt` and `eval-artifact` reconstruct the expected lesson and scan the entire artifact for raw provenance. Metrics tests lock receipt-verified series/version/lesson grouping, same artifact/checkpoint upsert and the existing `needs_more_data` threshold.
- the same learning-series harness also locks the trusted `provision-psychology-learning-storage` precondition and its fixed private `proposals` / `confirmations` / `catalogs` / `progress` tree. It exercises symlink, hardlink, rebinding, temporary-source and payload races inside a transaction; an unsafe artifact is retained rather than path-cleaned online, and `psychology_learning_progress_persist_failed` is tested as at-least-once with idempotent retry. These checks demonstrate transaction-scoped fail-closed behavior, not continuous same-UID at-rest anti-tamper: residual inspection/rebuild/removal belongs to trusted offline maintenance with all writers stopped.
- a classic poetry quote domain harness: unit and e2e tests lock `classic_poetry_quote_post` to `acct-classic-poetry-local`, `classic_poetry_style`, `xhs_classic_poetry_hashtagging`, quote-led body structure, `#古诗词`, and guide-post directions such as Li Bai `长风破浪会有时`, Li Qingzhao, Wang Wei, and optional Su Shi. Generic poetry scenes must not be routed back to forced `#苏轼` content.
- a modern psychology relationship-uncertainty regression harness: unit tests now lock `他3小时没回消息，我已经想好分手后猫归谁了` to `亲密关系 / 不确定感`, `relationship_uncertainty_waiting_message`, a semantic text-carousel recommendation, and deterministic copy that uses `事实 / 脑补 / 我需要什么` rather than workplace reply wording
- a modern psychology growth-direction guidance harness: unit tests lock `relationship_mixed_signal_camp_vote`, `social_battery_cancel_plan_boundary`, and `after_hours_message_body_alarm` as first `guide-post` directions for exact high-intent scenes, including bounded `psychology_text_card_v1` recommendations, concrete saveable tools, and A/B or A/B/C comment prompts; deterministic draft tests cover the two previously generic paths, `忽冷忽热` and `社交电量取消局`, without claiming post-metrics uplift
- a modern psychology growth-sublane regression harness: unit tests now lock sleep recovery/light-wellness scenes to `睡眠恢复 / 轻养生`, `sleep_recovery_shutdown_card`, and semantic text-carousel guidance; e2e deterministic dry-run tests require a concise concrete title, 200-380 char body, 5-minute shutdown/save tool, role/camp comment prompt, professional-help boundary, and valid 4–7-page plan without medical wellness claims
- a psychology text-carousel harness: domain/drafting/runtime tests lock the exact closed parent fields plus slide-only `slide_id/order/role/headline/body_lines`, 4–7 contiguous pages, one-topic semantic roles, nested model normalization, safety scanning, and unchanged legacy/non-psychology plans. Learning tests lock historic controlled-template-v1 single-card receipts and current v2 catalog-owned 7-page reconstruction. Renderer/transaction tests cover 1080×1440 role variants, content-addressed manifests, page/file hashes, path containment, idempotent reuse and atomic complete-set visibility. Run/ledger/publisher tests require manifest order, set-wide descriptor/snapshot verification, lock-serialized page-aware ledger projection under concurrent appends, and descriptor-pinned `base_dir` plus fixed `outputs/artifacts/generated-image-assets` ancestors opened/created one component at a time with `dir_fd` + no-follow. Regressions rebind or replace intermediate ancestors around locking, replace and directory fsync and require fail-closed behavior; the same suite requires local watermark skip and zero publisher side effects on page, manifest or ledger failure, with stable status `psychology_carousel_generation_failed`. Requested-image learning tests advance production progress only after the complete set, page-aware operational ledger and strict artifact pass, while no-image tests retain the prior content-artifact timing.
- guide/docs/wrapper tests lock ordinary `format_archetype=text_carousel`, local `psychology_text_card_v1`, 4–7 page range and ordered semantic roles without introducing a manual pagination flag. Current learning directions expose the exact 7-role carousel format while historic controlled-template-v1 directions remain `note_card`; the wrapper may display only PTSM-returned `page_count` / `ordered_roles` structure, must not claim `guide-post` returned page copy, and may not author page text or add an image override.
- a local XHS post metrics loop: unit tests lock artifact-linked `xhs-record-metrics` rows, score/rate calculation, checkpoint validation, and `xhs-metrics-report` grouping by psychology topic direction, image style, or `carousel_style`. Rows also normalize `image_count`: verified carousels retain their page count, while historic/single-cover artifacts remain count `1` with empty carousel style. Growth claims therefore stay tied to recorded views/likes/collects/comments/shares rather than dry-run quality alone.

This feature intentionally leaves three harness surfaces unchanged: the cross-domain minimum
`shared_contracts/evaluation/final_content.schema.yaml`, Topic Radar discovery/routing contracts, and
task-completion automation semantics. Psychology-specific nested validation is stricter at domain/runtime/eval
boundaries; it must not broaden the shared eval schema or redefine when a generic development task is complete.

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

## Discovery-First Hotspot Contracts

`hotspot-discovery` 的 deterministic contract 覆盖：调用 public scan 时没有
domain/playbook/account/keyword filter、只消费 evidence-consistent cluster、按 score 稳定排序并以
透明的 Top-N receipt 截断，同时从同一次完整 scan 以不重复补充视图保留低排名的 routed candidate、
保留 `completed` / `partial` / `insufficient_evidence` 诊断，并在 artifact 中隔离来源字段。
cluster 的 representative title 必须由其 evidence 支持，非有限 score 必须归零，未知质量状态必须 fail closed，
避免损坏 artifact 影响路由或被误报为 completed。
测试还锁定 `existing_playbook_fit` / `ambiguous` / `unmapped` 与 evidence-rich
`new_domain_candidate`：后者只能触发 review，不得自动创建新 playbook。

文档 wrapper contract 同时锁定 `ptsm-topic-radar-discovery` 对宽泛热点请求运行
`hotspot-discovery`，而 `ptsm-xhs-domain-opportunity` 必须要求显式关键词并转交泛发现请求。
任何修改这些入口、artifact 或 operator 状态语义的变更都应更新 focused docs test，并运行
`harness-check --changed-path ...`。
