# Agent Skill Loading and Runtime Registration

Date: 2026-03-19

## Goal

整理这次关于 `skill` 的讨论，澄清下面几个容易混淆的问题：

1. `skill 已注册`、`skill 已暴露给模型`、`skill 内容已加载` 是否是一回事。
2. `ADK SkillToolset` 当前到底支持什么，不支持什么。
3. 截至 `2026-03-19`，业界主流最佳实践是否支持“运行时动态给 agent 增加 skill”。
4. 这些结论如何映射到 `PTSM` 后续的 agent / skill 架构。

## Executive Summary

结论先说：

- `progressive disclosure` 解决的是“不要把每个 skill 的完整内容都一次性塞进 prompt”。
- 它没有消灭 `catalog discovery / routing` 的问题。一个 agent 仍然要面对“当前有哪些可用 skill / tool”这个候选空间。
- 在 `ADK` 当前的 `SkillToolset` 设计里，`skill catalog` 基本是创建 `agent` / `toolset` 时确定的；运行时支持的是 `按需激活和加载`，不是官方意义上的 `hot add / hot remove skill catalog`。
- 截至今天，业界主流最佳实践支持两种“动态”：
  - `请求级动态选择` 本次暴露哪些 `skills / tools`
  - `运行时按需加载` skill 正文、资源或工具定义
- 但主流并不把“让一个长期运行中的 agent 在执行过程中自我扩容 skill catalog”作为核心推荐范式。
- 真正成熟的大规模动态能力发现，今天更多发生在 `tool search / MCP / registry retrieval` 这一层，而不是 `skill catalog hot-plug` 这一层。

## First Principle: Four Different Layers

讨论 skill 时，至少要分清四层：

1. `System catalog`
   - 系统总共有多少个 skill。
   - 例如整个产品里存在 200 个 skill。

2. `Agent-bound catalog`
   - 当前这个 agent 预先绑定了哪些 skill。
   - 例如某个 writing agent 只绑定 12 个 writing-related skills。

3. `Runtime exposed surface`
   - 在当前请求里，模型一开始能看到哪些 metadata。
   - 这通常是 `skill name / description / path` 或 namespace / server 级描述，而不是完整 skill 正文。

4. `Activated / loaded content`
   - 模型真正加载并使用了哪些 skill 的正文、参考资料、脚本或附加工具。

`progressive disclosure` 的价值，主要发生在第 `3 -> 4` 层：  
它减少的是“完整内容暴露”，不是“候选项存在”本身。

因此，“系统装了很多 skill” 和 “当前请求一开始给模型看了很多 skill metadata” 不是一回事；但它们也不是完全无关，因为 metadata 本身仍然参与选择竞争。

## ADK Current State

### 1. ADK 已经有 Skills / SkillToolset

这点需要明确修正旧认知。  
截至 `2026-03-19`，`ADK` 官方文档已经提供实验性的 `Skills` 能力，文档标注为：

- `Supported in ADK Python v1.25.0`
- `Experimental`

官方入口是：

- `google.adk.skills`
- `google.adk.tools.skill_toolset.SkillToolset`

典型写法是：

```python
weather_skill = load_skill_from_dir(...)

my_skill_toolset = SkillToolset(
    skills=[weather_skill]
)

root_agent = Agent(
    model="gemini-2.5-flash",
    name="skill_user_agent",
    tools=[my_skill_toolset],
)
```

这意味着 `ADK` 不是没有 skill 概念，而是把 skill 作为一个 `toolset` 挂到 agent 上。

### 2. ADK 的 Skills 是渐进式加载，不是全文平铺

`ADK Skills` 官方文档把 Skill 明确分成三层：

- `L1 Metadata`
- `L2 Instructions`
- `L3 Resources`

含义分别是：

- `L1`：供发现用的 metadata，比如 `name`、`description`
- `L2`：正文 instructions，在 skill 被触发时再加载
- `L3`：`references/`、`assets/`、`scripts/` 等资源，按需进一步加载

因此，`ADK SkillToolset` 确实实现了 `progressive disclosure`。

### 3. 但 ADK 的 skill catalog 仍然基本是构造时确定的

从 `SkillToolset` 当前实现看，它的核心模式仍然是：

- 构造 `SkillToolset(skills=[...])`
- 内部保存这组 `skills`
- 每轮请求时，把这些已注册 skills 的 metadata 注入给模型
- 只有模型决定使用某个 skill 时，再调用 `load_skill` / `load_skill_resource`

从官方源码可以看到几个关键信号：

- `SkillToolset.__init__(skills=[...])` 在初始化时接收并保存 `skills`
- `process_llm_request()` 会对内部 `_skills` 做格式化，然后把 skills 索引注入到 LLM request
- `load_skill` 会把某个 skill 标记为 activated，并返回其 instructions
- `adk_additional_tools` 只有在 skill 被激活后才会从 `additional_tools` 中解析并暴露

这说明：

- `SkillToolset` 支持运行时动态激活某个已注册 skill
- 也支持 skill 激活后再暴露附加工具
- 但 stock `SkillToolset` 不是一个“运行中随时向 catalog 新增未知 skill”的 registry

### 4. ADK 当前没有明确的“运行中热插拔 catalog”官方路径

`ADK` 维护者在 `Issue #3647` 中对“运行时修改 `agent.tools`”的答复很重要：

- tool resolution 发生在 preprocessing 阶段
- 在 callback 里修改 `agent.tools` 不是推荐的官方方式
- 更建议通过不同工具集的 agent 做切换，而不是在同一 agent 上临时改 tools

把这个结论投射到 `SkillToolset` 上，实际含义就是：

- `SkillToolset` 属于挂在 `agent.tools` 里的 toolset
- 因此它更像“创建时确定 catalog，运行中按需展开内容”
- 而不是“同一个运行中的 agent 官方支持不断增删 skill catalog”

### 5. 对 ADK 的准确表述

因此，对 `ADK SkillToolset` 最准确的说法应当是：

- `对`：创建 agent 时，基本会确定当前 agent 绑定的 skill catalog。
- `对`：运行时只会按需加载 skill 的 instructions / resources / additional tools。
- `不完全对`：不能把“运行时按需加载某个已注册 skill”误解成“支持运行时向 agent 增加一个原本不在 catalog 里的新 skill”。

## Cross-Vendor Comparison

### 1. ADK: construction-time catalog, runtime progressive disclosure

`ADK` 当前更像：

- 先给 agent 一个已知 skill 列表
- 再在运行中按需加载 skill 正文和资源

它支持的是：

- `dynamic activation`
- `dynamic loading`

它不以官方一等能力的形式强调：

- `runtime hot registration of new skills`

### 2. OpenAI: request-time mounting + tool search

`OpenAI` 当前官方文档里，`skill` 和 `tool search` 是两条相关但不完全相同的线：

#### Skills

`OpenAI Skills` 文档把 skill 定义为一个带 `SKILL.md` 的 versioned bundle。  
使用方式是：在请求里把 skill mount 到 shell environment。

这说明它的主模式是：

- `请求级声明` 本次可用的 skills
- skill 一旦 mounted，模型可以决定是否使用

这本质上是 `request-time selection`，不是长生命周期 agent 在执行中自我扩容 catalog。

#### Tool search

对于大规模动态能力发现，`OpenAI` 当前主推的是 `tool_search`：

- `tool search allows the model to dynamically search for and load tools into the model's context as needed`
- 可配合 `defer_loading: true`
- 官方明确推荐在 `namespace` 或 `MCP server` 级别做延迟加载
- 当工具发现依赖 `tenant state / project state` 时，推荐 `client-executed tool search`

这点非常关键：  
`OpenAI` 真正成熟的“大规模动态能力发现”机制是在 `tool` 层，而不是“让一个 agent 在跑的过程中热插一个 skill 到 catalog”。

### 3. Anthropic: request-scoped skills, not open-ended runtime mutation

`Anthropic` 当前的 `Agent Skills` 也是典型的 request/container 级模式：

- 在 `container.skills` 里显式传入本次请求可用的 skills
- 官方限制 `Maximum Skills per request: 8`
- 文档明确提示：`Including unused Skills impacts performance`
- 文档还明确说明：改变 `Skills list` 会打断 prompt cache，最佳实践是尽量保持稳定

这说明 Anthropic 的推荐范式是：

- skill 是 `per-request selected set`
- 不要给模型挂一大堆无关 skills
- 也不要把“中途不断改 skill 列表”当成高频常态

对于大规模工具面，Anthropic 当前也把重点放在 `tool search`，而不是无限扩展 skill list。

## What Current Best Practice Actually Supports

截至 `2026-03-19`，比较准确的 industry best practice 表述是：

### 1. 支持运行时动态加载 skill 内容

这是主流能力，已经比较成熟：

- 先暴露 metadata
- 再按需加载正文 instructions
- 再按需加载 references / assets / scripts

这一点，`ADK`、`Anthropic`、`OpenAI` 都有对应形态。

### 2. 支持请求级动态选择本次暴露哪些 skills / tools

这也是主流能力：

- `Anthropic`: `container.skills`
- `OpenAI`: 请求里 mount skills / 声明 namespaces / MCP servers / deferred tools
- 自建系统：请求前先做 routing / retrieval，再构造本次 agent request

这类动态选择通常发生在：

- request 构造阶段
- route / retrieval 阶段
- tool search 调用边界

而不是发生在 agent 已经跑到中途之后再“热插 catalog”。

### 3. 不把长期运行 agent 的 skill catalog 热插拔当成默认主路径

主流文档和框架今天都没有把这个模式作为推荐主干。原因很实际：

- cache 稳定性更差
- 行为更难评测
- 观测和复现更困难
- 安全边界更模糊
- 一旦 catalog 与 prompt 前缀频繁变化，性能和命中率都会更不稳定

所以当前更常见的思路不是：

- “让一个 agent 自己无限生长 skill catalog”

而是：

- “每次请求前选好当前需要的 candidate set”
- “进入请求后再按需展开详细内容”

## Recommended Mental Model

一个更实用的心智模型是：

- `skill` 适合封装稳定的方法论、工作流、领域知识和复用性 instruction bundle
- `tool / MCP / registry search` 适合承载大规模、动态、租户相关、权限相关的能力发现
- `router / selector` 负责在请求开始前，把总 catalog 缩成一个小的 candidate set
- `progressive disclosure` 负责把 candidate set 里真正命中的 skill 再展开成正文和资源

换句话说：

- `skill` 更像知识和流程包
- `tool search` 更像大规模动态发现层

## Implications for PTSM

对 `PTSM` 来说，比较稳妥的架构方向不是“给一个强 agent 安装越来越多的 skill，然后期待它自己在运行中扩容和收敛”，而是分三层：

### 1. Registry layer

系统层面可以有很多 skill：

- 平台相关
- 领域相关
- 写作相关
- 发布相关
- 审核相关
- 复盘相关

这一层是完整 catalog。

### 2. Request-time selection layer

在每次请求开始前，根据：

- 当前任务类型
- 平台
- 账号
- tenant 配置
- 用户权限
- 上下文状态

先选出一个小的 candidate set。

这个 candidate set 才应该进入当前 agent 的可见面。

### 3. Runtime activation layer

进入执行后，再让 agent：

- 先看到 skill metadata
- 再按需 `load skill`
- 再按需读 references / assets
- 再按需启用附加工具

这才是比较符合今天最佳实践的分层。

## Recommended Decision Rule for PTSM

如果 `PTSM` 未来 skill 数量不大，而且每个 agent 角色边界很稳定，那么：

- 用固定 `SkillToolset` 或固定 skill list 即可

如果 `PTSM` 未来有明显的长尾、租户定制、平台差异和权限差异，那么：

- 不要把“单 agent + 超大固定 skillset”当成主方案
- 应该增加一层 `skill selector / registry retrieval`
- 每次请求前先筛选，再构造本次 agent 的 skill surface

一句话总结：

> 当前最佳实践支持“按需加载内容”和“请求级动态选择”，但并不把“运行中的单 agent 动态热插 skill catalog”作为主流推荐模式。

## Sources

- ADK Skills: https://google.github.io/adk-docs/skills/
- ADK SkillToolset source: https://raw.githubusercontent.com/google/adk-python/main/src/google/adk/tools/skill_toolset.py
- ADK issue on runtime model/tool switching: https://github.com/google/adk-python/issues/3647
- OpenAI Skills: https://developers.openai.com/api/docs/guides/tools-skills
- OpenAI Tool Search: https://developers.openai.com/api/docs/guides/tools-tool-search
- OpenAI Function Calling: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI MCP and Connectors: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- Anthropic Agent Skills guide: https://platform.claude.com/docs/en/build-with-claude/skills-guide
- Anthropic Agent Skills overview: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Anthropic Tool Search: https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool
