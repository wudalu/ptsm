---
title: Harness Engineering In PTSM
status: active
owner: ptsm
last_verified: 2026-04-18
source_of_truth: true
related_paths:
  - README.md
  - docs/index.md
  - docs/plans/2026-04-17-harness-engineering-first-stage.md
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
- mechanical architecture checks for import boundaries
- durable local runtime memory and checkpoints
- queryable run summaries and run events
- verification evidence artifacts for `run-plan` verify loops
- normalized plan-run failure reasons and evidence query CLI
- drift checks and safe garbage collection for stale harness artifacts

## What We Should Build Next

- traces and metrics if local file observability stops being enough

## What We Should Not Copy Blindly

- minimal merge gates on external side-effecting publish flows
- assumptions that every agent-generated pattern is worth preserving
- policies optimized for a million-line, high-throughput product without local adaptation
