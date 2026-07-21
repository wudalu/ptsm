# Hotspot novelty and compact XHS copy plan

> **For the implementation team:** execute this plan task by task with test-first changes. Keep `topic_radar` independent of `ptsm`; ordinary playbook runs must remain local-pattern-only unless `--fresh-topic-research` is explicit.

## Goal

Make the existing eight-platform Topic Radar produce evidence-backed, non-duplicated topic candidates, and make all XHS playbooks default to a shorter, more native, human-sounding copy contract without relaxing any domain safety rules.

## Architecture and boundaries

- `topic_radar` owns platform collection, canonical identity, event clustering, scan quality, candidate diversity, and artifact provenance. It must not import `ptsm`.
- `ptsm` consumes the public `topic_radar.cli.run_scan()` API only for explicit fresh research. It receives selected angle metadata, never raw source titles, authors, URLs, feed IDs, or tokens in a drafting context.
- The currently supported platform set is `xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai`; this work strengthens those integrations rather than inventing unsupported sources.
- `xhs-domain-opportunity` remains a bounded XHS search-evidence operator report, not a whole-site or cross-platform trend ranking.
- `xhs_compact_native_v1` is a shared default generation contract rather than a new user-facing switch: 2–4 short beats, a concrete scene and human anchor, one usable action, and a natural reply opening. Wuxia retains its long-form exception; all safety/hashtag/source contracts remain enforced.

## Verification matrix

| Area | verify | done_when |
| --- | --- | --- |
| Eight-platform collection | `uv run pytest tests/unit/topic_radar/test_cli.py tests/unit/topic_radar/test_evidence.py -q` | empty platforms become explicit errors, aliases resolve, and all eight requested collectors participate in the canonical path |
| Evidence/novelty | `uv run pytest tests/unit/topic_radar/test_evidence.py tests/unit/topic_radar/test_cross_platform.py tests/unit/topic_radar/test_output.py -q` | duplicate XHS feeds collapse, event variants cluster, cross-platform claims have >=2 real platforms, and recent identical event+angle candidates are suppressed |
| PTSM handoff | `uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/application/use_cases/test_run_playbook.py -q` | fresh research invokes public `run_scan`, preserves quality/selection metadata, and does not leak source-level identifiers to drafting |
| XHS domain opportunity | `uv run pytest tests/unit/application/use_cases/test_xhs_domain_opportunity.py -q` | zero/error evidence yields `insufficient_evidence` and no static ranking; repeated feeds aggregate once per domain |
| Compact copy | `uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/evaluations/test_playbook_contracts.py tests/e2e/test_xhs_title_body_quality_contracts.py -q` | nine deterministic playbooks meet revised length bands, retain scene/human/action/reply and safety gates, and prompt asks for compact non-template prose |
| Docs/harness | `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_architecture_doc.py -q`; `uv run python -m ptsm.bootstrap doctor`; `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict` | every affected source-of-truth surface describes the new contract and the strict harness is green |

## Task 1: Canonical full-platform evidence pipeline

**Files:**
- Create: `src/topic_radar/analysis/evidence.py`
- Modify: `src/topic_radar/cli.py`
- Modify: `src/topic_radar/output/artifacts.py`
- Modify: `src/topic_radar/config.py`
- Test: `tests/unit/topic_radar/test_evidence.py`
- Test: `tests/unit/topic_radar/test_cli.py`
- Test: `tests/unit/topic_radar/test_output.py`

1. Write failing unit tests for platform aliases (`xhs`), empty collector results, duplicate XHS `feed_id`, no-ID fallback identity, platform-local heat normalization, and schema-v2 scan quality serialization.
2. Add pure evidence dataclasses/helpers with canonical titles, source identity, query-term merge, platform-local normalized heat, deterministic event fingerprints, and scan quality (`completed`, `partial`, `insufficient_evidence`).
3. Route all collectors through the one canonical post-collection pipeline. Never put an empty list in `all_trending`; retain partial failures; do not call the LLM if valid evidence is empty.
4. Add optional, backwards-compatible artifact fields: `schema_version`, `scan_quality`, `evidence`, and `topic_clusters`. Preserve `raw_trending` and existing result fields.
5. Run the task tests and then the full topic-radar unit suite.

**verify:** `uv run pytest tests/unit/topic_radar/test_evidence.py tests/unit/topic_radar/test_cli.py tests/unit/topic_radar/test_output.py -q`

**done_when:** The public `run_scan()` returns a truthful partial/insufficient status, emits no recommendation from zero evidence, and records one canonical evidence row per source observation.

## Task 2: Event clustering, evidence-backed diversity, and scan-history cooldown

**Files:**
- Modify: `src/topic_radar/analysis/evidence.py`
- Modify: `src/topic_radar/analysis/cross_platform.py`
- Modify: `src/topic_radar/analysis/llm_analyzer.py`
- Modify: `src/topic_radar/analysis/schemas.py`
- Modify: `src/topic_radar/cli.py`
- Modify: `src/topic_radar/output/artifacts.py`
- Test: `tests/unit/topic_radar/test_evidence.py`
- Test: `tests/unit/topic_radar/test_cross_platform.py`
- Test: `tests/unit/topic_radar/test_llm_analyzer.py`

1. Write failing tests for paraphrased same-event clustering, non-match isolation, actual-platform-only cross-platform signals, one-event-per-top-N diversity, invalid LLM evidence references, and a recent `(event_fingerprint, angle_signature)` cooldown.
2. Build clusters deterministically from canonical titles/Chinese n-gram overlap; keep evidence IDs and per-platform support. Cross-platform signals must derive from clusters, not LLM-asserted platform names.
3. Supply the LLM with IDs/clusters and permit it only to label/select existing evidence. Validate its sample/evidence references and drop unsupported outputs; rules fallback remains available.
4. Use deterministic MMR-style selection to avoid multiple angles from the same event in one scan. Persist a small append-only scan history beneath the output directory and suppress recent duplicate event+angle candidates while allowing a new event/angle.
5. Run topic-radar tests including existing regression suites.

**verify:** `uv run pytest tests/unit/topic_radar -q`

**done_when:** A report cannot call an XHS-only item cross-platform, repeated rephrasings occupy one event slot, and repeating the same event+angle within the cooldown does not fill the next report.

## Task 3: PTSM fresh-research and domain-opportunity truthfulness

**Files:**
- Modify: `src/ptsm/skills/runtime_context.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/application/use_cases/xhs_domain_opportunity.py`
- Test: `tests/unit/skills/test_runtime_context.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/application/use_cases/test_xhs_domain_opportunity.py`

1. Write failing tests proving the runtime context calls public `topic_radar.cli.run_scan()` with the default eight platforms, preserves partial/insufficient state, and continues to avoid live scans for ordinary/deterministic runs.
2. Replace the duplicated two-platform runtime scan with the public scan API. Render only evidence-backed selected direction/angle metadata into the prompt; redact source-level titles, URLs, authors, IDs, and tokens.
3. Add feed-level de-duplication to `xhs-domain-opportunity`, aggregate recommendations once per domain, and require non-zero successful samples before emitting a ranked recommendation or "new domain" candidate.
4. Use `insufficient_evidence` for all-empty/all-error scans and explicitly describe partial data rather than static mapping tiers as discovered evidence.
5. Run targeted unit tests and the relevant playbook selection tests.

**verify:** `uv run pytest tests/unit/application/use_cases/test_xhs_domain_opportunity.py tests/unit/skills/test_runtime_context.py tests/unit/application/use_cases/test_run_playbook.py -q`

**done_when:** Fresh mode has one full-platform path, normal mode remains offline/local, and no zero-sample domain scan invents a ranked opportunity.

## Task 4: Default `xhs_compact_native_v1` copy contract

**Files:**
- Modify: `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/playbooks/definitions/*/evaluation.yaml`
- Modify as needed: `src/ptsm/playbooks/definitions/*/planner.md`
- Modify: `src/ptsm/evaluations/llm_judge.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`
- Test: `tests/unit/evaluations/test_playbook_contracts.py`
- Test: `tests/unit/evaluations/test_content_quality_judge.py`
- Test: `tests/e2e/test_xhs_title_body_quality_contracts.py`

1. Write failing prompt/contract tests: compact 2–4 short beats, no mandatory four independent sections, natural combined action/reply, new body length bands, title max/fallback safety, and non-template wording.
2. Update the shared human-voice skill and DeepSeek requirements to name `xhs_compact_native_v1`: front-load lived scene, retain one domain-specific usable detail, permit a save/reply in one sentence, and prohibit writing-course labels and artificial step explanations.
3. Align factory, planner, and evaluator length bands: fengkuang 90–220; enrichment/poetry 120–280; English 140–300; psychology 200–380; AI/World Cup/Reddit 180–420; wuxia 450–750. Keep explicit extended-asset exceptions only where required source material/prompt is present.
4. Replace generic minimum-character padding with contextual short additions so deterministic drafts do not append the same canned paragraph. Keep every domain's existing safety, source, hashtag, and professional-help constraints.
5. Change title tension from one universal wording list to domain-appropriate concrete-entry validation/prompt preference; do not force English, poetry, or World Cup titles into the same dramatic phrasing.
6. Update the LLM judge rubric to reward concise oral rhythm, concrete detail, and non-template endings without making subjective judge output a hard deterministic gate.
7. Run all compact-copy tests and representative deterministic dry-runs.

**verify:** `uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/evaluations/test_playbook_contracts.py tests/unit/evaluations/test_content_quality_judge.py tests/e2e/test_xhs_title_body_quality_contracts.py -q`

**done_when:** The nine playbooks are materially shorter except the permitted wuxia form, still pass all safety/format gates, and the shared prompt/skill no longer demands an essay-like four-part structure.

## Task 5: Source-of-truth docs, regression, and merge

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/observability.md`
- Modify: `docs/topic-radar.md`
- Modify: `docs/operations/topic-radar-runbook.md`
- Review and explicitly mark unchanged in handoff if appropriate: `docs/operations/local-runbook.md`, `integrations/openclaw/*/SKILL.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`
- Test: `tests/unit/docs/test_architecture_doc.py`

1. Document the canonical full-platform collection, evidence quality states, event cluster / novelty fields, fresh-only PTSM handoff, zero-evidence behavior, compact copy mode, and operator diagnosis for partial scans.
2. Update any artifact examples/schema references and observability fields. State that topic-radar is still independent and that `xhs-domain-opportunity` remains bounded XHS evidence.
3. Run changed-path docs-sync and harness checks, then full tests, doctor, and strict base-ref harness.
4. Request a spec-compliance review followed by a code-quality review; address findings before final verification.
5. Merge the verified feature branch to `main` without touching unrelated untracked root-worktree files.

**verify:** `uv run pytest -q --ignore=tests/e2e`; `uv run python -m ptsm.bootstrap doctor`; `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict`

**done_when:** Docs match implementation, all verification is green, the feature branch is merged to `main`, and the original workspace's unrelated files remain untouched.

## Review follow-up: evidence-boundary and resilience fixes

Independent code review found and this implementation addresses the following
operator-facing edge cases before merge:

1. Ordinary/local-only `topic_research` must not consume an ambient same-day
   Topic Radar artifact; only the current explicit fresh receipt is eligible.
2. Rules fallback must emit concrete angles and selector defense-in-depth must
   reject unexpanded `{placeholder}` fields.
3. XHS and trends-hub MCP tool loading must be server-isolated, so a failed
   service leaves healthy platform collection available as `partial` evidence.
4. Event clustering must reject incompatible weather/AI core terms; static
   cross-platform snapshots must not claim temporal acceleration.
5. Source-title redaction must protect copied specific titles and all raw
   provenance without treating a short generic term (for example `AI`) as a
   prohibited source leak inside a genuinely new angle.
6. Separator-only XHS keyword input must safely use defaults, and
   domain-opportunity dedup must distinguish authoritative feed IDs from
   title+author bridge aliases.
7. Fresh context consumption must require the exact current scan receipt and a
   readable receipt artifact; it must not infer a same-day artifact path.
8. A title+author alias may bridge one ID-less XHS observation to the first
   real feed ID only; later distinct feed IDs with the same visible identity
   stay separate.
9. Prompt caps must be platform-balanced, and every prompt-visible cluster
   must reference only evidence rows visible in that same prompt.
10. Both Topic Radar and domain-opportunity keyword parsing must accept ASCII
    and full-width commas, with separator-only input falling back to bounded
    default queries.
11. Fresh `topic_selection` metadata must retain opaque traceability only, not
    the terminal scan summary or raw source material.
12. Once a title+author bridge has more than one authoritative feed ID, a later
    ID-less observation must remain unresolved instead of merging into an
    arbitrary source; compact deterministic fallbacks must satisfy their own
    playbook executor contracts for short scenes and memory alternatives.

**verify:** targeted regression tests in `tests/unit/topic_radar`,
`tests/unit/skills/test_runtime_context.py`, and
`tests/unit/application/use_cases/test_xhs_domain_opportunity.py`, followed by
the full unit suite, e2e compact-copy contracts, docs checks, and strict
harness check.
