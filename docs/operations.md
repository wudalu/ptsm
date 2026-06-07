---
title: PTSM Operations
status: active
owner: ptsm
last_verified: 2026-06-04
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
  - src/ptsm/application/models.py
  - src/ptsm/interfaces/cli/main.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/analyze_xhs_patterns.py
  - src/ptsm/application/use_cases/xhs_domain_opportunity.py
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
- `uv run python -m ptsm.bootstrap run-playbook --scene "Google发布Gemini 3模型" --account-id acct-ai-tech-local --playbook-id ai_tech_daily_post`
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
- `uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --scene "Google 发布 Gemini 3，想写普通人能懂的 AI 工具变化" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --scene "想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id daily_english_post --account-id acct-daily-english-local --scene "学一个表示坚持的高级词汇，想配真实职场例句" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id world_cup_daily_post --account-id acct-world-cup-local --scene "阿根廷和法国决赛前，想写普通球迷看球清单" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap guide-post --playbook-id reddit_curation_daily_post --account-id acct-reddit-curation-local --scene "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度" --non-interactive --format json`
- `uv run python -m ptsm.bootstrap run-playbook --caller openclaw --scene "他3小时没回消息，我已经想好分手后猫归谁了" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --caller openclaw --guidance-ack --scene "他3小时没回消息，我已经想好分手后猫归谁了" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --scene "凌晨两点，我还在改白天会议那句话" --account-id acct-psychology-local --playbook-id modern_psychology_post`
- `uv run python -m ptsm.bootstrap run-playbook --scene "办公室下班后还是很紧绷，想写一个睡眠恢复和轻养生的5分钟下班信号" --account-id acct-psychology-local --playbook-id modern_psychology_post --eval --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-playbook --scene "想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出" --account-id acct-ai-tech-local --playbook-id ai_tech_daily_post --publish-mode dry-run`
- `uv run python -m ptsm.bootstrap run-fengkuang --fresh-topic-research --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap run-playbook --fresh-topic-research --account-id acct-psychology-local --playbook-id modern_psychology_post`
- `uv run python -m ptsm.bootstrap run-fengkuang --fresh-topic-research --account-id acct-fk-local --auto-generate-image --publish-mode mcp-real --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "公开" --wait-for-publish-status`
- `uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap collect-xhs-patterns --lane human_enrichment --keywords "人类丰容,家的丰容计划,低成本改造,钩织,拼豆" --sample-limit-per-keyword 8`
- `uv run python -m ptsm.bootstrap analyze-xhs-patterns --sample-path outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json --lane human_enrichment`
- `uv run python -m ptsm.bootstrap run-playbook --scene "把书桌改成十分钟手作角" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --format-pattern-path outputs/artifacts/xhs-pattern-library/current.json`

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
- `xhs-record-metrics` / `xhs-metrics-report` 是内容实验的本地指标回收入口。前者把已发布帖子的 `2h`、`24h` 或 `72h` 浏览、点赞、收藏、评论、分享追加到 `outputs/artifacts/xhs-post-metrics/metrics.jsonl`；后者按方向、封面样式、checkpoint、账号或 playbook 聚合。心理学增长实验优先用 `--playbook-id modern_psychology_post --checkpoint 24h --group-by topic_direction_id` 比较 `sleep_recovery_shutdown_card`、`relationship_mixed_signal_camp_vote`、`social_battery_cancel_plan_boundary`、`after_hours_message_body_alarm` 等方向。少于 3 条记录的 group 只作为早期信号，不应直接改 prompt。
- `--fresh-topic-research` 通过 topic-radar 先扫描平台热点，交互式让用户选题后再生成内容，此时 `--scene` 可选。
- `collect-xhs-patterns` / `analyze-xhs-patterns` 是周期采集和格式沉淀入口。普通 `run-playbook` 默认只读取本地 pattern snapshot，不会每次发帖都检索实时高互动帖子；需要实验特定 snapshot 时，用 `--format-pattern-path` 覆盖。
- 2026-06-04 的正文人味优化尝试用 `collect-xhs-patterns --lane body_human_voice --keywords "活人感,小红书文案,发疯文学,情绪管理,人类丰容"` 做 bounded live XHS 抓取，但当前 MCP `search_feeds` 对 `活人感` / `小红书文案` 返回 HTTP 500，落盘 artifact `outputs/artifacts/xhs-body-human-voice/samples-2026-06-04.json` 的 `sample_count` 为 0。因此这次策略只把 2026-05-15 / 2026-05-17 本地真实样本和公开趋势摘要作为依据，不声称拿到了 2026-06-04 热门帖样本。后续要刷新热门帖，先恢复 MCP 登录/健康，再重跑 bounded `collect-xhs-patterns`。
- `reddit_curation_daily_post` 会在 `reddit_discussion_scan` skill 激活时尝试读取 Reddit 英文讨论作为内部素材。按 Reddit Responsible Builder Policy，读取 Reddit API 前需要为该用途取得 explicit approval，并保持透明、限量、只读、不规避限制、不做 Reddit 数据商业化或 AI 训练。配置已获批 app 的 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT` 后会用 OAuth 形成真实最新 Reddit runtime context；如果 app 创建受验证码阻塞，可先设置 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT`，用 Reddit public `.json` 页面低频只读扫描。未配置时 dry-run 会完成但上下文标记为 `missing_credentials`。读者可见成稿只呈现中文热点帖，不暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL。
- `run-playbook` 是多 playbook 的通用入口；`run-fengkuang` 只保留给已有发疯文学兼容脚本和习惯命令。
- 做 XHS persona 或热梗映射回归时，优先用 dry-run 加 `--eval` 检查 artifact：标题应在 22 字以内，有具体物件/关系/场景钩子，并出现冲突、反差或戏剧张力 cue，同时避开 `日常`、`实录`、`干货分享` 这类泛标题；正文应按 `首屏钩子 -> 领域要素 -> 可保存单元 -> 评论交接` 组织并落在对应 playbook 的长度带内，还应有本领域现场锚点和真人视角，例如时间、物件、关系、一句原话、材料、路线、动作，以及 `我` / `你` / `我们` / `今天` / `那一秒` 这类人称或时间地点锚点。现代心理学还要额外检查标题不出现心理机制名或 `不是你` 破梗，正文控制在 260-580 字，用一句轻机制服务场景，用 `哪派`、`A.` / `B.` 或 `____` 这类认领入口替代泛泛问经历。eval 会通过 `title_max_chars`、`title_must_include_tension_any`、`title_must_not_include_any`、body length band、`body_must_include_scene_signal`、`body_scene_signal_any`、`body_human_anchor_any` 和 `combined_must_not_include_any` 拦截过长/平淡标题、泛标题、过长/过短正文、缺少现场/真人锚点的正文、`首先`、`其次`、`综上`、`本文`、`作为AI` 等模板化或元叙事表达，也会拦截 `可复制疯话`、`可收藏小结`、`可保存单元`、`评论交接` 等读者可见的内部功能标签。
- `guide-post` 是小红书发帖前的只读选题向导：支持当前九个 playbook：`modern_psychology_post`、`fengkuang_daily_post`、`human_enrichment_daily_post`、`classic_poetry_quote_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。默认走对话式引导；脚本场景用 `--non-interactive` 输出 JSON。JSON 和 Markdown 都包含场景相关的 4 个 `topic_guidance.directions`，把本地热点/爆点机制产品化为用户可选方向；输出带 `selection_policy == "dynamic_scene_diversity_rerank"`、`open_direction_ids`、兼容字段 `open_direction_id` 和 `direction_type_counts`。selector 从 curated 候选和多个 PTSM 本地组合的 `open_scene` 候选中动态选择方向，scene 关键词只来自用户输入，lane affinity 只来自选题 lane，并用 diversity family、direction source type 和 open-scene mechanism 避免不同场景只得到同一组固定锚点。每个方向带 `direction_type`、`scene_fit`、`trend_signal`、`viral_hook`、适合场景、内容角度、保存工具、评论提示、避坑和 `format_recommendation`；格式建议包含 `format_archetype`、`cover_role`、`body_shape`、`visual_evidence_need` 和 `avoid_format`，用于确认方向后的封面/正文/评论结构约束。输出还带 `topic_guidance.image_recommendation`，用于用户确认方向后选择图片方式：本地截图会给出 `--local-image-style wechat_chat|iphone_notes|note_card`，provider 图会给出 `--auto-generate-image`、`provider=bailian` 和 `model=qwen-image-2.0-pro`。输出不包含 research 文件路径、原始来源说明、URL 或 provenance。普通 `guide-post` 不默认运行 live XHS / topic-radar 扫描。真正生成和发布仍走 `run-playbook`；带 `--topic-direction-id <chosen id>` 时，运行时会把该方向的公开 payload 注入 `topic_selection.direction` 和 drafting runtime context。
- 对 `想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出` 这类 AI tech 场景，`guide-post` 应返回 `提示词构建 / 好用 prompt`、`ai_prompt_context_card` 和可直接复制 prompt 成品 + `任务 / 背景 / 输出格式 / 反例` 拆解工具卡，封面推荐 `--local-image-style iphone_notes`。这只是 `ai_tech_daily_post` 的 AI 工作流子线；2026-06-04 的 live opportunity scan 因 XHS MCP 工具不可用没有真实样本，不能称为新领域趋势排名。
- 古诗词金句 `guide-post` 不把诗词 scene 默认解释为苏轼或怀民。泛古诗词/经典诗句场景应返回唐诗金句、宋词清醒、月亮乡愁、山水松弛、杜甫现实感、节气四季等可选方向；明确提到苏轼、定风波、赤壁或怀民时，苏轼方向才作为候选子线出现。默认标签是 `#古诗词`，不强制 `#苏轼`。
- 心理学 `guide-post` 保留更丰富的六步 brief：先问具体场景，再建议心理学 lane、机制、非诊断化重构、可保存动作、角色/阵营/填空式评论提示和低密度封面；生成时机制用于服务场景，不应前置成标题破梗。非心理学交互只问具体场景、可选 lane 和评论提示覆盖，避免把心理学机制问题套到其他领域。
- 对 `他3小时没回消息，我已经想好分手后猫归谁了` 这类亲密关系等待消息场景，心理学 `guide-post` 应返回 `亲密关系 / 不确定感` 和 `事实 / 脑补 / 我需要什么`，封面推荐 `--local-image-style iphone_notes`；不要把它作为职场协作式消息边界回复来生成。
- 对 `睡眠恢复和轻养生很火，想写办公室下班后的5分钟恢复` 这类增长子线场景，心理学 `guide-post` 应返回 `睡眠恢复 / 轻养生`、`sleep_recovery_shutdown_card` 和 `5 分钟下班信号`，封面推荐 `--local-image-style iphone_notes`；这是 `modern_psychology_post` 的子线实验，不是新养生 playbook，也不能写成医疗、营养或治疗建议。2026-06-02 的 live opportunity scan 因 MCP 缺少 `search_feeds` 没有真实样本，不能把这条子线称为已验证趋势排名。
- 对 `对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队` 这类亲密关系场景，心理学 `guide-post` 应返回 `relationship_mixed_signal_camp_vote`、`事实 / 信号 / 我要不要问清楚` 和 A/B 阵营评论入口；不要把它写成职场处理时间或优先级。
- 对 `约好的局临时不想去了，怕扫兴又很累，想写社交电量边界` 这类社交耗竭场景，心理学 `guide-post` 应返回 `social_battery_cancel_plan_boundary`、`取消局三句` 和 A/B 角色认领；不要鼓励失联或羞辱社交。
- 对 `领导18:57发来一句在吗，下班后身体被消息拉回工位` 这类下班消息场景，心理学 `guide-post` 应返回 `after_hours_message_body_alarm`、`下班消息三步` 和 A/B/C 评论入口；这是心理学的职场低控制感/身体警报表达，不是发疯文学。
- OpenClaw 心理学集成使用 `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` 作为薄 wrapper：先调用 `guide-post` 展示 `topic_guidance.directions`、`direction_type`、`scene_fit` 和 `format_recommendation`，用户确认方向后再调用 `run-playbook --caller openclaw --guidance-ack --topic-direction-id <chosen id>`。如果 OpenClaw 直接调用 `run-playbook --caller openclaw` 生成 `modern_psychology_post` 且没有 `--guidance-ack`，PTSM 会返回 `topic_guidance_required`，不会启动 workflow、写 run 或发布。
- OpenClaw 非心理学 XHS 集成使用 `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`。该 wrapper 自动把发疯文学、人类丰容、古诗词金句、武侠人物、AI科技、每日英语、世界杯和 Reddit英文讨论转译意图映射到对应 playbook；意图模糊时先问一个短澄清问题；方向确认后展示 PTSM 返回的 `format_recommendation` 和 `topic_guidance.image_recommendation`，再 dry-run 生成，并把确认的方向 id 作为 `--topic-direction-id` 传给 `run-playbook`。如果用户更换场景，wrapper 必须重新调用 `guide-post`，不要沿用上一轮方向。wrapper 只能展示 PTSM-returned `open_scene` 方向和 PTSM-returned 格式/图片建议，不能自己发明开放方向、格式或图片策略。非心理学没有 runtime hard preflight gate，因此 `run-playbook --caller openclaw` 不会因为缺少非心理学 guidance ack 而被拒绝。
- OpenClaw/Codex 领域机会分析使用 `integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md` 作为薄 wrapper：当用户想比较小红书领域、寻找新增 PTSM 领域或评估 playbook 覆盖缺口时，先调用 `xhs-domain-opportunity` CLI 生成 JSON/Markdown brief，再按 `existing_playbook_fit`、`sublane_first`、`new_domain_candidate` 给下一步建议。该 wrapper 不生成、不发布、不复制 PTSM scoring，也不展示原始 feed id/token。
- `run-fengkuang --auto-generate-image` 会在缺少 `--publish-image-path` 时尝试调用已配置的图片后端生成封面；即梦配置优先于百炼配置，真实发布模式下默认也会尝试自动补图。PTSM 生成图会请求源头不加 provider 水印，并在 artifact 的 `image_generation.watermark_policy` 里记录 `no_provider_watermark` 和具体 provider controls；本地 renderer 还会记录 `image_generation.provenance.source == "ptsm_local_renderer"`。
- `--no-auto-generate-image` 可以关闭自动补图；`--publish-image-path` 使用手动图片；`--local-image-style note_card|iphone_notes|wechat_chat` 可以主动选择本地截图式封面，即使外部图片 provider 已配置也生效。当前 `wechat_chat` 是内容区聊天转录封面，不绘制手机头部、底部输入栏或头像；正文或 `final_content.image_plan` 中的 `theme`、`chat_title`、`chat_times`、`golden_line` 等本地渲染参数会进入 renderer payload 和 artifact 证据。缺省本地时间会按 scene 明确时间或 payload hash 确定性变化，generic 对话发言人会补模拟昵称。
- 真实发布会按图片来源执行去水印：PTSM 本地 renderer 图片不画水印，也跳过 `watermark_removal` 后处理；provider/LLM 生成图和手动 `--publish-image-path` 图片仍会经过防御性去水印。dry-run 图片实验仍可用 `WATERMARK_REMOVAL_ENABLED=true` 选择是否预览 provider/manual 图片清理。
- 每次自动生成图片都会追加本地资产台账 `outputs/artifacts/generated-image-assets/assets.jsonl`，记录 image path、provider/style/model、playbook/account、artifact、image_plan、provenance source 和 prompt hash，用于后续筛选可复用图片；不会自动复制或提交图片文件。
- 小红书真实发布前，需要先单独启动外部 `xiaohongshu-mcp` 服务；PTSM 默认不会自动拉起 `.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64`。
- 浏览器动作保留为人工或条件触发，不应成为默认无人值守 gate。
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
