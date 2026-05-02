# PTSM Local Runbook

See also:

- `docs/operations/task-completion-automation.md`

## Startup

Check available commands:

```bash
uv run python -m ptsm.bootstrap --help
```

If you plan to use XiaoHongShu real publish, start the external `xiaohongshu-mcp` server in a separate terminal first:

```bash
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

This listens on `:18060` by default, which matches `XHS_MCP_SERVER_URL=http://localhost:18060/mcp`.
PTSM does not auto-start this external service for you. If it is not running, `doctor`, `xhs-login-status`, and `run-fengkuang --publish-mode mcp-real` will fail with a connection error.

Run a local dry-run:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周四晚上加班后回家" \
  --account-id acct-fk-local
```

Run a local dry-run for the generic playbook entrypoint:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析" \
  --account-id acct-sushi-local \
  --playbook-id sushi_poetry_daily_post
```

If you want dry-run to exercise model image generation too:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周六社畜躺平" \
  --account-id acct-fk-local \
  --auto-generate-image
```

For real publish runs, PTSM now defaults to auto-generating a cover image when `--publish-image-path` is omitted and an image backend is configured.

Preferred `.env` fields for Volcengine Jimeng image generation:

```env
JIMENG_API_KEY=your-volcengine-ak
JIMENG_SECRET_KEY=your-volcengine-sk
JIMENG_MODEL=jimeng_t2i_v40
JIMENG_BASE_URL=https://visual.volcengineapi.com
JIMENG_WIDTH=1536
JIMENG_HEIGHT=2048
```

Fallback `.env` fields for Bailian image generation:

```env
PIC_MODEL_API_KEY=sk-...
PIC_MODEL_MODEL=qwen-image-2.0-pro
PIC_MODEL_BASE_URL=https://dashscope.aliyuncs.com/api/v1
PIC_MODEL_SIZE=1104*1472
```

When both are present, PTSM uses Jimeng first.
Generated images are persisted under `outputs/generated_images/`, and the artifact records `image_generation.provider/model/prompt/generated_image_paths`.

Ask the workflow to do a post-publish status check after the dry-run finishes:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --wait-for-publish-status
```

Force a real publish to stay private:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --publish-visibility "仅自己可见"
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

If `xhs-login-status` or real publish fails with a connection error, first confirm the local MCP server process above is still running.

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

When upstream publish responses omit identifiers, `xhs-check-publish` will also try a narrow MCP search fallback for posts that were not published as `仅自己可见`. The fallback only succeeds on exact title matches; it does not try to guess fuzzy matches. During `run-fengkuang --wait-for-publish-status`, PTSM gives that public fallback a short retry window so newly published posts can become searchable before the initial run finishes.

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

Use it when `xhs-check-publish` alone is not enough to tell whether the root issue is login state, missing publish identifiers, private-post verification limits, unsupported MCP status checks, or a real publish error.

If you only need to open the resulting post or fall back to creator center:

```bash
uv run python -m ptsm.bootstrap xhs-open-browser \
  --target artifact \
  --artifact outputs/artifacts/<artifact>.json
```

## Current Limits

- `xhs-open-browser` was not exercised end-to-end in automation here because opening a GUI browser requires local approval.
- successful real publishes now persist the requested `visibility` in `publish_result.platform_payload`, and will also persist `post_id` / `post_url` when the upstream MCP response exposes them.
- `xhs-check-publish` can auto-verify public posts either from direct identifiers or, when identifiers are missing, from an exact-title `search_feeds` fallback. `run-fengkuang --wait-for-publish-status` will retry that public fallback briefly, but a longer upstream indexing delay can still leave the first run at `manual_check_required`.
- `仅自己可见` posts still cannot be auto-verified if upstream did not return `post_id` / `post_url`; current tooling can only fall back to manual confirmation in that case.
- Real publish still depends on a reachable `xiaohongshu-mcp` server and valid login state.
