# Evaluation System Best Practices Research Notes

Date: 2026-05-07

## Goal

调研 LLM / agent 应用的 evaluation system 应该如何设计，重点回答：

1. 整个执行流程每一步产物是否都应该被评估。
2. rule、contract、LLM judge 三类 evaluator 如何分层。
3. offline eval、online eval、human review、production trace mining 应该如何组合。
4. PTSM 当前 harness / observability 能借鉴什么，不应该直接照搬什么。

## Current PTSM Baseline

PTSM 现在已经有可用但偏轻量的 harness surface：

- runtime 主链路是 `ingest -> planner -> executor -> reflector -> finalize`，再由 `run_playbook()` 编排 image / publish / post-publish checks。
- artifact 和 run store 已经持久化运行结果、事件、skill activation metadata、runtime skill context metadata。
- `harness-evals` 已经聚合 run completion、event status、plan-run evidence、per-skill completion rate。
- `harness-report` 已经组合 doctor、gc、harness-evals，并能作为本地 gate。

缺口也很明确：

- 没有每个 runtime step 的结构化 eval result。
- 没有把 node input / output / artifact slice 建模成可评分 span。
- 没有 task-specific dataset 或 golden cases。
- 没有 rule / contract / LLM judge 的统一 evaluator registry。
- 没有 human review 校准 judge 的闭环。
- 没有把 failed production runs 自动沉淀成 regression dataset。

## Industry Pattern Summary

主流实践正在收敛到一个共同模型：

```text
trace/span + dataset example + evaluator/scorer + score artifact + aggregate report
```

不同产品命名不同，但概念高度相似：

- OpenAI: evals、datasets、graders、trace grading、agent workflow evals。
- LangSmith: offline evaluation、online evaluation、datasets、experiments、LLM-as-judge、code evaluators、summary evaluators。
- Phoenix: traces/spans、LLM evaluators、code evaluators、human labels、OpenTelemetry/OpenInference instrumentation。
- Braintrust: datasets、tasks、scorers、experiments、logs、human review。
- Ragas / DeepEval: task-specific metrics for RAG, tool use, agent goal completion, faithfulness, contextual precision/recall, tool correctness.
- Google Vertex AI: pointwise / pairwise model-based metrics, computation-based metrics, metric prompt templates, human rating calibration for judge models.
- Anthropic: define success criteria first, build task-specific empirical evals, include edge cases, automate when possible, and quantify qualitative criteria with rubrics.

## Best Practice 1: Eval-Driven Development

OpenAI and Anthropic both emphasize先定义成功标准，再写/改系统。对 agent 系统来说，这意味着：

- 每个 workflow change 都应该明确它想改善什么 metric。
- 每个 prompt/model/skill/playbook 改动都应该有可以重复跑的数据集。
- 不能只看一次 manual run 的输出感觉。
- production logs 应该被持续挖掘成 eval cases。

对 PTSM 的含义：

- 每个 playbook 应该有 `evaluation_profile`，声明必须满足的内容、风格、格式、平台、发布安全约束。
- 每次新增领域或 skill，不只加 prompt，还要加最小 eval cases。
- `harness-check` 可以先 gate deterministic rule/contract eval；LLM judge eval 先做 warning/report，稳定后再升 gate。

## Best Practice 2: Offline and Online Evals Both Matter

LangSmith、Phoenix、Braintrust 都把 evaluation 分成两条线：

- Offline eval: 上线前用 curated dataset / historical traces 跑 experiments，适合 CI、regression、prompt/model 比较。
- Online eval: 线上真实流量或本地真实 run 后评分，适合 monitoring、异常发现、dataset curation。

对 PTSM 的含义：

- Offline: `ptsm eval-run --suite <suite>` 对一组 fixtures / golden cases 跑 deterministic backend 或固定 judge，输出可比较 report。
- Online/local: 每次 `run-playbook` 完成后可以异步或显式 `ptsm eval-artifact --artifact ...`，把评分写到 artifact/run summary。
- Dataset flywheel: `harness-evals` 中失败或低分 run 可以进入 `ptsm eval-candidates`，人工确认后进入 `eval_datasets/`。

## Best Practice 3: Evaluate the Trace, Not Only the Final Output

OpenAI agent eval docs 和 Phoenix/Braintrust traces 都强调：agent workflow 的问题常常出现在中间步骤，而不是最终文本。

常见 agent eval target：

- final response: 最终答案或最终内容是否满足任务。
- single step: 某一步是否选对 tool / skill / context。
- trajectory: 整条执行路径是否符合预期，包括 tool calls、handoff、guardrails、retry。
- artifact slice: 某个持久化 artifact 字段是否符合 schema 或业务约束。

对 PTSM 的含义：

- `planner` 要评估 playbook selection、required skills、runtime context presence。
- `executor` 要评估 structured content schema、标题/正文/hashtags 基本约束。
- `reflector` 要评估是否正确 retry/finalize/fail，而不是只看最终状态。
- `finalize` 要评估 artifact completeness。
- image / publish 要评估外部副作用前后的 safety contract 和 metadata completeness。

## Best Practice 4: Use Rule, Contract, and LLM Judge Together

业界一致的分层是：

### Rule Evaluators

适合确定性、低成本、高置信度检查：

- JSON parse / schema required fields。
- title length、hashtags count、empty body。
- publish visibility policy。
- artifact file exists。
- generated image path exists。
- no external publish in dry-run。
- exact / regex / string presence。

这类 evaluator 应该优先进入 CI 和 local gate。

### Contract Evaluators

适合检查系统内部约定和跨步骤输入输出：

- node input/output shape。
- playbook declares required skills and those skills are activated。
- runtime context provider has traceable source。
- publish result includes identifiers when available。
- side-effect ledger idempotency key exists before external write。
- artifact schema version is supported。

这类 evaluator 是 PTSM 最缺的一层，应该成为新 evaluation system 的核心。

### Where Contracts Should Live

对 PTSM 来说，canonical contract 应该统一放在 `shared_contracts/evaluation/`，同时和 playbook 结合使用。关键区别是：`shared_contracts` 定义共享 schema/catalog，playbook-local 文件只做绑定、覆盖和业务约束。

推荐分层：

- `shared_contracts/evaluation/` 是统一 contract catalog 和 schema template 的来源，负责跨 playbook 的通用结构，例如 `EvalTarget`、`EvalResult`、`final_content.v1`、`artifact.v1`、run summary schema。
- `playbook.yaml` 继续负责 playbook identity、routing、required skills、reflection 这类高频运行时定义。
- `playbook_dir/evaluation.yaml` 负责把这个 playbook 的执行节点绑定到共享 contract ID，并声明业务约束，例如 planner 必须激活哪些 skills、executor 的 `final_content.v1` 需要哪些字段和风格约束、reflector 允许哪些 decision、final artifact 必须包含哪些业务字段。
- `src/ptsm/evaluations/*` 负责 evaluator 实现，读取 playbook-local bindings 和 shared schemas 后执行 rule / contract / LLM judge。

这个分层的理由：

- shared contract catalog 保证 evaluator、artifact、run summary、content shape 这些通用结构不会在多个 playbook 中漂移。
- playbook 最知道自己的业务产物标准，例如发疯文学、小红书 AI 资讯、每日英语学习的内容结构和风格都不同。
- runtime/shared contract 才知道系统级 invariant，例如 run/artifact link、skill metadata traceability、eval result schema。
- evaluator suite 负责把 contract 变成评分和 gate，不应该让 playbook 直接承担执行逻辑。
- implementation 之前应该先有 contract catalog，列出每类 contract 的 owner、scope、enforcement、gate level 和 schema template；否则 evaluator 很容易变成分散的 ad hoc checks。

反模式：

- 不要把每个节点的所有 contract 都塞进 `playbook.yaml`，否则 playbook 会从业务定义膨胀成执行引擎配置。
- 不要让 playbook-local 文件重新定义 shared schema；它应该引用 `shared_contracts/evaluation/` 的 contract ID，再补充业务约束。
- 不要只做全局 contract，否则不同领域的业务产物会被迫共享过粗的标准。
- 不要让 LLM judge prompt 直接成为 contract 的唯一来源；可执行 contract 需要结构化字段。

### LLM Judge Evaluators

适合主观或语义型检查：

- 账号人设是否一致。
- 标题是否吸引平台用户。
- 正文是否符合领域风格。
- 事实是否被引用来源支持。
- 反思 feedback 是否真正被修复。
- 英语学习内容是否教学上清楚。
- AI tech 内容是否没有过度断言。

LLM judge 不应该替代 deterministic checks。它应该在 rule/contract 通过后运行，并输出结构化 label/score/reason。

### Human Review

Braintrust、LangSmith、Google Vertex 都强调 automated scoring 需要 human calibration：

- 人工评分用于校准 judge rubric。
- 人工纠正低置信 judge case。
- 人工确认哪些 production failures 应该加入 dataset。
- 人工评估内容策略和品牌调性。

PTSM 可以先用本地 JSON review queue，而不是直接接外部标注系统。

## Best Practice 5: Prefer Structured Judge Output

Phoenix、LangSmith、OpenAI graders、Vertex metric templates 都强调 evaluator output 应该结构化。自由文本 judge 解释可以保留，但不能作为唯一结果。

推荐 shape：

```yaml
score: 0.0-1.0
label: pass | fail | warning | not_applicable
reason: short explanation
evidence:
  - field: final_content.title
    observation: ...
confidence: 0.0-1.0
```

对 PTSM 的含义：

- 所有 eval results 都写成 JSON artifact。
- judge prompt 要要求输出固定 schema。
- LLM judge 失败或输出不可解析时，eval result 是 `error`，不能静默通过。

## Best Practice 6: Pairwise Beats Absolute Scores for Some Subjective Tasks

OpenAI 和 Vertex 都支持 / 推荐 pairwise 模式用于比较 prompt/model 版本。原因是主观质量的绝对分数常常漂移，而 A/B 哪个更好更稳定。

对 PTSM 的含义：

- style / engagement / title quality 这类指标不应该过早 gate 绝对分。
- prompt/model/skill 改动可以跑 pairwise eval：
  - baseline artifact
  - candidate artifact
  - judge chooses winner with rubric
- 这适合未来 `ptsm eval-compare --baseline-run ... --candidate-run ...`。

## Best Practice 7: Dataset Design Is a Product Decision

Anthropic 和 OpenAI 都强调 test cases 要贴近真实任务分布，同时覆盖 edge cases。对 PTSM，dataset 不能只有“正常场景”。

每个 playbook 至少需要：

- typical cases: 平时真实会跑的场景。
- edge cases: 模糊、过短、过长、低信息量、跨领域输入。
- adversarial cases: 要求越权发布、要求造假、要求绕过平台限制。
- regression cases: 过去失败过、人工修过、低分过的真实 run。
- golden references: 少量人工认可的高质量 artifact。

数据集粒度应该分三层：

- node dataset: 只测 planner/executor/reflector 的输入输出。
- artifact dataset: 测完整 artifact slice。
- end-to-end dataset: 从 request 跑到 final artifact / dry-run publish。

## Best Practice 8: Metrics Need Ownership and Thresholds

没有 owner 的 eval 很快会变成噪音。每个 metric 应该声明：

- owner。
- purpose。
- applies_to。
- scorer_type。
- threshold。
- gate_level。
- false_positive_handling。
- calibration_source。

推荐 gate levels：

- `required`: CI/local gate 必须通过。
- `warning`: report 里显示，不阻塞。
- `manual_review`: 进入人工队列。
- `experimental`: 只记录，不进 aggregate。

## PTSM-Specific Evaluation Target Matrix

| Step | Artifact / Span | Rule | Contract | LLM Judge |
| --- | --- | --- | --- | --- |
| ingest | request + account + playbook inputs | required fields, platform match | account/playbook compatibility | usually no |
| planner | selected playbook, skills, runtime context | required skills present | skill details and context sources traceable | routing appropriateness |
| executor | draft content | JSON/fields/length/hashtags | prompt assets and skill contexts consumed | content quality, tone, relevance |
| reflector | decision + feedback | allowed decision enum | retry/finalize consistent with rules | feedback usefulness |
| finalize | final artifact | artifact exists, schema complete | artifact links to run and skills | final quality if not already judged |
| image | generated images + metadata | path exists, provider fields | prompt derived from content/context | image prompt fit, optional image review |
| publish | publish payload/result | dry-run safety, visibility | side-effect ledger and idempotency | usually no |
| post-publish | status checks | post id/url or fallback status | manual check if private/no identifiers | usually no |

## Recommended PTSM Architecture Direction

The best fit is a local-first evaluation system:

```text
Execution spans -> eval targets -> evaluators -> eval artifacts -> harness aggregates
```

Core concepts:

- `EvalTarget`: normalized view of one thing to score, usually a node/span/artifact slice.
- `Evaluator`: deterministic rule, contract check, or LLM judge.
- `EvalSuite`: ordered collection of evaluators for a playbook/domain/phase.
- `EvalResult`: structured score/label/reason/evidence.
- `EvalRun`: batch execution over one artifact, run, dataset, or experiment.
- `ReviewQueue`: human review candidates created from low confidence, disagreement, or high-risk failures.

Storage should remain file-based first:

- `.ptsm/evals/<eval_run_id>/summary.json`
- `.ptsm/evals/<eval_run_id>/results.jsonl`
- `.ptsm/eval_datasets/<suite>/<case_id>.json`
- `.ptsm/eval_reviews/<review_id>.json`

This matches current PTSM observability instead of forcing an external dashboard.

## Recommended Implementation Phases

### Phase 1: Rule and Contract Foundation

Build:

- evaluation result schema
- evaluator registry
- artifact/run target extractor
- rule evaluators
- contract evaluators
- `ptsm eval-artifact`
- harness-report aggregation

Gate:

- schema completeness
- required runtime metadata
- artifact/run link integrity
- dry-run / publish safety

### Phase 2: Dataset and Regression Loop

Build:

- local eval datasets
- `ptsm eval-suite`
- `ptsm eval-candidates`
- regression case promotion flow
- per-playbook suite definitions

Gate:

- deterministic regression suite before prompt/playbook/skill changes merge.

### Phase 3: LLM Judge Layer

Build:

- judge provider interface
- structured judge prompts
- rubric definitions
- judge cache
- confidence/error handling
- human review queue for low confidence / disagreement

Gate:

- start as warning only.
- promote stable judges after human agreement is measured.

### Phase 4: Experiment Comparison

Build:

- baseline vs candidate artifact comparison
- pairwise judge support
- model/prompt/skill experiment metadata
- report diffs over metrics and cost/latency

Gate:

- block only when required deterministic metrics regress.
- subjective pairwise stays advisory until calibrated.

## What Not To Do

- Do not create one giant LLM judge for the whole run.
- Do not gate CI on uncalibrated subjective scores.
- Do not store only aggregate scores and lose per-step evidence.
- Do not require external services before local eval artifacts are useful.
- Do not make every metric mandatory on day one.
- Do not treat human review as optional forever; it is the calibration source for judge quality.

## Sources

- OpenAI Evaluation Best Practices: https://platform.openai.com/docs/guides/evaluation-best-practices
- OpenAI Working with Evals: https://platform.openai.com/docs/guides/evals
- OpenAI Agent Workflow Evals: https://platform.openai.com/docs/guides/agent-evals
- OpenAI Testing Agent Skills Systematically with Evals: https://developers.openai.com/blog/eval-skills
- Anthropic Define Success Criteria and Build Evaluations: https://docs.anthropic.com/en/docs/test-and-evaluate/define-success
- Anthropic Create Strong Empirical Evaluations: https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests
- Anthropic Demystifying Evals for AI Agents: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- LangSmith Evaluation: https://docs.langchain.com/langsmith/evaluation
- LangSmith Evaluation Types: https://docs.langchain.com/langsmith/evaluation-types
- LangSmith Application-Specific Evaluation Approaches: https://docs.langchain.com/langsmith/evaluation-approaches
- Phoenix Evaluation: https://docs.arize.com/phoenix/evaluation/evals
- Phoenix Built-In Eval Templates: https://arize.com/docs/phoenix/evaluation
- Braintrust Evaluation Quickstart: https://www.braintrust.dev/docs/evaluation
- Braintrust Scorers: https://www.braintrust.dev/docs/guides/functions/scorers
- Braintrust Human Review: https://www.braintrust.dev/docs/guides/human-review
- Ragas Available Metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- Ragas Agentic or Tool Use Metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/agents/
- DeepEval Tool Correctness: https://deepeval.com/docs/metrics-tool-correctness
- DeepEval Faithfulness: https://deepeval.com/docs/metrics-faithfulness
- Google Vertex AI Define Evaluation Metrics: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/eval-python-sdk/determine-eval
- Google Vertex AI Metric Prompt Templates: https://cloud.google.com/vertex-ai/generative-ai/docs/models/metrics-templates
