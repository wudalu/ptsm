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
- **Memory**: reads recent same-account, same-playbook lessons and injects a compact anti-repetition context before drafting. Ordinary psychology also maintains a private, cover-excluded inner-page fingerprint window of the recent 12 successful complete carousel receipts; it never reuses learning-series history.
- **Executor**: DeepSeek LLM generates title, image_text, body, hashtags from scene + persona + planner + static skills + local pattern context + recent memory context. XHS prompts use `xhs_compact_native_v1`: a concrete human/scene entry, 2–4 short beats, one domain-usable detail, and a natural combined save/reply opening inside the playbook’s compact length band—not four fixed正文 moves.
- **Reflector**: enforces required rules such as `#发疯文学`, configured deterministic quality rules such as rejecting generic titles, requiring a comment/copyable mechanic, keeping正文 inside the playbook length band, and blocking mental-health/medical jokes. Light positive closings like `也算` are recommended style, not a mandatory phrase gate. Passes to finalize, or retries up to max_attempts.

Review `content_review`, `content_review.image_plan`, and the final正文. If content and image strategy look good, proceed to real publish. When the planned style is `wechat_chat`, check that the visible text is a short content-only transcript rather than a full phone screenshot. For `modern_psychology_post`, a default `text_carousel` plan must contain **one topic, one 4–7-page set** of ordered semantic slides; the first cover remains low-density and inner pages contain bounded short lines. A request for more than 7 pages/images (including 12) needs the explicit three-way router before any run: `one_carousel` is the supported one-topic 4–7-page set; `multiple_posts` is supported only after separately confirming every post and running each independently; `independent_assets` is unsupported because 8–12 **independent image assets** are outside this psychology wrapper/PTSM path and must go to a separately authorized asset workflow. Never silently turn any choice into a batch/loop/repeat. `max_text_units` is per-page text density, not image count.

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

1. **Image generation**: Auto-triggered when `publish_mode=mcp-real`, no `--publish-image-path` is provided, and `--no-auto-generate-image` is not set. Ordinary single-image routes keep the existing operator/provider/local selection. A validated `modern_psychology_post` text carousel is different: it always uses local `psychology_text_card_v1`, renders every ordered slide under a runtime-owned staging directory, verifies all PNG/page hashes, writes `manifest.json`, and atomically promotes only the complete set under `outputs/generated_images/`. Only a current-memory-bound runtime reservation is accepted; the application persists its receipt intent before ledger append and commits the recent-12 inner-page identity only after canonical receipt and complete page-aware ledger projection succeed. Pre-ledger failures abort; possibly durable post-append failures retain the intent for application-only expiry reconciliation. An explicit ordinary-post `--local-image-style note_card|iphone_notes|wechat_chat` intentionally bypasses the carousel and keeps the legacy single-cover path; learning-series overrides remain forbidden.

2. **Watermark removal**: PTSM local-renderer output has no provider watermark and records a group-level skip; this includes every page in a psychology carousel. Provider/LLM output and manual image paths still run OpenCV Canny edge detection + TELEA inpainting before real publish. Dry-run provider/manual experiments only run this step when `WATERMARK_REMOVAL_ENABLED=true`.

3. **Publish**: XHS MCP `publish_content` is called with title, body, images, tags, and visibility. The side-effect ledger (`.ptsm/agent_runtime/side-effects.json`) records successful publishes keyed by `thread_id` — re-running with the same thread_id will skip duplicate publish.

Keep `.ptsm/agent_runtime/` on durable local storage alongside `outputs/` while writers may run. Its execution-memory store holds ordinary-carousel reservations and the recent-12 successful receipt identities; do not delete, reinitialize, or copy it between concurrent writers as a retry shortcut. Normal image/ledger failure releases a reservation; stale leases are recovered by the store rather than by deleting memory files.

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
| `--local-image-style note_card|iphone_notes|wechat_chat` | Actively choose the deterministic legacy single-cover style; ordinary psychology only, never learning-series |
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

Generated images request no provider watermark at source. Jimeng submits `logo_info.add_logo=false`; Bailian submits `watermark=false` and keeps no-watermark/logo terms in the negative prompt even when `PIC_MODEL_NEGATIVE_PROMPT` is overridden. The local renderer also avoids PTSM branding/footer text on the final image. Check `image_generation.watermark_policy.requested=no_provider_watermark` in the artifact to confirm the generated image path used this policy.

### Local Renderer Styles

PTSM can also use the local Pillow renderer as an explicit local cover path and write 3:4 PNGs under `outputs/generated_images/`. The default style is `note_card`, which records `image_generation.style=xhs_note_card_v1`. The shared `xhs_image_strategy` skill may set `final_content.image_plan.backend=local_social_screenshot` to choose this path automatically. For dry-runs or private tests that need a more native social screenshot shape, pass one of these as an explicit local override, even when Jimeng or Bailian is configured:

```bash
--local-image-style iphone_notes
--local-image-style wechat_chat
```

These local styles render iPhone Notes-like and WeChat chat transcript-like covers from the generated title, `image_text`, body summary, scene, and runtime context. They do not call external image APIs, and artifacts record the effective style as `iphone_notes_v1` or `wechat_chat_v1`. The artifact also records `image_generation.image_plan` so the run can be audited as `llm_image_plan`, `manual_override`, or default provider/local behavior.

`wechat_chat` now renders a content-only chat transcript: 无头部、无底部、无头像, with speaker labels beside the bubbles. It is meant for scenes where the first-screen asset is the actual chat exchange, copyable reply, or comment prompt. The renderer reads explicit structured messages from `chat_messages` / `messages`, or speaker-prefixed body lines such as `同事：刚看见热搜` and `我：我现在啥事都发文字确认`; this prevents a chat cover from collapsing into one generic bubble. `theme=dark` switches the transcript to a dark background, `chat_times` inserts up to three timestamp labels, and `chat_title` / `conversation_title` can label incoming messages when the body uses generic speakers. `status_time`, `unread_count`, and `show_avatars` are preserved in the payload for audit compatibility, but the current content-only renderer does not draw phone chrome or avatar blocks.

`psychology_text_card_v1` is not a `--local-image-style` choice. It is the local-only automatic
carousel renderer selected by a validated psychology `image_plan`. It creates one topic / one 4–7-page
set, not a generic batch; an oversized request must first select `one_carousel`, separately confirmed
`multiple_posts`, or unsupported `independent_assets` rather than silently use a batch. The parent plan keeps
`backend/style/role/text_density/max_text_units/cover_text_strategy/reason/prompt_focus` and adds
`carousel_style` plus `slides`; each slide has exactly `slide_id`, one-based contiguous `order`,
`role`, `headline`, and `body_lines`. A set contains 4–7 pages, starts with `cover_hook`, and uses
semantic inner roles such as scene, light mechanism, save tool, boundary and comment prompt. It
does not split the final body or invoke another model. `max_text_units` limits text on each page.

Successful output is an immutable directory named from the output stem and content-addressed set id.
Treat its `manifest.json` as authoritative: `pages.order` must match `generated_image_paths`, all files
must be regular/readable PNGs, and each page's `page_sha256` (canonical content) / `file_sha256` (PNG bytes)
must match before publish. Only an ordinary set with a verified receipt and ledger can expose
`carousel_delivery.status=ready`, whose ordered `attachments` are the only safe handoff to an outer chat/IM
relay. PTSM does not own external delivery, so ready is not delivered, published, or acknowledged. The relay
keeps its own (not PTSM) `relay_attempt_id`, acknowledgement/outcome/retry record keyed by the receipt; it may
call an image set delivered only after all ordered attachments are acknowledged. If generation, manifest verification
or asset-ledger projection fails, the run status is `psychology_carousel_generation_failed`; PTSM **emitted no ready
handoff** and **invoked no external chat/IM sender**, and it does not advance the recent-12 committed memory window.
It cannot assert that a relay or recipient received no page: **relay ACK/outcome is authoritative** for whether any
page was received or delivered. If only the later external publish fails, keep the committed set for retry.

### Watermark Removal

```env
WATERMARK_REMOVAL_ENABLED=true
```

Real publish runs this post-processing step for provider/LLM and manual images regardless of
`WATERMARK_REMOVAL_ENABLED`. PTSM local-renderer output, including every page of
`psychology_text_card_v1`, records `skipped_for_local_renderer` and is passed through unchanged. The
env flag controls whether dry-run provider/manual image experiments also preview cleanup.

The remover uses OpenCV to detect text-like patterns in image corners (Canny edge detection → contour filling → mask dilation) and remove them via TELEA inpainting. Results are written to `*-nowm.png` and recorded in the artifact under `watermark_removal`.

## Hotspot Scanning (xhs_trend_scan)

The `xhs_trend_scan` skill runs during the planner phase. Ordinary generation is local-first:

1. Try to load `outputs/artifacts/xhs-pattern-library/current.json`.
2. If a matching lane exists, inject pattern ids, hook archetypes, body structures and image sequences as `runtime_skill_contents`.
3. If no snapshot exists, ordinary generation skips dynamic context and falls back to static `SKILL.md` guidance.
4. This skill does not itself fall back to live MCP. Except for AI evidence mode, explicit `--fresh-topic-research` uses the public Topic Radar eight-platform scan once before workflow selection; direct XHS collection remains the separate `collect-xhs-patterns` job. AI 科技必须先单独运行 `hotspot-discovery`，再提供 facts/test record evidence file；其 `--fresh-topic-research` 调用只返回分流提示。

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
  --scene "读到李白长风破浪会有时，想写给低谷里的自己" \
  --account-id acct-classic-poetry-local \
  --playbook-id classic_poetry_quote_post

# Wuxia character commentary dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "分析令狐冲的自由人格与当代职场人不愿被体制化" \
  --account-id acct-wuxia-local \
  --playbook-id wuxia_character_post

# AI tech evidence-gated dry-run (the file must be a valid hands_on bundle)
uv run python -m ptsm.bootstrap run-playbook \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post \
  --ai-content-mode hands_on \
  --ai-evidence-file /path/to/ai-evidence.json \
  --publish-mode dry-run

# Daily English dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "学一个表示坚持的高级词汇" \
  --account-id acct-daily-english-local \
  --playbook-id daily_english_post

# Modern psychology dry-run
uv run python -m ptsm.bootstrap guide-post \
  --scene "下班后还在反复复盘白天一句话"

uv run python -m ptsm.bootstrap guide-post \
  --scene "对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --scene "约好的局临时不想去了，怕扫兴又很累，想写社交电量边界" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --scene "领导18:57发来一句在吗，下班后身体被消息拉回工位" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap run-playbook \
  --scene "下班后还在反复复盘白天一句话" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --auto-generate-image

# Cross-domain topic guidance dry-runs
# JSON directions include `selection_policy`, `open_direction_ids`, the compatible
# `open_direction_id`, `direction_type`, `direction_type_counts`, `scene_fit`,
# each direction's `format_recommendation`, and
# `topic_guidance.image_recommendation` for the post-choice image route.
# The public shape is 4 dynamically reranked PTSM-returned directions; when
# changing the scene, rerun `guide-post` instead of reusing the previous direction
# set. Use the returned `image_recommendation.command_hint` after the direction is
# confirmed instead of inventing provider/model/local-style choices. Pass the
# chosen id with `run-playbook --topic-direction-id`; runtime resolves the public
# direction payload and injects it into drafting as topic direction guidance.
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id fengkuang_daily_post \
  --account-id acct-fk-local \
  --scene "领导18:57发来一句在吗，工牌想替我发疯" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id human_enrichment_daily_post \
  --account-id acct-enrichment-local \
  --scene "想把书桌角落改成十分钟适我主义手作位" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id classic_poetry_quote_post \
  --account-id acct-classic-poetry-local \
  --scene "下班路上想用王维空山新雨后写一点松弛感" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id wuxia_character_post \
  --account-id acct-wuxia-local \
  --scene "想用令狐冲写一种当代职场里的自由人格" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id ai_tech_daily_post \
  --account-id acct-ai-tech-local \
  --ai-content-mode news_brief \
  --ai-evidence-file /path/to/ai-evidence.json \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id ai_tech_daily_post \
  --account-id acct-ai-tech-local \
  --ai-content-mode hands_on \
  --ai-evidence-file /path/to/ai-evidence.json \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id daily_english_post \
  --account-id acct-daily-english-local \
  --scene "学一个表示坚持的高级词汇，想配真实职场例句" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id world_cup_daily_post \
  --account-id acct-world-cup-local \
  --scene "阿根廷和法国决赛前，想写普通球迷看球清单" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id reddit_curation_daily_post \
  --account-id acct-reddit-curation-local \
  --scene "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度" \
  --non-interactive \
  --format json

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

The ordinary psychology guide now returns `format_archetype=text_carousel`,
`local_style=psychology_text_card_v1`, `page_count.min=4`, `page_count.max=7`, ordered semantic
roles, and `command_hint=--auto-generate-image`. There is no page-copy or carousel-style CLI flag.
There is also no batch/count flag: more than 7 pages/images must use `one_carousel`, separately confirmed
`multiple_posts`, or unsupported `independent_assets` for independent image assets; `max_text_units` remains a
per-page density bound.
Use an explicit `--local-image-style note_card|iphone_notes|wechat_chat` only when the ordinary post
really needs one legacy cover instead of the default carousel.

### AI Tech Evidence Files

AI 科技是唯一不能用 `--scene` 直接生成的 playbook。先选 mode，再在本地写 JSON
evidence file；`run-playbook` 必须同时收到两者。`guide-post` 也要求
`--ai-content-mode`，它只展示该 mode 的 directions；把返回的 matching
`topic_direction_id` 原样带回 run 命令。完整三种 JSON 例子见
[`docs/operations.md`](../operations.md#ai-tech-evidence-gated-runs)。

```bash
# 先得到与 evidence mode 对应的方向（不会读热点或启动 workflow）
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id ai_tech_daily_post \
  --account-id acct-ai-tech-local \
  --ai-content-mode hands_on \
  --ai-evidence-file /path/to/ai-evidence.json \
  --non-interactive --format json

# 使用上一步返回的 matching id；可不传 scene
uv run python -m ptsm.bootstrap run-playbook \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post \
  --topic-direction-id ai_prompt_context_card \
  --ai-content-mode hands_on \
  --ai-evidence-file /path/to/ai-evidence.json \
  --publish-mode dry-run
```

最小 shape 的规则如下：

- `news_brief`：`news_items` 恰为 3–5 个不同事件；每项有 `label`、
  `event_fingerprint`、至少一条 `facts` 和至少一个 opaque `source_refs`。
- `hands_on`：一个 `topic` 加一个 `hands_on` record；record 必有 `product`、
  `version`、`tested_at`、`task`、`input_summary`、`observed_output`、`limitation` 和
  `test_evidence_refs`。
- `fact_translation`：一个 `topic`、至少两项 `{statement, source_refs}` 和
  `audience.who_should_care` / `audience.who_can_wait`。

所有 refs 都是 opaque ID（例如 `source:release-001`），不能写 URL、域名、作者、原始
标题、feed ID 或 token。`trend_support` 可有 `cluster_id` 或 `evidence_ids`，但只是
选题依据，不能代替 facts 或 test record。`news_brief` / `fact_translation` 不得写第一人称
实测；只有 `hands_on` 可说明已测试/已观察，而且只能复述 record 中的内容与局限。

若需要不限定方向的热点，先运行 `hotspot-discovery` 并人工核验。不要给 AI run 加
`--fresh-topic-research`：它会返回 `ai_tech_fresh_research_separate`，提醒你把 discovery
与 evidence collection 分开。

### Psychology Learning Series

心理学学习系列不使用自由 `--scene`。builtin `after_work_rumination` 保持现有 catalog flow；用户
自定义专题则必须先经过 PTSM plan → review → exact confirmation，不能把热点、operator idea、URL 或
研究笔记直接传入课程 run。普通心理学场景帖仍走上面的通用 psychology guide flow。受控系列的标题、
正文、封面和图片计划都不能手改或加 `--local-image-style` / `--publish-image-path`。历史 confirmed
controlled-template-v1 保持原单卡；builtin 与新确认 custom revision 使用 template v2 的 7 张 catalog-owned
`psychology_text_card_v1` pages。guide 只返回 `page_count` / `ordered_roles` 结构；wrapper/operator
不得声称拿到了 `slides` 或 page copy，也不能自行补写页面。

#### Choose a publication mode first

把用户请求先路由为 **单篇心理学帖**、**内置学习系列** 或 **自定义学习系列**。单篇帖使用上面的普通
psychology `guide-post --scene`；内置系列从 `after_work_rumination` roadmap 开始并等待显式选课；自定义系列
由用户提供主题和可选 2–6 项目录，随后依次走下面的 provision、proposal/review、exact confirmation、roadmap
和选课命令。意图不清时先问用户选哪一种，不默认创建 catalog、生成或发布。“继续下一课”或“看系列进度”必须先
重新查询 roadmap；`recommended_next_lesson` 只是建议。“改目录”必须创建新 proposal 和 immutable version，
不能改写已确认 catalog 或 progress。

#### Provision custom storage

首次创建 custom series 前，先初始化固定的私有存储树。这个动作只能在**所有 writer 都已停止**、可信
operator 独占 storage parent 时执行；不要把它作为正在失败的 plan、confirm 或 run 的重试手段。

```bash
uv run python -m ptsm.bootstrap provision-psychology-learning-storage --format json
```

命令只在返回的 catalog root 下建立固定的 `proposals`、`confirmations`、`catalogs` 和 `progress`
目录。之后 `plan-psychology-series`、`confirm-psychology-series`、guide 与 run 都不会隐式 provision：
目录缺失、被替换或不再是 private storage 时会 fail closed，先停止操作并由可信 operator 检查。

#### Custom topic / outline

可选 outline 文件是 2–6 项 JSON list，每项只允许安全的 `id`、`title` 和可选 `goal`。例如：

```json
[
  {"id": "notice_patterns", "title": "先看见下班后的脑内续播"},
  {"id": "practice_pause", "title": "给下班后的自己一个停顿", "goal": "练习一个短暂停顿动作"}
]
```

```bash
# proposal 仅供审核，JSON 返回 `series.lessons` plus top-level `publication_plan`，绝不直接生成或运行 lesson。
uv run python -m ptsm.bootstrap plan-psychology-series \
  --topic "下班后如何把工作从脑子里放下" \
  --curriculum-outline-file outline.json \
  --format json

# 审核 returned publication plan 和 exact proposal_fingerprint 后才确认。
uv run python -m ptsm.bootstrap confirm-psychology-series \
  --proposal-id "<returned proposal_id>" \
  --proposal-fingerprint "<returned proposal_fingerprint>" \
  --confirm --format json
```

确认创建 immutable `user_confirmed` revision；变更主题、outline 或顺序时重新 proposal/confirm，不能手写
catalog 或指定 catalog-root。proposal JSON 是 `series.lessons` plus top-level `publication_plan`，不是 roadmap。
先不带 lesson 查询 custom roadmap，读取 `selection_required`、`series.roadmap`、
`series.publication_plan`、`series.recommended_next_lesson` 和 `series.production_progress`；其 `kind` is `operator_content_production`。recommendation 是建议，不会自动选课或生成。用户明确选择 lesson（也可非推荐）
时，第二次 `guide-post` 必须带 returned explicit frozen `--psychology-curriculum-version`，只使用该响应返回的
matching direction id 进行 dry-run。progress 不是读者学习进度，也不代表自动发布；仅 safe completed
artifact/receipt 后才更新；若请求图片，还必须先有完整 committed carousel。不请求图片时仍沿用既有
safe content-artifact 时机。缺失或篡改 catalog/receipt 会 fail closed，可用 `eval-artifact --artifact <path>`
复核。builtin roadmap 不含这些 custom `series.publication_plan`、`series.recommended_next_lesson` 或
`series.production_progress` 字段。

```bash
# 先不带 lesson 查询 custom `series.roadmap`、`series.publication_plan`、`series.recommended_next_lesson` 与 `series.production_progress`。
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --non-interactive --format json

# 用户明确选择一课（可不是推荐课）后，再 pin 返回的 frozen version。
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --psychology-lesson-id "<chosen lesson_id>" \
  --psychology-curriculum-version "<returned curriculum_version>" \
  --non-interactive --format json
```

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --psychology-lesson-id "<chosen lesson_id>" \
  --psychology-curriculum-version "<returned curriculum_version>" \
  --topic-direction-id "<matching returned direction id>" \
  --publish-mode dry-run --eval --auto-generate-image
```

Current v2 learning carousel still records the page-aware operational asset ledger. Learning
response/artifact deliberately keeps only safe carousel evidence:
`status`, `renderer`, `carousel_style`, `image_count`, and `manifest_sha256` on success; it never
stores ledger details, local paths or page text. A trusted local operator can inspect the committed set under
`outputs/generated_images/`, follow its `manifest.json` order, and cross-check the local generated-image asset ledger. `psychology_carousel_generation_failed`
means no page was published and no production progress was advanced.

#### Custom storage failures and production progress

proposal、confirmation 和 catalog 都以 immutable 新文件名写入。若中断或同 UID race 在名字可见后才失败，
runtime 不会再按可变路径删除或覆盖该残留；当前 run 必须视为失败，由可信 operator 在所有 writer 停止后做
trusted offline maintenance（review、cleanup 或重建），再重新开始。这里的保护是 transaction 内的 fail-closed 检查，
不是对持续运行的同 UID writer 的跨操作、持久防篡改保证。

`series.production_progress` 是 operator 内容生产记账，并采用 at-least-once 语义：安全 artifact 后若
progress rename/durability barrier 报错并返回 `psychology_learning_progress_persist_failed` 时，完成标记仍可能
已经落盘。不要手改 sidecar；重新查询 roadmap，或用同一 series/version/lesson 重试，重试是 idempotent。它仍不是读者学习进度、发布状态或自动
下一课指令。

#### Builtin catalog

未选 lesson 的查询会返回 `selection_required`，不会默认第一课；课程目录拥有该课的
catalog-owned image plan。`--psychology-curriculum-version 1` 选择的是 builtin frozen catalog；
该 catalog 当前用的是 controlled template v2，因此会渲染 7 张 cards。不要把 curriculum version 与
controlled template version 混为一谈。

```bash
# 目录查询不会创建 run，也不会读取 live topic research；会返回 selection_required。
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id after_work_rumination \
  --non-interactive --format json

# 用户确认后再次取回该课的精确 direction、标题/封面钩子和图片计划。
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id after_work_rumination \
  --psychology-lesson-id notice_the_loop \
  --psychology-curriculum-version 1 \
  --non-interactive --format json

# 仅将上一步返回的 lesson id 与 matching direction id 带回；先 dry-run。
uv run python -m ptsm.bootstrap run-playbook \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --psychology-content-mode learning_series \
  --psychology-series-id after_work_rumination \
  --psychology-lesson-id notice_the_loop \
  --psychology-curriculum-version 1 \
  --topic-direction-id psychology_learning_after_work_rumination_notice_the_loop \
  --publish-mode dry-run --eval --auto-generate-image
```

`psychology_learning_required`、`psychology_learning_invalid`、
`psychology_learning_topic_direction_invalid`、`psychology_learning_draft_invalid` 或
`psychology_learning_artifact_invalid` 都是安全停点；图片 set 失败则返回
`psychology_carousel_generation_failed`。修正 catalog selection 或本地 set 条件后重新开始，
不要在同一请求中加自由场景绕过它。成功 artifact 只含 series/lesson receipt 和 opaque
references，可用 `eval-artifact` 复核。

### Reddit Discussion Scan

Reddit英文讨论转译使用 Reddit app-only OAuth 做只读扫描，不需要 Reddit 用户名或密码。按 Reddit Responsible Builder Policy，读取 Reddit API 前需要为该用途取得 explicit approval；app 描述要透明说明只读取公开 hot/top 英文讨论用于人工编辑参考，不做自动回帖、投票、私信、商业化 Reddit 数据或 AI 训练。读者可见成稿只呈现中文热点帖，不暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL。创建并获批 Reddit app 后配置：

```env
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-client-secret
REDDIT_USER_AGENT=ptsm:reddit-curation:0.1 (by /u/your_reddit_username)
REDDIT_PUBLIC_JSON_FALLBACK=true
REDDIT_SUBREDDITS=OpenAI,ChatGPT,ClaudeAI,ArtificialInteligence,singularity,psychology,AskPsychology,productivity
REDDIT_SORTS=hot,top
REDDIT_TIME_FILTER=day
REDDIT_LIMIT_PER_LISTING=12
```

如果 Reddit app 创建被 reCAPTCHA 或审批卡住，可以先只配置 `REDDIT_USER_AGENT` 并保留 `REDDIT_PUBLIC_JSON_FALLBACK=true`。这会读取 `reddit.com/r/<sub>/<sort>.json` public listing 做低频只读 fallback；仍需遵守 Reddit policy、限量请求，并避免把 Reddit 原文长段或来源痕迹带到小红书成稿里。

如果未配置 Reddit env，artifact 的 `runtime_skill_details` 仍会记录 `reddit_discussion_scan`，但 runtime context 会标记 `missing_credentials`。这时可以做离线结构验证，不应把正文当成“最新热点”。

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

Eval 会对 artifact 的 planner skill activation、executor final content、reflector decision、image generation、publish result、post-publish checks 和 artifact completeness 分别运行 rule evaluator（required fields、hashtags、publish mode、dry-run safety）和 contract evaluator（root fields、skill match、playbook node contract）。XHS playbook node contract 会检查必需标签、标题泛化、正文长度带、保存/评论触发和模板化语言。结果写入 `.ptsm/evals/<eval_run_id>/summary.json` + `results.jsonl`。

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
    "account_id": "acct-classic-poetry-local",
    "nickname": "古诗词金句实验号",
    "platform": "xiaohongshu",
    "domain": "古诗词金句",
    "publish_mode": "dry-run",
    "cookie_profile_id": "classic-poetry-local-cookie",
    "cookie_path": "cookies/classic-poetry-local.json"
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
| 古诗词金句 | `acct-classic-poetry-local` | `cookies/classic-poetry-local.json` | 经典诗词金句、可保存读法、生活共鸣 |
| 武侠人物评述 | `acct-wuxia-local` | (未绑定 cookie) | 金庸古龙人物深度评述 |
| AI科技资讯 | `acct-ai-tech-local` | (未绑定 cookie) | evidence-gated 快讯、实测记录与事实转译 |
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

# 登录古诗词金句账号（另一个终端，另一个端口）
COOKIES_PATH=cookies/classic-poetry-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64 -port :18061
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

# 古诗词金句领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "读到李白长风破浪会有时，想写给低谷里的自己" \
  --account-id acct-classic-poetry-local \
  --playbook-id classic_poetry_quote_post

# 武侠人物评述领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "分析令狐冲的自由人格" \
  --account-id acct-wuxia-local \
  --playbook-id wuxia_character_post

# AI科技资讯领域
uv run python -m ptsm.bootstrap run-playbook \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post \
  --ai-content-mode fact_translation \
  --ai-evidence-file /path/to/ai-evidence.json \
  --publish-mode dry-run

# 每日英语学习领域
uv run python -m ptsm.bootstrap run-playbook \
  --scene "学一个表示坚持的高级词汇" \
  --account-id acct-daily-english-local \
  --playbook-id daily_english_post

# 现代心理困境观察领域
uv run python -m ptsm.bootstrap guide-post \
  --scene "看到别人周末都在聚会，自己突然觉得很失败"

uv run python -m ptsm.bootstrap guide-post \
  --scene "对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap run-playbook \
  --scene "下班后还在反复复盘白天一句话" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post

# 人类丰容实验领域
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id human_enrichment_daily_post \
  --account-id acct-enrichment-local \
  --scene "把书桌改成十分钟手作角" \
  --non-interactive

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
| `acct-classic-poetry-local` | `cookies/classic-poetry-local.json` |

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

## Discovery-First Hotspot Operation

当问题是“现在有什么热点、先找热点再决定写什么”时，先执行：

```bash
uv run python -m ptsm.bootstrap hotspot-discovery --max-hotspots 12
```

阅读 `outputs/artifacts/hotspot-discovery/` 的 JSON/Markdown 和 scan status。默认只展示按 score
排序的前 12 个，`eligible_hotspot_count` / `returned_hotspot_count` / `hotspot_limit` 会说明截断；
主列表外的已有领域候选从 `routed_hotspots` 读取（每行至少引入一个未展示 playbook；`ambiguous` 保留完整候选），且不会改变全平台排名。`partial` 时先处理 platform diagnostics；`insufficient_evidence` 时不要生成静态热点列表。`operator_headline` 只是
操作者阅读字段，选择映射后的 playbook/account 后才运行 `guide-post` 或 `run-playbook`。

当操作目标是比较明确的 XHS 候选赛道，才使用 `xhs-domain-opportunity --keywords "..."`。该命令
不再接受空白/仅分隔符关键词的默认回退，因此它不能取代 `hotspot-discovery`。
