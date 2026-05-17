---
title: PTSM Playbooks
status: active
owner: ptsm
last_verified: 2026-05-16
source_of_truth: true
related_paths:
  - src/ptsm/playbooks/registry.py
  - src/ptsm/playbooks/loader.py
  - src/ptsm/playbooks/definitions
  - src/ptsm/evaluations/playbook_contracts.py
  - src/ptsm/accounts/registry.py
  - src/ptsm/accounts/definitions
---

# Playbooks

Playbook 是 PTSM 的业务编排单元。它把领域、平台、技能需求和反思规则绑定成一个可加载定义。

## Current State

- 当前仓库里有七个真实 playbook：`fengkuang_daily_post`、`sushi_poetry_daily_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`modern_psychology_post`、`human_enrichment_daily_post`。
- `wuxia_character_post` 专门输出长篇武侠人物评述（800-1500字），用当代流行文化视角解读金庸古龙人物。默认绑定 `acct-wuxia-local`。
- `ai_tech_daily_post` 专门输出 AI/科技资讯速递，结构化拆解科技进展。默认绑定 `acct-ai-tech-local`。
- `daily_english_post` 是每日英语单词学习内容，陪伴式教育风格。默认绑定 `acct-daily-english-local`。
- `modern_psychology_post` 专门输出现代心理困境观察内容，用第一人称微场景解释心理机制，并要求一个可保存的小工具、例子型评论提示和专业帮助边界；`psychology_safety` 约束诊断、治疗承诺、药物建议和危机处理边界。默认绑定 `acct-psychology-local`。
- `human_enrichment_daily_post` 专门输出人类丰容 / 日常变量实验内容，用一个具体角落、物件或路线写「原本惯性 -> 一个变量 -> 三步清单 -> 轻量结果 -> 评论区例子」。它要求低成本、非医疗化、非购物清单式表达，并通过 `content_review.image_form` 暴露 3:4 封面和轮播形式建议。默认绑定 `acct-enrichment-local`。
- `modern_psychology_post` 的 deterministic fallback 会按场景簇生成不同候选：周日/周一预焦虑、被说想太多后的边界压力、下班后被消息拉回工位、会议尴尬复盘、脑内复盘会、普通回复复盘接龙。这样离线实验候选不会因为同属“反刍思维”而退化成同一个标题/封面。
- `PlaybookRegistry` 支持列出定义、按 id 查询，以及按账号选择。
- `PlaybookDefinition.reflection` 是结构化规则字典，支持必需规则（如 `required_hashtag`、非空 `must_include_phrase`）、可选内容质量规则（如 `title_must_not_equal_any`、`body_must_include_any`、`body_must_not_include_any`）和推荐规则（如 `recommended_phrases`）。推荐词只作为风格提示，不应被 runtime 当成硬门槛。
- `PlaybookLoader` 负责把 markdown 资产读出来供运行时使用，包括 planner、persona 和 reflection 三类文本输入。

## Definition Layout

每个 playbook 定义目录至少应包含：

- `playbook.yaml`
- `planner.md`
- `persona.md`
- `reflection.md`

可选:

- `evaluation.yaml` — 播放本地 evaluation contract 绑定，定义每个 phase 的 node contracts、约束和 invariant

其中：

- `planner.md` 定义任务目标和输出约束
- `persona.md` 定义这个领域账号该像什么样的人在发帖
- `reflection.md` 定义 revise / finalize 阶段的检查标准
- `evaluation.yaml` 引用 shared contract ID 并对每个 node 补充业务约束

`playbook.yaml` 的 `reflection` 字段可以包含非字符串值，例如 `recommended_phrases`、`title_must_not_equal_any`、`body_must_include_any`、`body_must_not_include_any` 列表。runtime reflector 会强制必需项和明确配置的 deterministic quality rules；如果某个 playbook 只是建议使用某类收束词，应该放在推荐字段或 markdown 标准里，避免把所有输出锁成同一个句式。

`fengkuang_daily_post` 的当前 reflection 规则要求 `#发疯文学`，拒绝 `打工人地铁生存实录`、`会议连环暴击实录`、`社畜崩溃边缘实录` 这类泛标题，并要求正文至少出现评论区/接一句/可复制/模板/写在等平台原生机制之一，同时禁止把心理疾病、医院、治疗、用药当笑点。

发疯文学和现代心理学 playbook 的 `playbook.yaml` reflection rules 与 `evaluation.yaml` 都会拦截内容实验操作词泄漏，例如 `想让评论区`、`想存一组`、`变体要求`、`模板要求`、`comment_chain`、`save_tool`、`identity_conflict`。这些词可以出现在 operator 选题记录或实验日志里，但不能进入最终正文。

这两个 XHS 内容质量 playbook 的 `evaluation.yaml` 还配置了 `quality_judges.executor_content_quality`，gate level 为 `required`。显式启用 eval judge 时，失败会计入 `required_failed`；运行时配置 LLM judge backend 时，reflector 会把失败的 `rewrite_hint` 作为下一轮生成反馈。无论 judge 是否通过，最终 artifact 仍会写出 `content_review`，供人工确认后再决定是否发布。

当前定义目录位于 [`src/ptsm/playbooks/definitions/`](../src/ptsm/playbooks/definitions/)。

## Routing Rules

- 账号注册表提供 `account_id -> domain/platform` 基础映射。
- 请求可以显式指定 `playbook_id`，否则按账号域和平台做默认选择。
- `acct-fk-local` 默认落到 `fengkuang_daily_post`，`acct-sushi-local` 默认落到 `sushi_poetry_daily_post`，`acct-daily-english-local` 默认落到 `daily_english_post`，`acct-psychology-local` 默认落到 `modern_psychology_post`，`acct-enrichment-local` 默认落到 `human_enrichment_daily_post`。
- 兼容入口 `run-fengkuang` 仍保留，但多 playbook 场景优先使用通用 `run-playbook`。

## Related Files

- Registry: [`src/ptsm/playbooks/registry.py`](../src/ptsm/playbooks/registry.py)
- Loader: [`src/ptsm/playbooks/loader.py`](../src/ptsm/playbooks/loader.py)
- Accounts: [`src/ptsm/accounts/registry.py`](../src/ptsm/accounts/registry.py)
