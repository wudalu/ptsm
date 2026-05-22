# PTSM Local Runbook

See also:

- `docs/operations/publish-quickstart.md`
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

If the upstream MCP browser session cannot generate a QR code, the command still returns JSON with `status: login_required`, `qrcode_error`, and `next_actions`. `xhs-login-qrcode` first tries the MCP `get_login_qrcode` tool and then the REST `/api/v1/login/qrcode` fallback when the MCP tool fails or omits image data. Treat HTTP 500 or timeout QR errors as an MCP/browser-session issue: restart `xiaohongshu-mcp` or its browser session, then rerun the QR command before scanning or publishing. If QR login still fails, use the upstream login helper to write cookies first:

```bash
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-login-darwin-amd64
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

The login helper opens a browser and may require QR scan plus second-factor confirmation. After it exits, verify with `uv run python -m ptsm.bootstrap xhs-login-status` before scanning or publishing.

### Step 2 — Dry-run (Content And Optional Image Preview)

Always dry-run first. This runs the full plan → execute → reflect pipeline without publishing. It does not generate images by default, but `--auto-generate-image` can preview the same image decision path before any real publish:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "你的场景描述" \
  --account-id acct-fk-local
```

This exercises:
- **Planner**: selects playbook (`fengkuang_daily_post`) and skills such as `xhs_trend_scan`, `topic_research`, `fengkuang_style`, `positive_reframe`, `xhs_hashtagging`, and `xhs_image_strategy`.
- **xhs_trend_scan**: loads the local XHS pattern library snapshot when available and injects reusable hook/body/image structures into `runtime_skill_contents`. Ordinary generation does not call live XHS by default; if no snapshot exists, it falls back to static SKILL.md guidance.
- **Memory**: reads recent same-account, same-playbook lessons and injects a compact anti-repetition context before drafting.
- **Executor**: DeepSeek LLM generates title, image_text, body, hashtags from scene + persona + planner + static skills + local pattern context + recent memory context.
- **Reflector**: enforces required rules such as `#发疯文学`, configured deterministic quality rules such as rejecting generic fengkuang titles, requiring a comment/copyable mechanic, and blocking mental-health/medical jokes. Light positive closings like `也算` are recommended style, not a mandatory phrase gate. Passes to finalize, or retries up to max_attempts.

Review `content_review`, `content_review.image_plan`, and the final正文. If content and image strategy look good, proceed to real publish.

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

1. **Image generation**: Auto-triggered when `publish_mode=mcp-real`, no `--publish-image-path` is provided, and `--no-auto-generate-image` is not set. Operator `--local-image-style` can actively choose `note_card`, `iphone_notes`, or `wechat_chat`; otherwise `final_content.image_plan` from `xhs_image_strategy` can choose `local_social_screenshot` or provider image. If neither the operator nor the LLM chooses a route, PTSM uses the configured image provider when available, then the local renderer. The image prompt incorporates scene, title, image_text, body summary, persona, and runtime trend context, but no hashtags or tag text are added to the image. Output lands in `outputs/generated_images/`.

2. **Watermark removal**: Real publish with any final image path always runs OpenCV Canny edge detection + TELEA inpainting to remove residual watermarks in image corners. Result written to `*-nowm.png` and recorded under `watermark_removal`. Dry-run image experiments only run this step when `WATERMARK_REMOVAL_ENABLED=true`.

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
| `--no-auto-generate-image` | Disable automatic image generation, including real publish auto-fill |
| `--publish-image-path <path>` | Use one or more existing local image files |
| `--local-image-style note_card|iphone_notes|wechat_chat` | Actively choose the deterministic local cover style |
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

### Local Renderer Styles

PTSM can also use the local Pillow renderer as an explicit local cover path and write 3:4 PNGs under `outputs/generated_images/`. The default style is `note_card`, which records `image_generation.style=xhs_note_card_v1`. The shared `xhs_image_strategy` skill may set `final_content.image_plan.backend=local_social_screenshot` to choose this path automatically. For dry-runs or private tests that need a more native social screenshot shape, pass one of these as an explicit local override, even when Jimeng or Bailian is configured:

```bash
--local-image-style iphone_notes
--local-image-style wechat_chat
```

These local styles render iPhone Notes-like and WeChat chat transcript-like covers from the generated title, `image_text`, body summary, scene, and runtime context. They do not call external image APIs, and artifacts record the effective style as `iphone_notes_v1` or `wechat_chat_v1`. The artifact also records `image_generation.image_plan` so the run can be audited as `llm_image_plan`, `manual_override`, or default provider/local behavior.

### Watermark Removal

```env
WATERMARK_REMOVAL_ENABLED=true
```

Real publish with final images always runs this post-processing step before publishing, regardless of `WATERMARK_REMOVAL_ENABLED`. The env flag controls whether dry-run image experiments also preview the same cleanup.

The remover uses OpenCV to detect text-like patterns in image corners (Canny edge detection → contour filling → mask dilation) and remove them via TELEA inpainting. Results are written to `*-nowm.png` and recorded in the artifact under `watermark_removal`.

## Hotspot Scanning (xhs_trend_scan)

The `xhs_trend_scan` skill runs during the planner phase. Ordinary generation is local-first:

1. Try to load `outputs/artifacts/xhs-pattern-library/current.json`.
2. If a matching lane exists, inject pattern ids, hook archetypes, body structures and image sequences as `runtime_skill_contents`.
3. If no snapshot exists, ordinary generation skips dynamic context and falls back to static `SKILL.md` guidance.
4. Live MCP `search_feeds` is reserved for explicit fresh research or the separate `collect-xhs-patterns` job.

This prevents normal content runs from depending on current XHS login state. The periodic collection command is:

```bash
uv run python -m ptsm.bootstrap collect-xhs-patterns \
  --lane human_enrichment \
  --keywords "人类丰容,家的丰容计划,低成本改造,钩织,拼豆" \
  --sample-limit-per-keyword 8

uv run python -m ptsm.bootstrap analyze-xhs-patterns \
  --sample-path outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json \
  --lane human_enrichment
```

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
  --auto-generate-image \
  --local-image-style iphone_notes

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

# AI tech news dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "Google发布Gemini 3模型" \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post

# Daily English dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "学一个表示坚持的高级词汇" \
  --account-id acct-daily-english-local \
  --playbook-id daily_english_post

# Modern psychology dry-run
uv run python -m ptsm.bootstrap guide-post \
  --scene "下班后还在反复复盘白天一句话"

uv run python -m ptsm.bootstrap run-playbook \
  --scene "下班后还在反复复盘白天一句话" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post

# World Cup dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点" \
  --account-id acct-world-cup-local \
  --playbook-id world_cup_daily_post

# Reddit英文讨论转译 dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度" \
  --account-id acct-reddit-curation-local \
  --playbook-id reddit_curation_daily_post
```

### Reddit Discussion Scan

Reddit英文讨论转译使用 Reddit app-only OAuth 做只读扫描，不需要 Reddit 用户名或密码。创建 Reddit app 后配置：

```env
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-client-secret
REDDIT_USER_AGENT=ptsm:reddit-curation:0.1 (by /u/your_reddit_username)
REDDIT_SUBREDDITS=OpenAI,ChatGPT,ClaudeAI,ArtificialInteligence,singularity,psychology,AskPsychology,productivity
REDDIT_SORTS=hot,top
REDDIT_TIME_FILTER=day
REDDIT_LIMIT_PER_LISTING=12
```

如果未配置 Reddit env，artifact 的 `runtime_skill_details` 仍会记录 `reddit_discussion_scan`，但 runtime context 会标记 `missing_credentials`。这时可以做离线结构验证，不应把正文当成“最新 Reddit 热帖”。

## Diagnostics

```bash
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap doctor --server-url http://localhost:19000/mcp
```

## Evaluation

每次 `run-playbook` / `run-fengkuang` 完成后可以自动评估产物质量。默认关闭，加 `--eval` 开启。

```bash
# Dry-run + eval
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周五下班" \
  --account-id acct-fk-local \
  --eval
```

Eval 会对 artifact 的 planner skill activation、executor final content、reflector decision、image generation、publish result、post-publish checks 和 artifact completeness 分别运行 5 个 rule evaluator（required fields、hashtags、publish mode、dry-run safety）和 2 个 contract evaluator（root fields、skill match）。结果写入 `.ptsm/evals/<eval_run_id>/summary.json` + `results.jsonl`。

### 手动对已有 artifact 跑 eval

```bash
uv run python -m ptsm.bootstrap eval-artifact --artifact outputs/artifacts/<artifact>.json
```

### 查看 eval 聚合

```bash
# 按 playbook 过滤
uv run python -m ptsm.bootstrap harness-evals --playbook-id fengkuang_daily_post

# harness-report 包含 eval 结果和阈值检查
uv run python -m ptsm.bootstrap harness-report --max-required-eval-failures 0
```

`harness-check` 会阻塞 `required_failed > 0` 的 eval 失败。默认 harness 不调用 LLM judge；当 `eval-artifact` 显式启用 LLM judge 或运行时配置了 XHS 内容质量 judge backend 时，XHS executor content-quality judge 使用 required gate，失败会触发重写或计入 `required_failed`。最终发布仍需人工确认 `content_review`。

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
  },
  {
    "account_id": "acct-wuxia-local",
    "nickname": "武侠人物深度评述",
    "platform": "xiaohongshu",
    "domain": "武侠人物评述",
    "publish_mode": "dry-run"
  },
  {
    "account_id": "acct-ai-tech-local",
    "nickname": "AI科技资讯实验号",
    "platform": "xiaohongshu",
    "domain": "AI科技资讯",
    "publish_mode": "dry-run"
  },
  {
    "account_id": "acct-daily-english-local",
    "nickname": "英语学习日记实验号",
    "platform": "xiaohongshu",
    "domain": "每日英语学习",
    "publish_mode": "dry-run"
  },
  {
    "account_id": "acct-psychology-local",
    "nickname": "心理观察手记实验号",
    "platform": "xiaohongshu",
    "domain": "现代心理困境观察",
    "publish_mode": "dry-run"
  },
  {
    "account_id": "acct-enrichment-local",
    "nickname": "日常丰容实验号",
    "platform": "xiaohongshu",
    "domain": "人类丰容实验",
    "publish_mode": "dry-run"
  },
  {
    "account_id": "acct-world-cup-local",
    "nickname": "世界杯看球手记实验号",
    "platform": "xiaohongshu",
    "domain": "世界杯主题",
    "publish_mode": "dry-run"
  }
]
```

### Domain-Account Mapping

| 领域 | 账号 | Cookie Profile | 说明 |
|------|------|---------------|------|
| 发疯文学 | `acct-fk-local` | `cookies/fk-local.json` | 打工人日常、情绪宣泄、自嘲治愈 |
| 苏轼诗词赏析 | `acct-sushi-local` | `cookies/sushi-local.json` | 诗词赏析、文化体验、生活感悟 |
| 武侠人物评述 | `acct-wuxia-local` | (未绑定 cookie) | 金庸古龙人物深度评述 |
| AI科技资讯 | `acct-ai-tech-local` | (未绑定 cookie) | AI/科技趋势速递与解读 |
| 每日英语学习 | `acct-daily-english-local` | (未绑定 cookie) | 每日单词学习、陪伴式教育 |
| 现代心理困境观察 | `acct-psychology-local` | (未绑定 cookie) | 场景化心理科普、情绪解释、安全边界 |
| 人类丰容实验 | `acct-enrichment-local` | (未绑定 cookie) | 家的丰容计划、低成本改造、日常变量实验 |
| 世界杯主题 | `acct-world-cup-local` | (未绑定 cookie) | 普通球迷看球笔记、赛前看点、看球清单 |

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

# 武侠人物评述领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "分析令狐冲的自由人格" \
  --account-id acct-wuxia-local \
  --playbook-id wuxia_character_post

# AI科技资讯领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "Google发布Gemini 3模型" \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post

# 每日英语学习领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "学一个表示坚持的高级词汇" \
  --account-id acct-daily-english-local \
  --playbook-id daily_english_post

# 现代心理困境观察领域
uv run python -m ptsm.bootstrap guide-post \
  --scene "看到别人周末都在聚会，自己突然觉得很失败"

uv run python -m ptsm.bootstrap run-playbook \
  --scene "下班后还在反复复盘白天一句话" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post

# 人类丰容实验领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "把书桌改成十分钟手作角" \
  --account-id acct-enrichment-local \
  --playbook-id human_enrichment_daily_post
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

`xhs-login-status` and `xhs-login-qrcode` should return bounded JSON even when QR generation fails. Look for `qrcode_error` and `next_actions`; do not continue with `topic-radar scan` or real publish until status becomes `ready`.

If the QR route returns MCP 500 or `TimeoutError`, run the upstream login helper with the same cookie target that the MCP server will later use:

```bash
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-login-darwin-amd64
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
uv run python -m ptsm.bootstrap xhs-login-status
```

Do not start MCP without `COOKIES_PATH` if the account is supposed to reuse an existing cookie file; otherwise `check_login_status` will report `login_required` even when a cookie file exists elsewhere.

## Current Limits

- `xhs-open-browser` opens a GUI browser — keep it conditional/manual, not in unattended automation.
- Successful real publishes persist `visibility` in `publish_result.platform_payload`, and `post_id`/`post_url` when upstream MCP exposes them.
- `xhs-check-publish` can auto-verify public posts via direct identifiers or exact-title `search_feeds` fallback. `--wait-for-publish-status` retries the public fallback briefly.
- `仅自己可见` posts still cannot be auto-verified if upstream didn't return `post_id`/`post_url`; they return `manual_check_required`.
- Real publish requires a reachable `xiaohongshu-mcp` server and valid login state.
- The `search_feeds` MCP tool uses keyword search — trending posts are derived from engagement, not official XHS trend rankings.
