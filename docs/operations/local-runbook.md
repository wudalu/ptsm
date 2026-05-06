# PTSM Local Runbook

See also:

- `docs/operations/task-completion-automation.md`

## Canonical Real Publish Workflow (Agent-Ready)

This is the end-to-end flow for publishing a post. Follow these steps in order.

### Step 0 — Start MCP Server

Real publish requires the external `xiaohongshu-mcp` server. Start it in a separate terminal:

```bash
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

It listens on `:18060` by default, matching `XHS_MCP_SERVER_URL=http://localhost:18060/mcp`.

### Step 1 — Pre-flight Check

```bash
uv run python -m ptsm.bootstrap doctor
```

This verifies: settings loaded, artifacts dir exists, XHS MCP reachable and logged in, harness docs fresh.

Confirm login status specifically:

```bash
uv run python -m ptsm.bootstrap xhs-login-status
```

If not logged in, materialize the QR code and scan it with the XHS app:

```bash
uv run python -m ptsm.bootstrap xhs-login-qrcode --output /tmp/xhs-login-qrcode.png
```

### Step 2 — Dry-run (Content Generation Only)

Always dry-run first. This runs the full plan → execute → reflect pipeline without publishing or generating images:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "你的场景描述" \
  --account-id acct-fk-local
```

This exercises:
- **Planner**: selects playbook (fengkuang_daily_post) and skills (xhs_trend_scan, fengkuang_style, positive_reframe, xhs_hashtagging)
- **xhs_trend_scan**: calls MCP `search_feeds` with keywords derived from the scene to find real-time hot posts on Xiaohongshu. The live trend context (top posts by engagement score, recommended angle, tension) is injected into both the content drafting prompt and the image generation prompt. If MCP is unreachable, it falls back to the static SKILL.md guidance.
- **Executor**: DeepSeek LLM generates title, image_text, body, hashtags from scene + persona + planner + static skills + live trend context
- **Reflector**: hard-checks that `#发疯文学` tag and `也算` phrase are present. Passes to finalize, or retries up to max_attempts.

Review the output. If content quality is good, proceed to real publish.

### Step 3 — Real Publish

After dry-run looks good, choose one of the two paths below based on your intent.

#### Path A: Private Test — 先验货

Publish as `仅自己可见` for safe content review. Open the XHS app to manually confirm the post looks right before going public.

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "你的场景描述" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "仅自己可见"
```

Note: `--wait-for-publish-status` is less useful here — private posts typically can't be auto-verified since the upstream MCP may not return `post_id`. Manual confirmation in the app is the expected verify step.

#### Path B: Public Publish — 公开发布

Publish as public for real engagement. Auto-verification via `search_feeds` exact-title match works for public posts.

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "你的场景描述" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "公开" \
  --wait-for-publish-status
```

With `--wait-for-publish-status`, PTSM retries `search_feeds` title match for ~8s to account for upstream indexing delay. If auto-verify still fails, add `--open-browser-if-needed` to fall back to the browser.

#### What happens in both paths

1. **Image generation**: Auto-triggered when `publish_mode=mcp-real` and no `--publish-image-path` is provided. Priority: Jimeng (`jimeng_t2i_v40`) → Bailian (`qwen-image-2.0-pro`). The image prompt incorporates scene, title, image_text, body summary, persona, and runtime trend context — but **no hashtags or tag text are added to the image** (the prompt explicitly forbids rendering `#发疯文学` or any topic tags on the image). Output lands in `outputs/generated_images/`.

2. **Watermark removal** (optional): If `WATERMARK_REMOVAL_ENABLED=true` in `.env`, OpenCV Canny edge detection + TELEA inpainting is applied to remove residual watermarks in image corners. Result written to `*-nowm.png`.

3. **Publish**: XHS MCP `publish_content` is called with title, body, images, tags, and visibility. The side-effect ledger (`.ptsm/agent_runtime/side-effects.json`) records successful publishes keyed by `thread_id` — re-running with the same thread_id will skip duplicate publish.

### Step 4 — Verify Publish

```bash
# Check publish status from artifact
uv run python -m ptsm.bootstrap xhs-check-publish \
  --artifact outputs/artifacts/<artifact>.json

# Full diagnosis if status is unclear
uv run python -m ptsm.bootstrap diagnose-publish \
  --artifact outputs/artifacts/<artifact>.json

# Or from run_id
uv run python -m ptsm.bootstrap diagnose-publish \
  --run-id <run_id>

# Open the post or creator center in browser
uv run python -m ptsm.bootstrap xhs-open-browser \
  --target artifact \
  --artifact outputs/artifacts/<artifact>.json
```

### Quick Reference: All Publish Flags

| Flag | Purpose |
|------|---------|
| `--publish-mode mcp-real` | Real publish via XHS MCP (omit for dry-run) |
| `--auto-generate-image` | Force image generation even in dry-run |
| `--publish-visibility "仅自己可见"` | Private post — safe for review before going public |
| `--publish-visibility "公开"` | Public post — visible to all, supports auto-verification |
| `--wait-for-publish-status` | Block until publish status is auto-verified or times out |
| `--open-browser-if-needed` | Open browser when status can't be auto-verified |

## Image Generation

### Preferred Backend: Volcengine Jimeng

```env
JIMENG_API_KEY=your-volcengine-ak
JIMENG_SECRET_KEY=your-volcengine-sk
JIMENG_MODEL=jimeng_t2i_v40
JIMENG_BASE_URL=https://visual.volcengineapi.com
JIMENG_WIDTH=1536
JIMENG_HEIGHT=2048
```

### Fallback: Bailian

```env
PIC_MODEL_API_KEY=sk-...
PIC_MODEL_MODEL=qwen-image-2.0-pro
PIC_MODEL_BASE_URL=https://dashscope.aliyuncs.com/api/v1
PIC_MODEL_SIZE=1104*1472
```

When both are configured, Jimeng is used first.

### Watermark Removal (Optional)

```env
WATERMARK_REMOVAL_ENABLED=true
```

Uses OpenCV to detect text-like patterns in image corners (Canny edge detection → contour filling → mask dilation) and remove them via TELEA inpainting. Results are written to `*-nowm.png` and recorded in the artifact under `watermark_removal`.

## Hotspot Scanning (xhs_trend_scan)

The `xhs_trend_scan` skill runs during the planner phase. It:

1. Derives search keywords from the scene (e.g., weekday cues, work cues, playbook domain)
2. Calls MCP `search_feeds` with each keyword
3. Ranks results by engagement score (`likes + comments×4 + shares×6 + collects×2`)
4. Injects the top 4 unique hits as `runtime_skill_contents` into both content drafting and image generation

If MCP is unreachable or not logged in, it silently falls back to static trend judgment from `SKILL.md`.

**Keyword derivation for 发疯文学:**
- Detects weekday tokens (周一~周日) → adds day-specific search terms
- Domain `发疯文学` always adds `"发疯文学 打工人"`
- Overtime cues (下班, 需求, 加班, etc.) add `"隐形加班"` and `"下班前 新需求"`

## Dry-run & Testing

```bash
# Standard dry-run (no publish, no image)
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周四晚上加班后回家" \
  --account-id acct-fk-local

# Dry-run with image generation
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周六社畜躺平" \
  --account-id acct-fk-local \
  --auto-generate-image

# Generic playbook dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "夜里读到《定风波》" \
  --account-id acct-sushi-local \
  --playbook-id sushi_poetry_daily_post

# Wuxia character commentary dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "分析令狐冲的自由人格与当代职场人不愿被体制化" \
  --account-id acct-wuxia-local \
  --playbook-id wuxia_character_post
```

## Diagnostics

```bash
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap doctor --server-url http://localhost:19000/mcp
```

## Logs

```bash
uv run python -m ptsm.bootstrap logs --run-id <run_id>
uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json
```

Each run writes metadata under `.ptsm/runs/<run_id>/` (summary.json, events.jsonl).

## Multi-Account Operations

PTSM 支持多个小红书账号，每个账号绑定独立的 cookie 文件和内容领域，互不串号。

### Account Inventory

```bash
ptsm accounts
```

输出：
```json
[
  {
    "account_id": "acct-fk-local",
    "nickname": "发疯文学实验号",
    "platform": "xiaohongshu",
    "domain": "发疯文学",
    "publish_mode": "dry-run",
    "cookie_profile_id": "fk-local-cookie",
    "cookie_path": "cookies/fk-local.json"
  },
  {
    "account_id": "acct-sushi-local",
    "nickname": "苏轼诗词赏析实验号",
    "platform": "xiaohongshu",
    "domain": "苏轼诗词赏析",
    "publish_mode": "dry-run",
    "cookie_profile_id": "sushi-local-cookie",
    "cookie_path": "cookies/sushi-local.json"
  }
]
```

### Domain-Account Mapping

| 领域 | 账号 | Cookie Profile | 说明 |
|------|------|---------------|------|
| 发疯文学 | `acct-fk-local` | `cookies/fk-local.json` | 打工人日常、情绪宣泄、自嘲治愈 |
| 苏轼诗词赏析 | `acct-sushi-local` | `cookies/sushi-local.json` | 诗词赏析、文化体验、生活感悟 |
| 武侠人物评述 | `acct-wuxia-local` | (未绑定 cookie) | dry-run 仅做内容生成测试 |

账号定义在 `src/ptsm/accounts/definitions/*.yaml`。新增账号只需加一个 YAML 文件。

### Per-Account Login

每个账号需要独立扫码登录，cookie 保存到账号绑定的 `cookie_path`。

**Step 1 — 启动 MCP Server（账号级 cookie）**

账号级 cookie 通过 `COOKIES_PATH` 环境变量传入 xiaohongshu-mcp：

```bash
# 登录发疯文学账号
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64

# 登录苏轼诗词账号（另一个终端，另一个端口）
COOKIES_PATH=cookies/sushi-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64 -port :18061
```

如果只有一个 MCP server 实例但要切换账号，重新启动并更换 `COOKIES_PATH` 即可。

**Step 2 — 扫码登录**

```bash
# 生成 QR code
uv run python -m ptsm.bootstrap xhs-login-qrcode --output /tmp/xhs-qr-fk.png
```

扫码后 cookie 自动存入 `cookies/fk-local.json`。确认登录状态：

```bash
uv run python -m ptsm.bootstrap xhs-login-status
# → ✅ 已登录
# → 用户名: xiaohongshu-mcp
```

**Step 3 — 验证账号级登录**

```bash
ptsm accounts
# 确认 cookie_profile_id 和 cookie_path 已绑定
```

### Running With Specific Account

```bash
# 发疯文学领域
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周四加班到崩溃" \
  --account-id acct-fk-local

# 苏轼诗词领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "夜里读到《定风波》" \
  --account-id acct-sushi-local \
  --playbook-id sushi_poetry_daily_post
```

账号的 `domain` 决定了自动选哪个 playbook。`publish_mode: dry-run` 默认只生成不发布。改为 `mcp-real` 后走真实发布链路。

### Cookie File Location

扫码登录后，cookie 按 `COOKIES_PATH` 环境变量指定的路径保存：

| 账号 | Cookie 路径 |
|------|-------------|
| `acct-fk-local` | `cookies/fk-local.json` |
| `acct-sushi-local` | `cookies/sushi-local.json` |

Cookie 文件由 xiaohongshu-mcp 管理，PTSM 通过账号定义引用，不直接读写。升级或重建 session 时只需在启动 MCP server 时指定新的 cookie 路径，重新扫码即可。

```bash
# 重建 cookie（例如 session 过期）
rm cookies/fk-local.json
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
# 然后重新扫码
```

### Safety: Cookie-Scoped Isolation

- **Side-effect ledger** 按 `thread_id + cookie_profile_id` 去重，不同账号的同名 thread 不会串号。
- **Artifact** 中包含 `cookie_profile_id` 摘要，排障时能看出哪次发布用的哪个账号。
- **Dry-run** 不需要 cookie；`cookie_profile_id` 为空时用全局 settings fallback。

## Login Troubleshooting

```bash
uv run python -m ptsm.bootstrap xhs-login-status
uv run python -m ptsm.bootstrap xhs-login-qrcode --output /tmp/xhs-login-qrcode.png
uv run python -m ptsm.bootstrap xhs-open-browser --target login
uv run python -m ptsm.bootstrap xhs-open-browser --target creator
```

## Current Limits

- `xhs-open-browser` opens a GUI browser — keep it conditional/manual, not in unattended automation.
- Successful real publishes persist `visibility` in `publish_result.platform_payload`, and `post_id`/`post_url` when upstream MCP exposes them.
- `xhs-check-publish` can auto-verify public posts via direct identifiers or exact-title `search_feeds` fallback. `--wait-for-publish-status` retries the public fallback briefly.
- `仅自己可见` posts still cannot be auto-verified if upstream didn't return `post_id`/`post_url`; they return `manual_check_required`.
- Real publish requires a reachable `xiaohongshu-mcp` server and valid login state.
- The `search_feeds` MCP tool uses keyword search — trending posts are derived from engagement, not official XHS trend rankings.
