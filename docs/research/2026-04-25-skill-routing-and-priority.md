# Skill Routing and Priority Research Notes

Date: 2026-04-25

## Goal

整理当前关于 `agent` 在拥有很多 `skills` 时，如何决定：

1. 哪些信息应该写进 `skill metadata`
2. 哪些决策必须由 `orchestrator` 执行
3. skill 的单一职责边界应该怎么划
4. skill 之间的顺序关系应该怎么表达
5. routing / triggering / sequencing 应该如何评测

重点回答一个工程问题：

> 当系统里 skill 数量持续增长时，如何避免“全靠 description 碰运气”，同时又不把 skill 体系做成一堆僵硬的硬编码优先级。

## Executive Summary

结论先说：

- 截至 `2026-04-25`，主流 skill 体系通常**没有一个跨平台通用的 `priority` 数值字段**。
- 主流框架和产品更常见的做法是：
  - `metadata` 负责 discovery / routing hints
  - `orchestrator` 负责 candidate set 缩减、冲突处理、顺序控制和风险 gating
  - 模型只在一个已经被压缩过的小候选集里做最终选择，或者只负责按需激活
- `description` 仍然是最关键的模型可见触发信号，但它不应该独自承担全部优先级逻辑。
- `metadata` 更适合表达“这个 skill 是什么、何时该用、何时不该用、适用环境是什么”；不适合承载复杂、隐式、跨 skill 的全局优先级体系。
- 真正稳定的“优先级”通常来自**请求级候选集控制**、**显式冲突组**、**phase gating**、**显式顺序约束**和**高风险显式调用策略**，而不是一个魔法权重。
- 如果两个 skill 长期频繁竞争，问题通常不在于“少了 priority”，而在于：
  - skill 边界重叠
  - candidate set 太大
  - metadata 写得像 marketing 文案而不是触发规则

## What Current Industry Practice Actually Looks Like

### 1. OpenAI

`OpenAI Codex Skills` 明确说明：

- skill 可以被显式调用，也可以被隐式调用
- 隐式调用依赖 skill `description`
- 因此 description 需要有清晰 scope 和 boundaries

OpenAI 还强调：

- skill 应该聚焦一个 job
- description 应该说明这个 skill 做什么、什么时候用
- 如果 routing 不稳定，优先迭代 `name / description / examples / negative examples`
- 可以通过 `allow_implicit_invocation: false` 禁止某个 skill 被隐式触发

这说明：

- OpenAI 当前并不把“skill priority 数值字段”作为一等机制
- 更接近的做法是“metadata 可发现 + invocation policy 控制”

### 2. Anthropic

Anthropic 的 skill authoring best practices 说得更直接：

- `description` 是 skill discovery 的关键
- Claude 会在可能有 `100+` skills 的候选空间里用 description 做选择
- description 必须同时包含：
  - 这个 skill 做什么
  - 什么时候用

Anthropic 还明确限制：

- 单个 session 最多 `20` 个 skills

这背后的信号很明确：

- 技能数量太多时，不应该指望模型在一个超大 skill 池里稳定做全量路由
- 系统应该主动控制 skill 暴露面，而不是让 description 独自背锅

### 3. Google ADK

ADK 的 `SkillToolset` 采用 progressive disclosure：

- 启动时只让 agent 看到 skill 的 `name + description`
- 需要时再 `load_skill`
- 更细的 references / assets / scripts 再进一步按需读取

这意味着：

- `metadata` 负责 discovery
- skill 正文和资源负责 execution
- ADK 也没有标准化的 skill priority 字段

### 4. Agent Skills Open Standard

`Agent Skills` 标准 frontmatter 里有：

- `name`
- `description`
- `compatibility`
- `metadata`
- `allowed-tools`

但**没有标准化的 `priority` 字段**。

所以：

- 如果你的系统里想加 `priority: 10`
- 这可以作为**你自己的 runtime 私有扩展**
- 但它不是当前 industry standard，也不应该假设别的 client / runtime 会懂

## First Principle: Split Discovery, Routing, and Activation

skill 选择问题，至少要拆成三层：

1. `Discovery`
   - 当前有哪些 skill 候选
   - 模型能看到哪些 metadata

2. `Routing`
   - 当前请求应该进入哪个 candidate set
   - 哪些 skills 该被排除
   - 哪些冲突必须由系统裁决

3. `Activation`
   - 在缩小后的 candidate set 里，到底激活哪个 skill
   - 激活后读取哪些 instructions / references / scripts

如果这三层不拆开，工程上就会出现两个极端：

- 极端 A：把所有 skill 都摊给模型，然后期待 description 自己解决冲突
- 极端 B：写一堆全局 priority 数值，最后演变成不可维护的硬编码规则

更稳的做法是：

- 先通过 `orchestrator` 把 skill 面缩到一个小候选集
- 再让模型基于 metadata 做选择
- 或者对高风险任务由 orchestrator 直接做确定性选择

## What Should Live In Skill Metadata

metadata 的职责不是“替代 orchestrator”，而是为 routing 和 activation 提供稳定、结构化、可评测的信号。

推荐把 metadata 分成四类。

### 1. Identity

这类字段回答“它是谁”：

- `name`
- `display_name`
- `description`
- `version`
- `owner`
- `maturity`

要求：

- `name` 稳定、唯一、适合被显式调用
- `description` 写成触发规则，而不是产品介绍

### 2. Routing Hints

这类字段回答“什么时候用 / 什么时候不用”：

- `when_to_use`
- `when_not_to_use`
- `trigger_phrases`
- `negative_triggers`
- `domains`
- `user_intents`
- `task_phases`

要求：

- `when_to_use` 必须包含典型任务场景
- `when_not_to_use` 必须显式写出近邻但不该命中的场景
- `trigger_phrases` 用用户真实会说的话，不用内部术语堆砌
- `negative_triggers` 用来压低误触发

### 3. Capability Contract

这类字段回答“它吃什么、吐什么、依赖什么”：

- `inputs.required`
- `inputs.optional`
- `outputs`
- `required_tools`
- `forbidden_tools`
- `network_required`
- `filesystem_required`

要求：

- 输入输出尽量结构化
- 把工具依赖写清楚，便于 orchestrator 先过滤再暴露
- 不要把执行约束埋在正文里让模型自行推断

### 4. Policy and Safety Hints

这类字段回答“它能不能被隐式触发、风险多高”：

- `invocation_mode`
- `allow_implicit_invocation`
- `risk_level`
- `require_user_confirmation`
- `max_auto_invocations_per_thread`

要求：

- 高风险 skill 默认不要允许完全隐式触发
- destructive / external-side-effect 型 skill 应该通过 policy 显式标出来

## What Should Not Be Delegated To Skill Metadata

下面这些事情不要指望只靠 metadata 解决：

- 全局候选集裁剪
- 跨 skill 的复杂冲突仲裁
- 多阶段 workflow 的顺序调度
- 高风险动作的审批和确认
- tenant / account / environment 级别的权限判断
- session 内的 budget 控制
- 线上 fallback / abstain / clarify 策略

这些都应该由 `orchestrator` 执行。

## What The Orchestrator Must Own

### 1. Candidate Set Reduction

`orchestrator` 应该先按这些条件过滤：

- 当前 agent role
- product / tenant / workspace
- platform
- environment
- available tools
- task phase
- user intent
- risk policy

目标不是找到最终 skill，而是把候选集压到一个小范围。

经验上更稳的做法是：

- 优先把候选 skill 控制在 `3-7` 个
- 高风险场景甚至控制到 `1-3` 个

### 2. Conflict Resolution

如果多个 skill 都“看起来合理”，应该优先由 orchestrator 做这些裁决：

- 显式点名 > 隐式触发
- `allow_implicit_invocation: false` 的 skill 不参与隐式选择
- 命中 `when_not_to_use` 或 `negative_triggers` 的 skill 直接淘汰
- 同一 `exclusivity_group` 内一次最多激活一个
- 高风险 skill 只有在满足 policy 时才进入候选集

### 3. Phase Gating

很多 skill 冲突不是内容冲突，而是阶段冲突。

例如：

- `trend-scan` 应只在 `research / planning` 阶段出现
- `copywriting` 应只在 `drafting / rewriting` 阶段出现
- `publisher` 应只在 `execute / release` 阶段出现

如果 phase 不先做 gating，模型会在不该出现的阶段看到太多相似 skills。

### 4. Approval and Side-Effect Control

下面这些 skill 不应该仅靠模型自由决定：

- 发布
- 支付
- 删除
- 写数据库
- 对外网络发送敏感数据

这些场景里，orchestrator 应该做：

- explicit invocation requirement
- user confirmation
- permission checks
- audit logging

### 5. Fallback and Clarification

当两个 skill 分数接近，或者都命中但置信度不够时，orchestrator 应该支持：

- `abstain`
- `needs_clarification`
- `fallback_to_generic_capability`

而不是强迫模型“必须选一个”。

## Single Responsibility For Skills

### Rule

一个 skill 应该只负责一类稳定、可复用的工作，而不是整个宽泛业务流程。

更准确地说：

- 一个 skill 解决“怎么做一类局部工作”
- 而不是“把从 research 到 publish 的全流程都包掉”

### Good Decomposition

更好的 skill 例子：

- `xhs-trend-scan`
- `xhs-copywriting`
- `xhs-hashtagging`
- `publish-content`
- `release-note-draft`
- `incident-summary`

这些 skill 的共同点是：

- 任务边界明确
- 输入输出相对稳定
- 触发条件可描述
- 可以独立评测

### Bad Decomposition

不好的 skill 例子：

- `social-media-super-skill`
- `marketing-all-in-one`
- `do-everything-for-release`
- `general-writer`

这些 skill 的问题是：

- 触发范围过大
- 与其他 skill 高度重叠
- 很难写清楚 when / when not
- 很难做精准 eval

### Design Test

一个 skill 如果要过单一职责检查，至少应该回答清楚：

1. 它只做哪一件局部工作
2. 它最容易和哪一个近邻 skill 混淆
3. 为什么它不应该和那个 skill 合并
4. 用户会用什么真实话语触发它
5. 哪三类 prompt 明确不该触发它

如果答不清楚，通常说明 skill 边界还没收好。

## How To Represent Ordering

最佳实践不是全局 `priority = 100 > 90 > 80`，而是显式表达顺序关系。

### 1. Preferred Order

适合表达“通常谁先谁后”：

- `preferred_before`
- `preferred_after`

例子：

- `trend-scan` `preferred_before: [copywriting]`
- `copywriting` `preferred_before: [publisher]`

这类字段适合 workflow 编排，但不适合作为唯一冲突裁决依据。

### 2. Exclusivity Group

适合表达“这些 skill 同阶段只能选一个”：

- `exclusivity_group: content-research`
- `exclusivity_group: publishing`

例子：

- `trend-scan` 和 `seo-keyword-expansion` 可能都属于 `research`，但同一轮只该激活一个

### 3. Phase Gating

适合表达“这个 skill 只属于哪个阶段”：

- `task_phases: [research]`
- `task_phases: [drafting]`
- `task_phases: [execution]`

phase gating 是比全局 priority 更稳的排序方式，因为它先从时序上消掉大量无意义竞争。

### 4. Invocation Policy

适合表达“这个 skill 是否只能显式调用”：

- `invocation_mode: explicit_only`
- `allow_implicit_invocation: false`

这类字段实际上也是一种顺序控制：

- 先由用户或系统显式决定可以用它
- 再进入实际执行

## Recommended Routing Schema

下面是一个建议的 skill schema。前半部分贴近当前行业常见字段，后半部分是 runtime 可执行的 routing 扩展。

```yaml
---
name: xhs-trend-scan
description: >
  在做小红书选题、内容切口判断、热点借势时使用。
  适用于需要从实时趋势、站内表达、热门讨论点中提炼写作方向的任务。
  不适用于纯文案润色、发布执行、图片生成、数据导出。

when_to_use:
  - 用户要求找热点、找选题、看趋势、找切口
  - 输入里出现“最近在火什么”“选题建议”“借势”“热点”
  - 当前任务阶段是 research 或 planning

when_not_to_use:
  - 任务只是改写现有文案
  - 任务是执行发布或调用发布工具
  - 任务没有研究需求，只要直接产出最终稿

trigger_phrases:
  - 热点
  - 趋势
  - 选题
  - 切口
  - 借势

negative_triggers:
  - 润色
  - 发布
  - 上传
  - 配图

inputs:
  required: [task_text]
  optional: [platform, domain, task_phase]

outputs:
  - topic_candidates
  - trend_summary
  - writing_angles

compatibility:
  platforms: [xiaohongshu]
  environments: [online]
  required_tools: [xhs_search, web_search]
  forbidden_tools: [publish_content]

routing:
  domains: [content_research, social_media]
  user_intents: [trend_scan, topic_discovery]
  task_phases: [research, planning]
  exclusivity_group: content_pipeline
  conflicts_with: [xhs-copywriting, xhs-publisher]
  preferred_before: [xhs-copywriting]
  preferred_after: []

policy:
  allow_implicit_invocation: true
  require_user_confirmation: false
  risk_level: low
---
```

## Recommended Routing Algorithm

推荐把 routing 做成 4 步，而不是一步到位。

### Step 1. Hard Filter

按这些条件做确定性过滤：

- compatibility
- environment
- required tools
- forbidden tools
- policy
- role / tenant / platform

### Step 2. Intent and Phase Filter

按这些条件继续缩小：

- user intent
- task phase
- domain
- invocation mode

### Step 3. Conflict Resolution

规则建议固定化：

- explicit invocation > implicit invocation
- `allow_implicit_invocation: false` 的 skill 不进入隐式候选集
- 命中 `when_not_to_use` 或 `negative_triggers` 直接淘汰
- 同一 `exclusivity_group` 一次最多激活一个
- 若两个 skill 同分，优先 phase 更精确匹配者
- 再同分，优先 maturity 更高或版本被 pin 的

### Step 4. Activation

- 低风险场景：模型在小候选集上做最终选择
- 高风险场景：orchestrator 直接确定 skill 或要求用户确认

## How To Evaluate Skill Routing

skill routing 的评测不能只看“正文效果”，必须把“选对 skill”单独拿出来做。

### 1. Dataset Design

每条 eval case 至少要有：

- `prompt`
- `expected_top1_skill`
- `acceptable_skills`
- `forbidden_skills`
- `task_phase`
- `risk_level`
- `requires_clarification`
- `notes`

还要专门准备 4 类 case：

- 正常命中
- 近邻冲突
- 应该 abstain / clarify
- 高风险不应隐式触发

### 2. Core Metrics

至少跟这些指标：

- `Top-1 accuracy`
- `Top-k coverage`
- `False activation rate`
- `Conflict violation rate`
- `Clarification precision`
- `Abstain recall`
- `Phase-order compliance`
- `Latency before activation`

如果系统支持多步编排，还要额外跟：

- `sequence correctness`
- `side-effect safety violations`

### 3. Error Buckets

最值得长期看的 bucket：

- metadata overlap
- wrong phase
- wrong risk policy
- candidate set too wide
- missing negative trigger
- skill too broad
- should-have-clarified-but-did-not

### 4. Iteration Loop

如果 routing 不稳，优先按这个顺序修：

1. 修 skill 边界
2. 修 `description / when_to_use / when_not_to_use`
3. 补 positive / negative examples
4. 缩小 candidate set
5. 加 phase gating / exclusivity_group
6. 最后才考虑更复杂的排序逻辑

## Recommended Decision Rule

对 `PTSM` 这类系统，更稳妥的策略是：

1. **不要设计全局 skill priority 数值体系**
2. **把 metadata 设计成 routing-friendly**
3. **把真正的优先级控制放到 orchestrator**
4. **通过 phase、conflict group、policy 和 candidate budget 来减少冲突**
5. **只让模型在一个小而干净的 skill surface 里做最终激活**

一句话总结：

> 当前最佳实践不是“给 skill 写一个全局优先级分数”，而是“用 metadata 做发现，用 orchestrator 做裁决，用 eval 持续收边界”。

## Sources

- OpenAI Codex Skills: https://developers.openai.com/codex/skills
- OpenAI Codex Best Practices: https://developers.openai.com/codex/learn/best-practices
- OpenAI Skills in API, operational best practices: https://developers.openai.com/cookbook/examples/skills_in_api#operational-best-practices
- Anthropic Agent Skills overview: https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview
- Anthropic skill authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Anthropic managed agents skills: https://platform.claude.com/docs/en/managed-agents/skills
- Google ADK skills: https://google.github.io/adk-docs/skills/
- Google Developers Blog, ADK agents with skills: https://developers.googleblog.com/developers-guide-to-building-adk-agents-with-skills/
- Agent Skills specification: https://agentskills.io/specification
