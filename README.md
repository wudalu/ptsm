# PTSM

Playbook-driven social media agent runtime.

## Current Baseline

This repository already contains a working `fengkuang` MVP vertical slice. The
current stable baseline includes:

- local account discovery
- playbook registry and asset loading
- builtin skill registry and on-demand loading
- a LangGraph-backed `fengkuang` workflow
- dry-run publishing and XiaoHongShu MCP publish integration
- local run artifacts and observability

## Planning Source Of Truth

`docs/plans/2026-03-14-ptsm-agent-platform.md` is historical greenfield context.
It reflects the earlier "empty scaffold" stage and should not be treated as the
current execution plan.

`docs/plans/2026-03-24-ptsm-agent-platform-rebaseline.md` is the current
implementation source of truth. It re-baselines the repo around the existing
`fengkuang` slice and defines the next platformization steps.

## Docs Map

`docs/index.md` is the navigation entrypoint for the repo's agent-readable
documentation map. Start there for architecture, runtime, playbook, skill,
observability, operations, and shared-contract references. For the repo's
harness-engineering adaptation notes, see `docs/harness-engineering.md`.

## Stable Commands

```bash
uv run python -m ptsm.bootstrap --help
uv run pytest -q
ptsm run-fengkuang --scene "周一早高峰地铁通勤"
ptsm run-plan --plan docs/plans/2026-03-24-ptsm-agent-platform-rebaseline.md --dry-run
ptsm runs --account-id acct-fk-local --status completed --limit 5
```
