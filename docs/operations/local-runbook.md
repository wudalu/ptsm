# PTSM Local Runbook

See also:

- `docs/operations/task-completion-automation.md`

## Startup

Check available commands:

```bash
uv run python -m ptsm.bootstrap --help
```

Run a local dry-run:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周四晚上加班后回家" \
  --account-id acct-fk-local
```

If you want dry-run to exercise model image generation too:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周六社畜躺平" \
  --account-id acct-fk-local \
  --auto-generate-image
```

For real publish runs, PTSM now defaults to auto-generating a cover image when `--publish-image-path` is omitted and Bailian image config is present.

Required `.env` fields for Bailian image generation:

```env
PIC_MODEL_API_KEY=sk-...
PIC_MODEL_MODEL=qwen-image-2.0-pro
PIC_MODEL_BASE_URL=https://dashscope.aliyuncs.com/api/v1
PIC_MODEL_SIZE=1104*1472
```

Generated images are persisted under `outputs/generated_images/`, and the artifact records `image_generation.provider/model/prompt/generated_image_paths`.

Ask the workflow to do a post-publish status check after the dry-run finishes:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --wait-for-publish-status
```

If you also want the workflow to open the browser when the status cannot be verified automatically:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --wait-for-publish-status \
  --open-browser-if-needed
```

## Diagnostics

Check local settings, artifact directory, and XiaoHongShu MCP preflight:

```bash
uv run python -m ptsm.bootstrap doctor
```

Override MCP server for a one-off diagnosis:

```bash
uv run python -m ptsm.bootstrap doctor --server-url http://localhost:19000/mcp
```

## Logs

Each run writes local metadata under:

```text
.ptsm/runs/<run_id>/
  summary.json
  events.jsonl
```

Inspect a run directly:

```bash
uv run python -m ptsm.bootstrap logs --run-id <run_id>
```

If an artifact contains `run.run_id`, inspect from the artifact:

```bash
uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json
```

## Login Troubleshooting

Check current login preflight:

```bash
uv run python -m ptsm.bootstrap xhs-login-status
```

Materialize the login QR code:

```bash
uv run python -m ptsm.bootstrap xhs-login-qrcode --output /tmp/xhs-login-qrcode.png
```

Open the QR code or creator page in the default browser:

```bash
uv run python -m ptsm.bootstrap xhs-open-browser --target login
uv run python -m ptsm.bootstrap xhs-open-browser --target creator
```

## Publish Verification

If the artifact contains `publish_result.post_id` or `publish_result.post_url`, ask PTSM to verify status:

```bash
uv run python -m ptsm.bootstrap xhs-check-publish \
  --artifact outputs/artifacts/<artifact>.json
```

If you want one read-only diagnosis that combines login readiness, artifact metadata, run logs, and publish verification:

```bash
uv run python -m ptsm.bootstrap diagnose-publish \
  --artifact outputs/artifacts/<artifact>.json
```

You can also start from the run id if you only have a run handle:

```bash
uv run python -m ptsm.bootstrap diagnose-publish \
  --run-id <run_id>
```

`diagnose-publish` will return:

- `likely_cause`
- `evidence`
- `next_actions`

Use it when `xhs-check-publish` alone is not enough to tell whether the root issue is login state, missing publish identifiers, unsupported MCP status checks, or a real publish error.

If you only need to open the resulting post or fall back to creator center:

```bash
uv run python -m ptsm.bootstrap xhs-open-browser \
  --target artifact \
  --artifact outputs/artifacts/<artifact>.json
```

## Current Limits

- `xhs-open-browser` was not exercised end-to-end in automation here because opening a GUI browser requires local approval.
- `xhs-check-publish` can only auto-verify when the artifact has a resolvable `post_id` or `post_url`, or when the MCP server exposes a supported status tool.
- Real publish still depends on a reachable `xiaohongshu-mcp` server and valid login state.
