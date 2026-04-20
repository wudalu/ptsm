---
title: Harness Engineering In PTSM
status: active
owner: ptsm
last_verified: 2026-04-20
source_of_truth: true
related_paths:
  - README.md
  - docs/index.md
  - docs/plans/2026-04-17-harness-engineering-first-stage.md
  - docs/plans/2026-04-20-docs-sync-gate.md
  - docs/plans/2026-04-20-harness-enforcement.md
  - src/ptsm/application/use_cases/docs_sync.py
  - src/ptsm/application/use_cases/harness_check.py
  - src/ptsm/application/use_cases/install_git_hooks.py
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
- an installable pre-push hook plus GitHub workflow so the same harness rules run locally and in CI
- a two-tier enforcement model: practical local gates by default, full `--strict` gates in CI branch protection
- mechanical architecture checks for import boundaries
- durable local runtime memory and checkpoints
- queryable run summaries and run events
- verification evidence artifacts for `run-plan` verify loops
- normalized plan-run failure reasons and evidence query CLI
- drift checks and safe garbage collection for stale harness artifacts
- local harness eval summaries over runs, events, and plan-run evidence
- an operational `harness-report` snapshot that composes `doctor`, `gc`, and `harness-evals`
- threshold checks that let local automation treat harness drift or reliability regressions as warnings
- a publish diagnostic surface that classifies likely failure causes and returns next actions for a single publish attempt
- side-effect ledger for safe publish replay on the same `thread_id`
- provider-backed image generation that can fill missing publish images and persist evidence into artifacts

## What We Should Build Next

- traces and metrics if local file observability stops being enough

## What We Should Not Copy Blindly

- minimal merge gates on external side-effecting publish flows
- assumptions that every agent-generated pattern is worth preserving
- policies optimized for a million-line, high-throughput product without local adaptation
