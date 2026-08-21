---
title: PTSM Operations
status: active
owner: ptsm
last_verified: 2026-08-21
source_of_truth: true
related_paths:
  - docs/operations/publish-quickstart.md
  - docs/operations/cloud-bootstrap.md
  - docs/operations/local-runbook.md
  - docs/operations/content-experiment-runbook.md
  - docs/operations/topic-radar-runbook.md
  - docs/operations/task-completion-automation.md
  - docs/research/2026-05-15-xhs-content-experiment-log.md
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
  - integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
  - integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md
  - integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md
  - src/ptsm/application/models.py
  - src/ptsm/interfaces/cli/main.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/infrastructure/memory/store.py
  - src/ptsm/application/services/image_carousel_transaction.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/psychology_learning_series.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/psychology_carousel.py
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/analyze_xhs_patterns.py
  - src/ptsm/application/use_cases/xhs_domain_opportunity.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/skills/runtime_context.py
  - src/topic_radar/cli.py
  - src/topic_radar/analysis/evidence.py
  - src/ptsm/infrastructure/images/note_card_backend.py
  - src/ptsm/application/use_cases/docs_sync.py
  - src/ptsm/application/use_cases/eval_artifact.py
  - src/ptsm/application/use_cases/xhs_post_metrics.py
  - src/ptsm/application/use_cases/harness_check.py
  - src/ptsm/application/use_cases/install_git_hooks.py
  - .github/workflows/harness.yml
  - .github/workflows/docs-sync.yml
  - .github/pull_request_template.md
---

# Operations

这个页面只做操作索引，不重复复制 runbook 内容。

## Prerequisites: Start MCP Server

topic-radar 扫描和真实发布都需要 `xiaohongshu-mcp` 服务。在另一个终端启动：

```bash
# 默认启动（全局 cookie）
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64

# 指定账号 cookie
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

监听 `localhost:18060`，对应 `XHS_MCP_SERVER_URL=http://localhost:18060/mcp`。PTSM 不会自动拉起它。

## Primary Runbooks

- 简洁发布手册: [`docs/operations/publish-quickstart.md`](operations/publish-quickstart.md)
- 云上 clone 与启动: [`docs/operations/cloud-bootstrap.md`](operations/cloud-bootstrap.md)
- 本地运行与排障: [`docs/operations/local-runbook.md`](operations/local-runbook.md)
- 内容实验与指标回收: [`docs/operations/content-experiment-runbook.md`](operations/content-experiment-runbook.md)
- 任务完成后的自动校验: [`docs/operations/task-completion-automation.md`](operations/task-completion-automation.md)

## Stable Operator Commands

- `uv run python -m ptsm.bootstrap --help`
- `uv run python -m ptsm.bootstrap doctor`
- `uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main`
- `uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/interfaces/cli/main.py --changed-path docs/operations/local-runbook.md`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict`
- `uv run python -m ptsm.bootstrap harness-check --changed-path src/ptsm/application/use_cases/harness_check.py --changed-path docs/operations.md`
- `uv run python -m ptsm.bootstrap install-git-hooks --base-ref origin/main`
- `uv run python -m ptsm.bootstrap gc`
- `uv run python -m ptsm.bootstrap gc --apply --runs-retention-days 14 --plan-runs-retention-days 14`
- `uv run python -m ptsm.bootstrap harness-evals --platform xiaohongshu --playbook-id fengkuang_daily_post`
- `uv run python -m ptsm.bootstrap harness-report --platform xiaohongshu --playbook-id fengkuang_daily_post --max-stale-docs 0 --min-run-completion-rate 0.8`
- `uv run python -m ptsm.bootstrap harness-report --fail-on-warning`
- `uv run python -m ptsm.bootstrap eval-artifact --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap diagnose-publish --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap diagnose-publish --run-id <run_id>`
- `uv run python -m ptsm.bootstrap xhs-record-metrics --artifact outputs/artifacts/<artifact>.json --checkpoint 24h --views 1000 --likes 80 --collects 60 --comments 8 --shares 2 --decision keep`
- `uv run python -m ptsm.bootstrap xhs-metrics-report --playbook-id modern_psychology_post --checkpoint 24h --group-by topic_direction_id`
- `uv run python -m ptsm.bootstrap xhs-metrics-report --playbook-id modern_psychology_post --checkpoint 24h --group-by image_style`
- `uv run python -m ptsm.bootstrap xhs-metrics-report --playbook-id modern_psychology_post --checkpoint 24h --group-by carousel_style`
- `uv run python -m ptsm.bootstrap logs --run-id <run_id>`
- `uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap runs --account-id <account_id> --status completed`
- `uv run python -m ptsm.bootstrap run-events --account-id <account_id> --event publish_finished --group-by status`
- `uv run python -m ptsm.bootstrap plan-runs --status failed --failure-reason pytest_failed`
- `uv run python -m ptsm.bootstrap run-playbook --scene "读到李白长风破浪会有时，想写给低谷里的自己" --account-id acct-classic-poetry-local --playbook-id classic_poetry_quote_post`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --eval`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --auto-generate-image`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "领导18:57发来一句在吗" --account-id acct-fk-local --auto-generate-image --local-image-style wechat_chat`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --publish-mode mcp-real --auto-generate-image --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --publish-mode mcp-real --auto-generate-image --publish-visibility "公开" --wait-for-publish-status`
- `uv run python -m ptsm.bootstrap run-playbook --scene "分析令狐冲的自由人格与当代职场" --account-id acct-wuxia-local --playbook-id wuxia_character_post`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --auto-generate-image`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "仅自己可见"`
- AI 科技 evidence-gated dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --account-id acct-ai-tech-local --playbook-id ai_tech_daily_post --ai-content-mode hands_on --ai-evidence-file /path/to/ai-evidence.json --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --scene "学一个表示坚持的高级词汇" --account-id acct-daily-english-local --playbook-id daily_english_post`
- Reddit英文讨论转译 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度" --account-id acct-reddit-curation-local --playbook-id reddit_curation_daily_post`
- 世界杯主题 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点" --account-id acct-world-cup-local --playbook-id world_cup_daily_post`
- 人设/爆品梗回归 dry-run:
  `uv run python -m ptsm.bootstrap run-fengkuang --scene "领导递来丝瓜汤式复盘，工牌当场想保持高雅" --account-id acct-fk-local --eval`
- 人设/爆品梗回归 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "同事临时加需求，想练一版三明治拒绝法边界句" --account-id acct-psychology-local --playbook-id modern_psychology_post --eval`
- 人设/爆品梗回归 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "一个人住，想把床头角落改成十分钟适我主义手作位" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --eval`
- `uv run python -m ptsm.bootstrap guide-post`
- `uv run python -m ptsm.bootstrap guide-post --scene "看到别人周末都在聚会，自己突然觉得很失败" --non-interactive`
- `uv run python -m ptsm.bootstrap guide-post --scene "他3小时没回消息，我已经想好分手后猫归谁了" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --scene "睡眠恢复和轻养生很火，想写办公室下班后的5分钟恢复" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --scene "对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --scene "约好的局临时不想去了，怕扫兴又很累，想写社交电量边界" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --scene "领导18:57发来一句在吗，下班后身体被消息拉回工位" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id fengkuang_daily_post --account-id acct-fk-local --scene "领导18:57发来一句在吗，工牌想替我发疯" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id human_enrichment_daily_post --account-id acct-enrichment-local --scene "想把书桌角落改成十分钟适我主义手作位" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id classic_poetry_quote_post --account-id acct-classic-poetry-local --scene "读到李白长风破浪会有时，想写给低谷里的自己" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id classic_poetry_quote_post --account-id acct-classic-poetry-local --scene "下班路上想用王维空山新雨后写一点松弛感" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id wuxia_character_post --account-id acct-wuxia-local --scene "想用令狐冲写一种当代职场里的自由人格" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --ai-content-mode news_brief --ai-evidence-file /path/to/ai-evidence.json --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --ai-content-mode hands_on --ai-evidence-file /path/to/ai-evidence.json --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --ai-content-mode fact_translation --ai-evidence-file /path/to/ai-evidence.json --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id daily_english_post --account-id acct-daily-english-local --scene "学一个表示坚持的高级词汇，想配真实职场例句" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id world_cup_daily_post --account-id acct-world-cup-local --scene "阿根廷和法国决赛前，想写普通球迷看球清单" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id reddit_curation_daily_post --account-id acct-reddit-curation-local --scene "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap run-playbook --caller openclaw --scene "他3小时没回消息，我已经想好分手后猫归谁了" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --caller openclaw --guidance-ack --scene "他3小时没回消息，我已经想好分手后猫归谁了" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --scene "凌晨两点，我还在改白天会议那句话" --account-id acct-psychology-local --playbook-id modern_psychology_post`
- `uv run python -m ptsm.bootstrap run-playbook --scene "凌晨两点，我还在改白天会议那句话" --account-id acct-psychology-local --playbook-id modern_psychology_post --auto-generate-image`
- `uv run python -m ptsm.bootstrap run-playbook --scene "办公室下班后还是很紧绷，想写一个睡眠恢复和轻养生的5分钟下班信号" --account-id acct-psychology-local --playbook-id modern_psychology_post --eval --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --account-id acct-ai-tech-local --playbook-id ai_tech_daily_post --topic-direction-id <matching-direction-id> --ai-content-mode fact_translation --ai-evidence-file /path/to/ai-evidence.json --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-fengkuang --fresh-topic-research --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap run-playbook --fresh-topic-research --account-id acct-psychology-local --playbook-id modern_psychology_post`
- `uv run python -m ptsm.bootstrap hotspot-discovery --max-hotspots 12`
- `uv run python -m ptsm.bootstrap run-fengkuang --fresh-topic-research --account-id acct-fk-local --auto-generate-image --publish-mode mcp-real --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "公开" --wait-for-publish-status`
- `uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap collect-xhs-patterns --lane human_enrichment --keywords "人类丰容,家的丰容计划,低成本改造,钩织,拼豆" --sample-limit-per-keyword 8`
- `uv run python -m ptsm.bootstrap analyze-xhs-patterns --sample-path outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json --lane human_enrichment`
- `uv run python -m ptsm.bootstrap run-playbook --scene "把书桌改成十分钟手作角" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --format-pattern-path outputs/artifacts/xhs-pattern-library/current.json`

## AI Tech Evidence-Gated Runs

`ai_tech_daily_post` 的 `--scene` 不是事实输入；有效运行必须同时给出
`--ai-content-mode` 和 `--ai-evidence-file <json>`。文件根字段 `mode` 必须和 CLI mode
相同，且只可使用下列三种 shape。`source_refs`、`test_evidence_refs`、
`event_fingerprint`、`cluster_id` 和 `evidence_ids` 都是 opaque identifier，例如
`source:release-001`；不要填 URL、域名、作者、feed ID 或原始标题。

```json
{
  "mode": "news_brief",
  "news_items": [
    {"label": "模型更新", "event_fingerprint": "event:model-001", "facts": ["已核验的公开事实"], "source_refs": ["source:release-001"]},
    {"label": "开发者工具", "event_fingerprint": "event:tool-002", "facts": ["另一条已核验事实"], "source_refs": ["source:release-002"]},
    {"label": "产品能力", "event_fingerprint": "event:product-003", "facts": ["第三条已核验事实"], "source_refs": ["source:release-003"]}
  ]
}
```

```json
{
  "mode": "hands_on",
  "topic": {"label": "长文摘要任务"},
  "hands_on": {
    "product": "测试工具", "version": "2026-07", "tested_at": "2026-07-23",
    "task": "把一段长文整理成要点", "input_summary": "一段去敏的长文本",
    "observed_output": "输出了结构化要点", "limitation": "复杂表格仍需人工复核",
    "test_evidence_refs": ["test:run-001"]
  }
}
```

```json
{
  "mode": "fact_translation",
  "topic": {"label": "某项产品能力变化"},
  "facts": [
    {"statement": "第一条已核验事实", "source_refs": ["source:release-010"]},
    {"statement": "第二条已核验事实", "source_refs": ["source:release-011"]}
  ],
  "audience": {"who_should_care": "需要这项能力的人", "who_can_wait": "暂不使用相关任务的人"}
}
```

`trend_support` 是可选的选择依据，形如 `{ "cluster_id": "cluster:topic-001" }` 或
`{ "evidence_ids": ["evidence:topic-001"] }`；它永远不替代 facts 或 test evidence。
先运行 `hotspot-discovery` 找不限定方向的全平台热点，人工核验并整理 evidence 文件后再运行
AI playbook。AI mode 使用 `--fresh-topic-research` 会返回
`ai_tech_fresh_research_separate`，不会扫描并把原始热点塞进草稿。

成功的 artifact 会含 `ai_tech_content_mode`、opaque `ai_tech_evidence_manifest` 和
`ai_tech_evidence_gate`；用 `eval-artifact --artifact <path>` 可离线审计 receipt。常见早停
状态为 `ai_tech_evidence_required`、`ai_tech_evidence_invalid`、
`ai_tech_topic_direction_invalid`、`ai_tech_draft_invalid` 与 `ai_tech_artifact_invalid`；这些都
发生在相应副作用之前。

## Psychology Text Carousel Runs

普通 `modern_psychology_post` 默认把一个主题表达成**一组** 4–7 张本地文字卡。它不是通用 batch
接口：用户显式要求超过 7 页/图片（例如 12 张）时，先停在三路 router，而不是循环运行：

- `one_carousel`：支持，一个主题的一组 4–7 页；确认主题后按一次普通 run 处理。
- `multiple_posts`：支持，但每一帖/主题都要用户分别明确确认、分别 guide/run，并各自取得 immutable
  receipt；“12 张”本身不是批量执行授权。
- `independent_assets`：不支持；8–12 张 **independent image assets**（不是帖子也不是 4–7 页 carousel）
  不属于当前心理学 wrapper/PTSM 路径。明确说 unsupported，并转交另行授权的素材工作流；不得把它暗改为
  carousel/多帖、生成假 receipt 或返回 ready。

不要静默拆分、循环运行、复用同一组或承诺未支持数量。`max_text_units` 是每页文字密度，不是图片数量。先用只读 guide 查看
`format_archetype=text_carousel`、`local_style=psychology_text_card_v1`、page range 和 ordered roles：

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --scene "凌晨两点，我还在改白天会议那句话" \
  --non-interactive --format json
```

选定 returned direction 后，只需用现有 `--auto-generate-image`；不要传手工页面或 carousel style：

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --scene "凌晨两点，我还在改白天会议那句话" \
  --topic-direction-id "<matching returned direction id>" \
  --publish-mode dry-run --auto-generate-image
```

`final_content.image_plan` 的 parent fields 是
`backend/style/role/text_density/max_text_units/cover_text_strategy/reason/prompt_focus/carousel_style/slides`；
每个 slide 只能有 `slide_id/order/role/headline/body_lines`。`slides.order` 是发布顺序，第一页必须是
低密度 `cover_hook`；inner pages 从 `concrete_scene`、`light_mechanism`、`save_tool`、
`scope_boundary`、`professional_boundary`、`comment_prompt` 中选择。所有页只讲同一主题；每页的
`max_text_units` 约束的是短行密度，而不是页数。

成功时检查 `image_generation.status=committed`、`image_count`、`set_id`、`manifest_path`、
`manifest_sha256` 和 ordered `pages`，并以 committed set 中的 `manifest.json` 为权威 receipt。普通
carousel 的 `pages` 必须完整连续地带 `order`、`page_sha256`（canonical page content）和
`file_sha256`（PNG bytes）。只有 canonical receipt 与 page-aware asset ledger 都成功后，才会 commit
per-account/per-playbook 的 cover-excluded inner fingerprint 到最近 12 个 successful complete ordinary
carousel receipts；draft artifact、reservation、失败页或 learning-series 都不占该窗口，失败会 release，过期
lease 可恢复。任一 page/manifest/ledger 不完整都会返回 `psychology_carousel_generation_failed`，不会进入
watermark、publisher 或 ready relay receipt；已在完整提交后发生的 publish failure 则保留 set，修复外部发布
条件后可重试。外层 chat/IM relay 只能在 ordinary `carousel_delivery.status=ready` 和
`external_relay_required=true` 时使用 receipt 的完整有序 `attachments` 转发，并以这些 canonical hashes
校验；PTSM 不拥有该 sender，ready 不等于已送达、已发布或已被 relay 接收。

relay 必须把 acknowledgement/outcome/retry 保存在自己的 durable record 中，**not a PTSM response schema**：
以 `set_id` / `manifest_sha256` 关联 immutable receipt，每次发送写 `relay_attempt_id`、
`relay_idempotency_key` 和（如为重试）`retry_of`；每个确认附件记录 `order`、`file_sha256` 与
`acknowledged_at`。`relay_outcome` 只能由 relay 写成 `pending`、`partial`、`delivered` 或 `failed`。
只有所有预期、按原序的附件都取得 sender acknowledgement，relay 才能写 `delivered`；PTSM 不写、不推断
ack、outcome 或 retry，也不因 relay 失败更改本地 receipt。重试保留同一 receipt identity/order 并使用
idempotency；目标支持逐张幂等时只重发未确认项，否则使用 channel-safe whole-set retry。若 ordinary
post 明确只要一张旧式封面，才传 `--local-image-style note_card|iphone_notes|wechat_chat`；该显式 override
保留 legacy single-image 行为。

## Psychology Learning Series Runs

`learning_series` 是 `modern_psychology_post` 的受控课程子模式，有 builtin
`after_work_rumination` 和 custom `user_confirmed` 两条路径。不要直接把 `--scene`、自由心理学
概念、热点、原始研究链接或 `--fresh-topic-research` 塞进课程 run。custom 主题必须先提案、审核、
精确确认；确认后只从 frozen catalog 选课。目录的标题、正文、封面和 catalog-owned image plan 受控
渲染，不能手改或用 `--local-image-style` / `--publish-image-path` 覆盖。historic confirmed
controlled-template-v1 继续验证原单卡；builtin 与新确认 custom revision 使用 template v2 的 7 张
`psychology_text_card_v1` catalog pages。`guide-post` 只展示 PTSM-returned `page_count` 与
`ordered_roles`，不会返回 `slides` 或 page copy；operator/wrapper 不得据此补写、改序或把正文重新分页，
真正的页面由 run 按 catalog exact plan 重建。

### Choose a publication mode first

面向用户的心理学发布先确认入口，而不是从 flags 倒推：**单篇心理学帖** 走普通 `guide-post --scene`
场景流；**内置学习系列** 查询 builtin `after_work_rumination` roadmap 后等待用户选课；**自定义学习系列**
由用户给主题和可选 2–6 项目录，再进入本节的 trusted provision、proposal/review/exact-confirmation、roadmap
和选课流程。意图不明确时先让用户选择，不能默认建立 custom catalog、生成或发布。“继续下一课”或“看系列进度”
先重新查询 roadmap，推荐顺序不是自动选课/生成/发布；“改目录”必须创建新 proposal 和 immutable version，不能
原地改已确认 catalog。下面保留各路径的精确命令和安全边界。

### Custom user-confirmed curriculum

先完成一次可信初始化。仅在首次创建该本地存储，或进行受信任离线维护时，在所有 writer 已停止且操作者
独占存储父目录的条件下执行；不要把它放进 workflow 或不可信 hook：

```bash
uv run python -m ptsm.bootstrap provision-psychology-learning-storage --format json
```

它创建/验证仅当前用户可访问的 `proposals`、`confirmations`、`catalogs`、`progress` 固定树。后续
`plan-psychology-series`、确认和 progress 写入只使用既有树，缺失、重绑或不可信目录会 fail closed，
不会补建为可信状态。这个命令不是清理或修复异常文件的手段；不可信残留只在所有 writer 停止后由
`trusted offline maintenance` 检查、重建或移除。

先把主题和可选 2–6 项 outline 交给 PTSM。outline 是 JSON list，每项只含安全的 `id`、`title` 与可选
`goal`；下面是两个条目的安全示例，保存为 `outline.json`：

```json
[
  {"id": "notice_patterns", "title": "先看见下班后的脑内续播", "goal": "识别一个反复出现的工作念头"},
  {"id": "practice_pause", "title": "给下班后的自己一个停顿", "goal": "练习一个短暂停顿动作"}
]
```

```bash
# 只生成 proposal/review；proposal JSON 是 `series.lessons` 加 top-level `publication_plan`，proposal 不返回 roadmap，也不会创建 runnable catalog 或 run。
uv run python -m ptsm.bootstrap plan-psychology-series \
  --topic "下班后如何把工作从脑子里放下" \
  --curriculum-outline-file outline.json \
  --format json

# 从上一步 JSON 原样复制 proposal_id 与 proposal_fingerprint，再明确确认。
uv run python -m ptsm.bootstrap confirm-psychology-series \
  --proposal-id "<returned proposal_id>" \
  --proposal-fingerprint "<returned proposal_fingerprint>" \
  --confirm \
  --format json
```

审核 proposal 的 `series.lessons`、top-level `publication_plan` 与 exact `proposal_fingerprint` 后才可确认。确认会创建 immutable
`user_confirmed` curriculum version；主题、outline、lesson identity 或顺序有变化时必须重新 plan/confirm，
没有 `--catalog-root` 或手写 catalog/progress 文件入口。接着先取路线图：

```bash
# 不带 lesson：custom response 返回 selection_required、`series.roadmap`、`series.publication_plan`、`series.recommended_next_lesson` 与 `series.production_progress`。
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --non-interactive --format json

# 用户明确选定一课（可不是推荐课）后，必须 pin 返回的 frozen version。
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --psychology-lesson-id "<chosen lesson_id>" \
  --psychology-curriculum-version "<returned curriculum_version>" \
  --non-interactive --format json
```

`series.recommended_next_lesson` 只是 publication suggestion；不会自动选择、生成或发布。仅把第二次 guide
返回的 matching `topic_direction_id` 与同一 explicit version 带进 dry-run。custom
`series.production_progress` 的 `kind` 是 `operator_content_production`，仅表示已经安全生成的运营内容，绝不是读者学习进度；不请求图片时沿用 safe
completed content-artifact 时机；请求图片时还必须先验证完整 committed carousel 与 page-aware asset ledger。preflight/workflow/eval/final-artifact/
carousel failure 不会推进，也不会自动发布下一课。用 `eval-artifact --artifact <path>` 审计 strict
`psychology_learning_catalog_receipt`；缺失或被篡改的 catalog/receipt 会安全拒绝。若 atomic rename 后的
边界检查失败，状态为 `psychology_learning_progress_persist_failed`：这具有 at-least-once 语义，不能据此
断言 progress 一定没有写入，也不能手工在线回滚/删除。恢复可信存储后重试同一课次是幂等的；可疑
artifact/progress 不复用、不发布，交给 `trusted offline maintenance`。

```bash
# 只用第二次 guide 返回的 exact version、lesson 和 matching direction；先 dry-run + eval。
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

生成后先查看 sealed response/artifact 的安全 receipt：`image_generation.status=committed`、
`renderer=ptsm_local_renderer`、`carousel_style=psychology_text_card_v1`、`image_count=7` 和
`manifest_sha256`。它不会暴露本地 path 或页面文案；可信本地 operator 如需验图，再在
`outputs/generated_images/` 中读取对应 committed set 的 `manifest.json` 并按 `pages.order` 检查 PNG，
也可查看 `outputs/artifacts/generated-image-assets/assets.jsonl` 中同 set 的 page-aware operational rows。
任一页/manifest/ledger 失败会返回
`psychology_carousel_generation_failed`，不会调用 publisher，也不会推进 custom production progress；
已提交 set 若只在后续 publish 失败则会保留，可在修复外部发布条件后重试。

### Builtin catalog

首期 builtin 目录为 `after_work_rumination`，curriculum version 为 `1`，但当前 controlled template
version 为 `2`。这两个版本号用途不同：前者选择 frozen catalog，后者决定 catalog-owned 7-page render。
`guide-post` 会返回当前 catalog version，
而实际 `run-playbook` 必须显式带上这个 version。初次路线图查询会返回 `selection_required`，不会默认
生成第一课或给出 run command；选中 lesson 后再请求一次 guide。builtin roadmap 不返回 custom-only
`series.publication_plan`、`series.recommended_next_lesson` 或 `series.production_progress`。

```bash
# 返回 selection_required roadmap 与六个 catalog learning_series_lesson directions，不创建 run
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id after_work_rumination \
  --non-interactive --format json

# 用户选课后再次获取该课的精确 direction、标题/封面钩子和 catalog image plan
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id after_work_rumination \
  --psychology-lesson-id notice_the_loop \
  --psychology-curriculum-version 1 \
  --non-interactive --format json

# 只使用上一步返回的 matching direction id；先 dry-run
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

常见早停状态为 `psychology_learning_required`、`psychology_learning_invalid`、
`psychology_learning_topic_direction_invalid`、`psychology_learning_draft_invalid` 和
`psychology_learning_artifact_invalid`；图片集不完整时为 `psychology_carousel_generation_failed`。
`psychology_learning_progress_persist_failed` 表示安全 artifact
可能已经完成、但 progress 边界未能确认，按 at-least-once 的幂等 retry/`trusted offline maintenance`
处理。其余状态都发生在对应副作用之前。系列 artifact 可用
`eval-artifact --artifact <path>` 复核，并通过实际数据而非推测复盘：

```bash
uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by psychology_learning_series_id

uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by psychology_learning_curriculum_version

uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by psychology_learning_lesson_id
```

少于 3 条记录的 series、version 或 lesson group 只是早期信号。只有 receipt-verified 的
learning artifact 才能写入课程指标；同一 artifact + checkpoint 会更新已有观测而非重复计数，且
课程分组会排除普通 `modern_psychology_post` 场景帖。普通场景帖继续使用既有 `guide-post` lane，
不能假装成某一课或自动推断读者进度。

## Usage Notes

- 默认校验门禁优先使用 `pytest` 和 `doctor`。
- `docs-sync` 会读取 source-of-truth 文档 front matter 里的 `related_paths`，要求相关代码变更至少伴随一个最具体候选文档面的更新。
- `harness-check` 会串起 `docs-sync`、本地 `harness-report` 和 deterministic `pytest -q`，是本地 pre-push 和 CI 的统一入口。
- `docs-sync --base-ref ...` 和 `harness-check --base-ref ...` 比较的是 `<base-ref>...HEAD` 的已提交 diff；如果要在 commit 之前预检当前工作树改动，改用 `--changed-path ...` 显式传入。
- 本地默认 `harness-check` 会把 `docs-sync`、source-of-truth docs freshness、deterministic pytest 和 `.ptsm/evals` 聚合出的 `required_failed > 0` 当成阻塞门禁；`--strict` 会把完整 `harness-report` warning 也变成阻塞。
- `install-git-hooks` 会写入 `.git/hooks/pre-push`，默认记录 `origin/main` 作为 base ref，并在 push 前先计算 `git merge-base HEAD origin/main`，再执行 `harness-check --base-ref <merge-base-sha>`。
- `gc` 默认只报告候选项；只有 `--apply` 才会删除本地 harness artifacts。
- `harness-evals` 只输出本地 JSON 汇总，不负责修改 artifact 或触发修复动作；现在也聚合 `.ptsm/evals` 中的 eval results。
- `harness-report` 是对 `doctor`、`gc`、`harness-evals` 的只读组合入口；需要把 warning 当成 gate 时，再显式加 `--fail-on-warning`。支持 `--max-required-eval-failures N` 对确定性 eval 失败做阈值控制。
- `eval` 默认关闭，每次运行时加 `--eval` 开启。CLI eval 只运行确定性 rule/contract evaluator；`eval-artifact` 显式启用 LLM judge 时会按 playbook `evaluation.yaml` 的 gate level 计入 `required_failed` 或 `warning_failed`。生成链路里的 XHS 内容质量 judge 由运行时 judge backend 配置决定，失败会触发重写而不是直接发布。
- 每个完成的 playbook artifact 和 CLI JSON 响应都会包含 `content_review`，用于人工确认生成逻辑、质量信号和发布前风险；review 不是自动发布批准。当前人审闭环通过 operator 阅读该说明并在对话中要求调整完成，不需要独立 review 操作台。
- `eval-artifact` 可对已有 artifact 独立跑 eval，不依赖运行时。
- `diagnose-publish` 是对单次发布问题的只读诊断入口，适合排查 “为什么没法自动确认已发布” 或 “为什么发布后状态不明确”。
- `xhs-record-metrics` / `xhs-metrics-report` 是内容实验的本地指标回收入口。前者把已发布帖子的 `2h`、`24h` 或 `72h` 浏览、点赞、收藏、评论、分享写入 `outputs/artifacts/xhs-post-metrics/metrics.jsonl`，并从 verified artifact 记录 `image_count` / `carousel_style`；旧/单图 artifact 规范化为 count `1` 和空 carousel style。后者可按方向、`image_style`、`carousel_style`、checkpoint、账号、playbook，或学习系列的 series / curriculum version / lesson 聚合。课程指标只接受 receipt-verified artifact；同一 artifact + checkpoint 是更新而非重复追加。心理学增长实验优先用 `--playbook-id modern_psychology_post --checkpoint 24h --group-by topic_direction_id` 比较方向，再用 `--group-by carousel_style` 区分 `psychology_text_card_v1` 与单张封面；课程比较则使用 `psychology_learning_series_id`、`psychology_learning_curriculum_version` 或 `psychology_learning_lesson_id`，并自动排除普通场景帖。少于 3 条记录的 group 只作为早期信号，不应直接改 prompt。
- 除 AI evidence mode 和 `modern_psychology_post --psychology-content-mode learning_series` 外，`--fresh-topic-research` 是已选 playbook 的实时 Topic Radar 发帖路径，且此时 `--scene` 可选；泛热点应先用 `hotspot-discovery`。learning series 的 Topic Radar 结果只能用于发现是否值得规划专题，不能成为 lesson facts、evidence、outline 或 run input。fresh 路径使用 public `topic_radar.cli.run_scan()` 的八平台默认集合，交互式只展示 evidence-backed 选题；`insufficient_evidence` 会在 workflow 前返回 diagnostic artifact、report path 和 platform errors，`partial` 会保留这些诊断并由 operator 决定是否继续。选择后正文只收到选定角度、讨论诱因和构造场景；raw title、作者、URL、feed id、token 与终端 `scan_summary` 都留在 Topic Radar surface。普通路径不回读旧 artifact；fresh builder 仅接受本次 receipt 明示且可读的 artifact，workflow 不会再发起第二次 live scan。`ai_tech_daily_post` 则返回 `ai_tech_fresh_research_separate`，必须先发现、再在 evidence 文件中独立记录事实或测试。
- `collect-xhs-patterns` / `analyze-xhs-patterns` 是周期采集和格式沉淀入口。普通 `run-playbook` 默认只读取本地 pattern snapshot，不会每次发帖都检索实时高互动帖子；需要实验特定 snapshot 时，用 `--format-pattern-path` 覆盖。
- 2026-06-04 的正文人味优化尝试用 `collect-xhs-patterns --lane body_human_voice --keywords "活人感,小红书文案,发疯文学,情绪管理,人类丰容"` 做 bounded live XHS 抓取，但当前 MCP `search_feeds` 对 `活人感` / `小红书文案` 返回 HTTP 500，落盘 artifact `outputs/artifacts/xhs-body-human-voice/samples-2026-06-04.json` 的 `sample_count` 为 0。因此这次策略只把 2026-05-15 / 2026-05-17 本地真实样本和公开趋势摘要作为依据，不声称拿到了 2026-06-04 热门帖样本。后续要刷新热门帖，先恢复 MCP 登录/健康，再重跑 bounded `collect-xhs-patterns`。
- `reddit_curation_daily_post` 会在 `reddit_discussion_scan` skill 激活时尝试读取 Reddit 英文讨论作为内部素材。按 Reddit Responsible Builder Policy，读取 Reddit API 前需要为该用途取得 explicit approval，并保持透明、限量、只读、不规避限制、不做 Reddit 数据商业化或 AI 训练。配置已获批 app 的 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT` 后会用 OAuth 形成真实最新 Reddit runtime context；如果 app 创建受验证码阻塞，可先设置 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT`，用 Reddit public `.json` 页面低频只读扫描。未配置时 dry-run 会完成但上下文标记为 `missing_credentials`。读者可见成稿只呈现中文热点帖，不暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL。
- `run-playbook` 是多 playbook 的通用入口；`run-fengkuang` 只保留给已有发疯文学兼容脚本和习惯命令。
- 做 XHS persona 或热梗映射回归时，优先用 dry-run 加 `--eval` 检查 artifact：标题应在 22 字以内，并以该领域的具体物件、关系、场景或一句原话切入，同时避开 `日常`、`实录`、`干货分享` 等泛标题；不再要求所有领域使用同一批张力 cue。正文使用 `xhs_compact_native_v1` 的 2–4 个短节拍：现场/真人锚点、一个可用领域细节和自然的保存或回复入口（可合并为一句），并落在 playbook 的紧凑长度带内。现代心理学还要额外检查标题不出现心理机制名或 `不是你` 破梗，正文控制在 200-380 字，用一句轻机制服务场景，用 `哪派`、`A.` / `B.` 或 `____` 这类认领入口替代泛泛问经历。eval 用 `title_max_chars`、领域化 `title_must_include_any` / `title_must_not_include_any`、body length band、`body_must_include_scene_signal`、`body_scene_signal_any`、`body_human_anchor_any` 和 `combined_must_not_include_any` 拦截泛标题、过长/过短正文、缺少现场/真人锚点的正文、`首先`、`其次`、`综上`、`本文`、`作为AI` 等模板化或元叙事表达，也会拦截 `可复制疯话`、`可收藏小结`、`可保存单元`、`评论交接` 等读者可见的内部功能标签。
- `guide-post` 是小红书发帖前的只读选题向导：支持当前九个 playbook：`modern_psychology_post`、`fengkuang_daily_post`、`human_enrichment_daily_post`、`classic_poetry_quote_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。默认走对话式引导；脚本场景用 `--non-interactive` 输出 JSON。JSON 和 Markdown 都包含场景相关的 4 个 `topic_guidance.directions`，把本地热点/爆点机制产品化为用户可选方向；输出带 `selection_policy == "dynamic_scene_diversity_rerank"`、`open_direction_ids`、兼容字段 `open_direction_id` 和 `direction_type_counts`。selector 从 curated 候选和多个 PTSM 本地组合的 `open_scene` 候选中动态选择方向，scene 关键词只来自用户输入，lane affinity 只来自选题 lane，并用 diversity family、direction source type 和 open-scene mechanism 避免不同场景只得到同一组固定锚点。每个方向带 `direction_type`、`scene_fit`、`trend_signal`、`viral_hook`、适合场景、内容角度、保存工具、评论提示、避坑和 `format_recommendation`；格式建议包含 `format_archetype`、`cover_role`、`body_shape`、`visual_evidence_need` 和 `avoid_format`，用于确认方向后的封面/正文/评论结构约束。输出还带 `topic_guidance.image_recommendation`。普通心理学默认让所有 returned direction 使用 `text_carousel / cover_hook`；顶层建议使用 `format_archetype=text_carousel` / `role=text_carousel`，另返回 `psychology_text_card_v1`、4–7 页、从 `cover_hook` 开始的 ordered roles 与 `command_hint=--auto-generate-image`。其 `open_scene` 候选只使用心理学可用的 copyable line、micro task、comment pattern 或 save card，不会混入世界杯看球清单或 AI 工具交接语义；显式 `guide-post --image-style wechat_chat|iphone_notes|note_card` 则精确保留指定的单图 recommendation，后续命令使用对应的 `run-playbook --local-image-style ...`，并在重建方向时保持同一单图格式。其他本地单图才给 `--local-image-style wechat_chat|iphone_notes|note_card`，provider 图给 `--auto-generate-image`、provider/model。输出不包含 research 文件路径、原始来源说明、URL 或 provenance。普通 `guide-post` 不默认运行 live XHS / topic-radar 扫描。真正生成和发布仍走 `run-playbook`；带 `--topic-direction-id <chosen id>` 时，运行时会把该方向的公开 payload 注入 `topic_selection.direction` 和 drafting runtime context。
- `ai_tech_daily_post` 是 `guide-post` 的模式例外：`--non-interactive` 时必须传 `--ai-content-mode`；返回的 directions 都带同一个 `content_mode`，没有 `open_scene` fallback。传 `--ai-evidence-file` 会让返回的 dry-run command 带上同一路径；随后应选一个 matching `topic_direction_id` 并执行 evidence-gated `run-playbook`。提示词相关选择只会在 `hands_on` 出现，成稿需展示一次已记录的测试任务、观察输出与局限，而不是“直接复制”的通用 prompt。
- 古诗词金句 `guide-post` 不把诗词 scene 默认解释为苏轼或怀民。泛古诗词/经典诗句场景应返回唐诗金句、宋词清醒、月亮乡愁、山水松弛、杜甫现实感、节气四季等可选方向；明确提到苏轼、定风波、赤壁或怀民时，苏轼方向才作为候选子线出现。默认标签是 `#古诗词`，不强制 `#苏轼`。
- 心理学 `guide-post` 保留更丰富的六步 brief：先问具体场景，再建议心理学 lane、机制、非诊断化重构、可保存动作、角色/阵营/填空式评论提示和 4–7 页 semantic carousel；第一页仍是低密度 cover，生成时机制用于服务场景，不应前置成标题破梗。非心理学交互只问具体场景、可选 lane 和评论提示覆盖，避免把心理学机制问题套到其他领域。
- 对 `他3小时没回消息，我已经想好分手后猫归谁了` 这类亲密关系等待消息场景，心理学 `guide-post` 应返回 `亲密关系 / 不确定感`、`事实 / 脑补 / 我需要什么` 和 `psychology_text_card_v1` 轮播建议；不要把它作为职场协作式消息边界回复来生成。只有 caller 明确要求单封面并传 `--local-image-style iphone_notes` 时才走旧路径。
- 对 `睡眠恢复和轻养生很火，想写办公室下班后的5分钟恢复` 这类增长子线场景，心理学 `guide-post` 应返回 `睡眠恢复 / 轻养生`、`sleep_recovery_shutdown_card`、`5 分钟下班信号` 和 semantic carousel；这是 `modern_psychology_post` 的子线实验，不是新养生 playbook，也不能写成医疗、营养或治疗建议。2026-06-02 的 live opportunity scan 因 MCP 缺少 `search_feeds` 没有真实样本，不能把这条子线称为已验证趋势排名。
- 对 `对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队` 这类亲密关系场景，心理学 `guide-post` 应返回 `relationship_mixed_signal_camp_vote`、`事实 / 信号 / 我要不要问清楚` 和 A/B 阵营评论入口；不要把它写成职场处理时间或优先级。
- 对 `约好的局临时不想去了，怕扫兴又很累，想写社交电量边界` 这类社交耗竭场景，心理学 `guide-post` 应返回 `social_battery_cancel_plan_boundary`、`取消局三句` 和 A/B 角色认领；不要鼓励失联或羞辱社交。
- 对 `领导18:57发来一句在吗，下班后身体被消息拉回工位` 这类下班消息场景，心理学 `guide-post` 应返回 `after_hours_message_body_alarm`、`下班消息三步` 和 A/B/C 评论入口；这是心理学的职场低控制感/身体警报表达，不是发疯文学。
- OpenClaw 心理学集成使用 `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` 作为薄 wrapper：先调用 `guide-post` 展示 `topic_guidance.directions`、`direction_type`、`scene_fit` 和 `format_recommendation`，用户确认方向后再调用 `run-playbook --caller openclaw --guidance-ack --topic-direction-id <chosen id>`。用户要求 >7/12 张时，wrapper 必须明确选择 `one_carousel`（支持的一组 4–7 页）、`multiple_posts`（每帖分别确认和独立 receipt），或 unsupported `independent_assets`（8–12 张 independent image assets 要转交外部素材工作流）；绝不在 PTSM 内循环或把三路折叠成假 batch。如果 OpenClaw 直接调用 `run-playbook --caller openclaw` 生成 `modern_psychology_post` 且没有 `--guidance-ack`，PTSM 会返回 `topic_guidance_required`，不会启动 workflow、写 run 或发布。成功普通轮播只提供 `carousel_delivery.status=ready` 的本地 relay handoff；外部 sender 的 ACK、`relay_outcome` 和 retry 记录属于 relay，只有所有 ordered `attachments` 获确认才可称 delivered，不能倒灌为 PTSM 成功。
- OpenClaw 非心理学 XHS 集成使用 `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`。该 wrapper 自动把发疯文学、人类丰容、古诗词金句、武侠人物、AI科技、每日英语、世界杯和 Reddit英文讨论转译意图映射到对应 playbook；意图模糊时先问一个短澄清问题。除 AI 科技外，方向确认后展示 PTSM 返回的 `format_recommendation` 和 `topic_guidance.image_recommendation`，再 dry-run 生成，并把确认的方向 id 作为 `--topic-direction-id` 传给 `run-playbook`。AI 科技必须先选 evidence mode、获取 matching direction，并带 `--ai-content-mode` + `--ai-evidence-file`；它有应用层 evidence preflight，即使 caller 是 OpenClaw 也不能跳过。wrapper 只能展示 PTSM-returned direction、格式/图片建议，不能自己发明开放方向、格式或图片策略。心理学的 `guidance_ack` 是独立 gate；其他非心理学 playbook 不因缺 guidance ack 被拒绝。
- OpenClaw/Codex 领域机会分析使用 `integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md` 作为薄 wrapper：当用户给出明确候选小红书领域/关键词、想比较覆盖缺口时，先调用 `xhs-domain-opportunity` CLI 生成 JSON/Markdown brief，再按 `existing_playbook_fit`、`sublane_first`、`new_domain_candidate` 给下一步建议。该 scan 只比较 bounded XHS keyword-search evidence：跨关键词优先去重同一 `feed_id`，完整 title+author 只桥接缺 ID 的一条观察到首个真实 ID，后续不同真实 ID 仍保留；若已有多个真实 ID，后续缺 ID 样本也保持 unresolved。ASCII `,` 和中文 `，` 可以分隔关键词，但 separator-only 输入会被拒绝。`insufficient_evidence` 或 no successful unique samples 时不得输出静态 ranking/fit/new-domain 结论；默认登录预检的 `login_required` 表示尚未搜索，必须先恢复 XHS 登录。wrapper 不生成、不发布、不复制 PTSM scoring，也不展示原始 feed id/token。
- `hotspot-discovery` 是默认的 discovery-first 操作入口：它不接受领域、账号、playbook、平台或关键词筛选，先运行 Topic Radar 默认平台扫描，再按 evidence-backed cluster 输出 `existing_playbook_fit`、`ambiguous`、`unmapped` 和可能的 `new_domain_candidate`。默认按 score 展示前 12 个；`--max-hotspots` 仅改变返回条数，receipt 必须保留 `eligible_hotspot_count` / `returned_hotspot_count` / `hotspot_limit`。如果 Top-N 外仍有已映射候选，`routed_hotspots` 会以不重复的补充视图给出最多 6 个；每行至少引入一个未展示 playbook，`ambiguous` 保留完整候选，并以 `route_status_counts` 说明完整已验证 cluster 集合的路由分布；它不改变全平台排名。阅读 `partial` 必须先展示 `platform_errors`，不得称为全平台结果；`insufficient_evidence` 时无可用热点建议。用户选择一个已有 playbook 后才进入 `guide-post` / `run-playbook`。OpenClaw/Codex 通过 `integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md` 调用它。
- `--auto-generate-image` 会在缺少 `--publish-image-path` 时执行已验证的图片计划；普通单图仍按即梦、百炼或本地 renderer 路由，现代心理学 text carousel 则始终使用 local-only `psychology_text_card_v1` transaction，不被 provider 配置替换。PTSM 生成图会请求源头不加 provider 水印，并在 artifact 的 `image_generation.watermark_policy` 里记录 `no_provider_watermark` 和具体 controls；本地 renderer 记录 `image_generation.provenance.source == "ptsm_local_renderer"`，完整 carousel 作为一组跳过去水印。
- `--no-auto-generate-image` 可以关闭自动补图；`--publish-image-path` 使用手动图片；`--local-image-style note_card|iphone_notes|wechat_chat` 可以主动选择本地截图式封面，即使外部图片 provider 已配置也生效。当前 `wechat_chat` 是内容区聊天转录封面，不绘制手机头部、底部输入栏或头像；正文或 `final_content.image_plan` 中的 `theme`、`chat_title`、`chat_times`、`golden_line` 等本地渲染参数会进入 renderer payload 和 artifact 证据。缺省本地时间会按 scene 明确时间或 payload hash 确定性变化，generic 对话发言人会补模拟昵称。
- 真实发布会按图片来源执行去水印：PTSM 本地 renderer 图片不画水印，也跳过 `watermark_removal` 后处理；provider/LLM 生成图和手动 `--publish-image-path` 图片仍会经过防御性去水印。dry-run 图片实验仍可用 `WATERMARK_REMOVAL_ENABLED=true` 选择是否预览 provider/manual 图片清理。
- 自动生成图片会更新本地资产台账 `outputs/artifacts/generated-image-assets/assets.jsonl`。单图保留既有记录；carousel 按 manifest order 原子写入整批 page-aware entries，包括 set/manifest、slide id/order/role、path 和 `page_sha256` / `file_sha256`，任一页不一致时不保留部分 batch，也不会给 ordinary run `carousel_delivery.status=ready`。current v2 learning carousel 也写该 operational ledger，但 sealed learning artifact/response 不复制 ledger、paths 或 page text，只保留安全 manifest-hash receipt。台账不会复制图片字节。
- 小红书真实发布前，需要先单独启动外部 `xiaohongshu-mcp` 服务；PTSM 默认不会自动拉起 `.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64`。
- 浏览器动作保留为人工或条件触发，不应成为默认无人值守 gate。
- psychology carousel 不改变 Topic Radar discovery/routing，也不改变任务完成自动化的完成状态语义；它只在已选 `modern_psychology_post` 的 draft/image/publish 边界内工作。跨领域 minimum `final_content` eval schema 也保持不变。
- 更细的触发策略以 [`docs/operations/task-completion-automation.md`](operations/task-completion-automation.md) 为准。

## Daily Enforcement

- 本地开发:
  `uv run python -m ptsm.bootstrap install-git-hooks --base-ref origin/main`
- 手动预检:
  `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`
- 手动严格预检:
  `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict`
- CI:
  `.github/workflows/harness.yml` 会在 PR 和 `main` push 上运行 `harness-check --strict`
- GitHub 仓库设置:
  在 branch protection 里把 `harness` 设成 required status check；如果要更快失败，也可以把 `docs-sync` 一起设成 required
