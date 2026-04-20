# 2026-04-20 Docs Sync Gate

## Goal

Add a path-aware docs gate that blocks code changes when the most specific source-of-truth documentation surface was not updated in the same change.

## Design

- Reuse active source-of-truth docs front matter instead of inventing a second mapping file.
- Treat `related_paths` as the authoritative coverage map for source-of-truth docs.
- Resolve ambiguity by preferring the most specific matching `related_paths` entry for each changed code path.
- Allow a source-of-truth doc to be satisfied by either the doc itself or any doc page explicitly listed in its `related_paths`.
- Keep the first version narrow:
  - only enforce on `src/ptsm/**` and `shared_contracts/**`
  - ignore docs-only and test-only changes
  - report unmapped code changes as errors so coverage gaps stay visible

## Tasks

1. Add `run_docs_sync()` under `application/use_cases` and expose it through a new `ptsm docs-sync` CLI command.
   Verify: `uv run pytest tests/unit/application/use_cases/test_docs_sync.py tests/unit/test_bootstrap.py -q`

2. Update source-of-truth docs to describe the new gate and include related paths for the new use case.
   Verify: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`

3. Add repository automation for the gate.
   - Create `.github/workflows/docs-sync.yml`
   - Create a pull request template that reminds authors to update docs in the same PR
   Verify: manual inspection

## Acceptance

- `ptsm docs-sync --changed-path ...` returns `1` when the relevant source-of-truth docs were not touched.
- A related runbook page can satisfy a source-of-truth doc when that page is part of the doc's declared surface.
- Broad docs such as `architecture.md` do not suppress more specific doc requirements.
- GitHub Actions can run the same gate on pull requests with `--base-ref <base sha>`.
