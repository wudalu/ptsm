# Agent User Intent Recognition Research Notes

Date: 2026-03-18

## Goal

研究当用户输入一个自由文本 requirement 时，agent 如何更稳地识别用户真实意图，并总结当前较靠谱的 industry practice、可提升准确率的手段，以及这些结论如何映射到 `PTSM` 当前 runtime。

## First Principle

“Intent recognition” 在 agent 系统里通常不是一个单点分类器问题，而是一个三层问题：

1. `Task / route intent`
   - 用户想让系统做什么大类事情。
   - 例如：生成内容、发布内容、查状态、修改账号、登录、分析效果。

2. `Execution intent / slots`
   - 在该任务里，用户真正要执行什么动作，还缺哪些参数。
   - 例如：平台、账号、领域、语气、是否发布、是否仅草稿。

3. `Ambiguity / out-of-scope handling`
   - 系统是否足够确定。
   - 如果不确定，是进入澄清、兜底路由，还是拒绝。

如果这三层不拆开，工程上常见问题是：

- 把所有问题都扔给一个大模型直接“猜”意图
- 没有 unknown / OOS 检测
- 缺参数时不追问，直接执行错误动作
- 表面离线准确率很高，但真实线上误判很多

## What Current Best Practice Looks Like

### 1. Use routing, not a single classifier

当前更稳的做法不是“一个 prompt 直接输出 intent”，而是做一个轻量 routing layer，在主 agent 前先做：

- 输入归一化
- 候选 intent 召回
- 最终判别
- 置信度判断
- 低置信度澄清

实证和工程资料都在收敛到这个方向：

- `Voiceflow` 的实测做法是先用 encoder NLU 找 top-10 candidate intents，再让 LLM 做最终分类，而不是直接全量分类。
- `Arora et al., EMNLP Industry 2024` 提出 hybrid system，用 uncertainty-based routing 结合 sentence transformer 和 LLM，在接近原生 LLM 准确率的情况下把延迟降了约 50%。
- `vLLM Semantic Router` 这类新一代 routing 产品也在强调 signal fusion，而不是只靠单一文本分类。

### 2. Low confidence should trigger clarification, not forced classification

近两年的论文非常清楚地支持这一点：

- `CICC` 把 classifier 的不确定性转成澄清问题，并且支持 OOS 检测。
- `AGENT-CQ` 说明高质量 clarifying questions 可以显著改善 query understanding 和后续 retrieval 效果。

这意味着：

- 真正提升准确率的关键，不只是把 top-1 intent 判得更准
- 更重要的是知道“现在还不该判”

### 3. Structured outputs are now standard for intent parsing

在 LLM 路由和意图识别场景里，当前工程 best practice 基本都会把模型输出限制成结构化 schema，而不是解析自由文本。

原因：

- 避免 label 漂移
- 避免遗漏字段
- 便于记录置信度、候选意图、缺失参数和澄清问题
- 方便做离线评估和线上观测

### 4. OOS / unknown detection is not optional

如果系统只能在一组已知标签里强制选一个，那线上误判会被系统性放大。

资料里反复出现两个结论：

- 未知意图检测决定了系统真实体验上限
- 意图标签空间越大、范围越宽，LLM 的 OOS 表现越不稳定

因此 production 系统通常至少要有：

- `unknown`
- `needs_clarification`
- `handoff / fallback`

这几个显式路径。

## Techniques That Improve Intent Accuracy

### 1. Separate candidate retrieval from final decision

推荐架构：

1. embedding / encoder 先召回 top-k intents
2. LLM 只在 top-k 里做最终判断
3. 输出 `predicted_intent + confidence + runner_up + reason + missing_slots`

优点：

- 降低 label space
- 降低 prompt 长度
- 提升稳定性
- 更容易做解释和调试

这个方法尤其适合你们未来从“固定 playbook”扩展到“多种用户需求入口”的场景。

### 2. Make intent labels operational, not semantic poetry

意图标签不要写成抽象概念，应该写成系统动作。

差的例子：

- `content`
- `social`
- `help`

更好的例子：

- `generate_draft`
- `publish_existing_draft`
- `rerun_failed_publish`
- `show_account_status`
- `login_xhs`
- `explain_playbook_capability`

标签越接近真实执行路径，路由越稳，澄清也越自然。

### 3. Give each intent a strong description and near-miss examples

`Voiceflow` 的实验说明，intent description 的写法会影响分类效果；他们用的是：

- encoder 召回 top candidate
- LLM 根据 intent description 最终判别

这说明 production 里应该为每个 intent 准备：

- 一句话描述
- 典型正例
- 容易混淆的反例
- 必须具备的 slot
- 不能命中的边界

对于 agent 来说，这比只给 label 名字有效得多。

### 4. Treat missing parameters as a first-class outcome

很多 requirement 不是“意图不清”，而是“意图清楚，但执行参数不全”。

例如：

- “帮我发一下今天的小红书”
- 意图可能很清楚是 `publish_content`
- 但缺账号、缺内容来源、缺可见性、缺平台上下文

所以建议把结果分成三类：

- `intent_resolved`
- `intent_resolved_but_missing_slots`
- `intent_uncertain`

前两类都不应该落到同一种追问里。

### 5. Ask clarifying questions only when they maximize information gain

追问不是越多越好。最佳实践是一次只问一个最能消除歧义的问题。

优先问：

- 能直接区分 top-2 / top-3 候选意图的问题
- 能解锁执行所需必填 slot 的问题

不优先问：

- 用户已经暗含给出的信息
- 对执行没有影响的偏好问题
- 一次问多个维度

一个常见模式：

- top-1 `generate_draft`
- top-2 `publish_content`
- 系统先问：“你是想先生成草稿，还是直接发布现有内容？”

### 6. Calibrate thresholds and support abstention

不要让模型“必须给答案”。

推荐保留：

- `top1_score`
- `margin = top1 - top2`
- `abstain_threshold`
- `clarify_threshold`

简单规则通常就能明显改善体验：

- 高置信度且 margin 足够大：直接进入执行
- 中置信度：问一个澄清问题
- 低置信度或命中 OOS：进入 fallback

### 7. Use small models or encoders for first-pass intent work

并不是所有流量都应该直接进入大模型 agent。

更常见的分层是：

- 编码器 / 小模型做 first-pass classification 或 candidate retrieval
- 大模型只处理复杂判别、解释和澄清

这在成本、延迟和稳定性上都更有优势。`EMNLP 2024` 的 hybrid 结果也支持这条路线。

### 8. Continuously evaluate on real traffic and active-error buckets

intent recognition 最容易犯的错误，是只在离线标注集上看平均准确率。

更实用的做法是长期跟踪这些 bucket：

- top-1 错判
- 本应澄清但直接执行
- 本应执行但进入澄清
- OOS 被错判为已知意图
- slot 缺失识别失败
- 用户改口后的最终真实意图

如果后面要做 prompt 优化或小模型蒸馏，这批样本会是最有价值的数据。

## A Practical Architecture For PTSM

基于当前代码，`PTSM` 现在更像“已知 playbook 的执行引擎”，还没有独立的自由输入理解层。

当前关键路径大致是：

- `run_fengkuang_playbook(...)`
- `build_fengkuang_workflow(...)`
- `ingest_request -> select_playbook -> load_assets -> draft_content -> reflect_content`

如果要支持“用户输入一个 requirement，系统自己判断该怎么做”，建议在 `ingest_request` 之前增加一层 `intent understanding`.

### Recommended flow

```text
user requirement
  -> normalize_request
  -> retrieve_candidate_intents
  -> llm_structured_intent_parse
  -> confidence_gate
      -> resolved: select playbook / tool / use case
      -> missing slots: ask targeted question
      -> uncertain: ask disambiguation question
      -> oos: fallback / refuse / handoff
```

### Recommended output schema

```json
{
  "intent": "publish_content",
  "confidence": 0.82,
  "candidate_intents": [
    {"name": "publish_content", "score": 0.82},
    {"name": "generate_draft", "score": 0.61}
  ],
  "required_slots": ["platform", "account_id", "content_source"],
  "filled_slots": {
    "platform": "xiaohongshu"
  },
  "missing_slots": ["account_id", "content_source"],
  "needs_clarification": true,
  "clarification_question": "你是想直接发布已有内容，还是先让我生成一版草稿？",
  "reason": "用户提到“发一下”，但没有提供现成内容，且系统检测到 draft/publish 两种高相似候选。"
}
```

### Intent layer candidates for PTSM

第一版不要建太多标签，建议先做 operational intents：

- `generate_draft`
- `publish_content`
- `generate_and_publish`
- `rerun_publish`
- `login_account`
- `show_account_status`
- `list_playbooks`
- `explain_capability`
- `modify_account_config`
- `unknown`

### Clarification strategy for PTSM

把追问分成两类：

1. `Disambiguation`
   - 例子：“你是想生成草稿，还是直接发布？”

2. `Slot elicitation`
   - 例子：“你要发到哪个账号？”

不要把这两类问题混在一条消息里。

## What I Would Not Do

不建议一开始就做这些事情：

- 直接让主 agent 自由推理所有 requirement，再自己决定 route
- 一上来做几十个 intent label
- 没有 `unknown` 还强制 top-1
- 用大量规则 if/else 取代数据驱动路由
- 把“分类错了”和“参数没补齐”混为一谈
- 没有线上评测就反复调 prompt

## Suggested Near-Term Plan

### Phase 1

先做可观测的 intent parser skeleton：

- 定义 8 到 10 个 operational intents
- 为每个 intent 写 description / examples / near-misses
- 用结构化输出产出 `intent + confidence + missing_slots + clarification_question`
- 先不接主 agent，只做 dry-run 评估

### Phase 2

增加 hybrid routing：

- embedding candidate retrieval
- top-k intent shortlist
- LLM final parse
- threshold + abstain

### Phase 3

增加闭环学习：

- 记录用户 requirement
- 记录系统初判
- 记录是否触发澄清
- 记录用户澄清后的真实意图
- 周期性回放 hardest cases

## Sources

- OpenAI Structured Outputs
  - https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Distillation Guide
  - https://platform.openai.com/docs/guides/distillation
- Voiceflow: 5 tips to optimize your LLM intent classification prompts
  - https://www.voiceflow.com/pathways/5-tips-to-optimize-your-llm-intent-classification-prompts
- Floris den Hengst et al., 2024, Conformal Intent Classification and Clarification for Fast and Accurate Intent Recognition
  - https://aclanthology.org/2024.findings-naacl.156/
- Clemencia Siro et al., 2024, AGENT-CQ: Automatic Generation and Evaluation of Clarifying Questions for Conversational Search with LLMs
  - https://arxiv.org/abs/2410.19692
- Gaurav Arora et al., 2024, Intent Detection in the Age of LLMs
  - https://aclanthology.org/2024.emnlp-industry.114/
- vLLM Semantic Router docs
  - https://vllm-semantic-router.com/docs/intro/

## Source-To-Claim Mapping

- “结构化输出是当前工程 best practice” 主要来自 OpenAI Structured Outputs 文档，外加当前主流 agent stack 的工程趋势判断。
- “hybrid routing 比纯大模型更稳更省” 主要来自 `Intent Detection in the Age of LLMs` 和 Voiceflow 的实证，外加我对 production agent 架构的推断。
- “低置信度时应澄清而不是强判” 主要来自 `CICC` 和 `AGENT-CQ`。
- “多信号路由会成为主流” 主要来自 vLLM Semantic Router 的系统设计文档，属于对 industry direction 的判断，不等同于已经成为唯一标准。
