---
title: PTSM Runtime
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/agent_runtime
  - src/ptsm/infrastructure/memory/store.py
---

# Runtime

The runtime centers on a `plan -> execute -> reflect` loop and writes artifacts
and run events to the local filesystem.
