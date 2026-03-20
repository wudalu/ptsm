# PTSM Skill Surface Design

**Goal:** 把前一份关于 `skill` 的研究，收敛成 `PTSM` 可直接采用的架构决策。重点回答一个工程问题：`PTSM` 应该如何组织 skill catalog、请求期候选集和运行期按需加载，既避免把所有 skill 平铺给一个 agent，又不把系统做成过度复杂的动态热插拔平台。

## 1. Design Decision

**推荐方案：采用 `request-scoped skill surface + runtime activation`。**

具体来说：

- 系统层面可以维护一个较大的 `skill registry`
- 每次请求开始前，先通过 selector 把总 catalog 缩成一个小的 candidate set
- 当前请求的 agent 只看到这组 candidate set 的 metadata
- 真正命中的 skill 再在运行时按需加载正文、资源和附加工具

明确不做的事情：

- 不把所有 skill 永久平铺到一个强 agent 上
- 不把“运行中的 agent 热插新的 skill catalog 项”当成第一阶段主能力

这个决策的核心原因是：

- 研究结论已经表明，当前业界成熟路径主要是 `request-time selection` 和 `runtime activation`
- 不论 `ADK`、`OpenAI` 还是 `Anthropic`，都没有把“单 agent 执行过程中持续扩容 skill catalog”作为默认推荐模式
- `PTSM` 当前最重要的是先把选择质量、执行稳定性和可观测性做稳，而不是追求极致动态性

## 2. Alternatives Considered

### Option A: Fixed monolithic skillset per agent

做法：

- 给一个主 agent 直接绑定大量 skills
- 依赖 progressive disclosure 控制上下文膨胀

优点：

- 实现最简单
- 便于快速起步

缺点：

- skill metadata 仍然会持续竞争选择
- skill 数量增长后，召回、触发和稳定性会先坏掉
- 很难做租户、账号、平台差异化

结论：

- 只适合非常小的 skill 数量
- 不适合作为 `PTSM` 的长期主架构

### Option B: Runtime hot registration of skills

做法：

- agent 在执行过程中，基于上下文或外部事件把新 skill 动态插入 catalog

优点：

- 理论上最灵活

缺点：

- 当前主流框架并不以此为默认能力
- 缓存、重放、调试、观测和安全边界都更复杂
- 对 `PTSM` 第一阶段来说明显过度设计

结论：

- 不作为当前推荐方案

### Option C: Request-scoped skill surface

做法：

- registry 保存全量 skill
- selector 在请求开始前构造本次 skill surface
- runtime 再按需加载命中的 skill 内容

优点：

- 与现有 industry practice 一致
- 保留大 catalog 的可扩展性
- 把复杂度压在请求开始前，而不是执行中间
- 最利于做观测、评测和回放

缺点：

- 需要额外实现 selector
- 需要把 registry、selector、runtime loader 分层

结论：

- 这是当前最平衡的方案

## 3. Recommended Architecture

### 3.1 Core idea

`PTSM` 不应该直接问“一个 agent 能装多少 skill”，而应该拆成三层：

1. `Registry layer`
   - 全量 skill catalog
   - 管理 skill metadata、版本、作用域、兼容平台、权限要求

2. `Selection layer`
   - 在请求开始前，从 registry 里选出本次 candidate set
   - 负责减少候选空间

3. `Runtime activation layer`
   - 只对命中的 skill 做进一步加载
   - 负责 `metadata -> instructions -> resources/tools` 的渐进展开

这三层拆开之后，`PTSM` 的 skill 问题就不再是“无限堆 skill 会不会爆”，而变成“selector 是否能把总 catalog 压成一个高质量的小候选集”。

### 3.2 Component model

推荐在 `src/ptsm/skills/` 下形成下面几个组件：

- `registry.py`
  - 加载和维护全量 skill catalog
  - 输出统一的 `SkillDescriptor`

- `descriptor.py` 或 `contracts.py`
  - 定义 skill metadata schema
  - 至少包括：
    - `skill_id`
    - `name`
    - `description`
    - `role_tags`
    - `platform_tags`
    - `playbook_tags`
    - `account_scope`
    - `permission_scope`
    - `token_budget_hint`
    - `assets_present`
    - `tools_present`

- `selector.py`
  - 根据请求上下文选出 candidate set
  - 输入：
    - user task
    - selected playbook
    - platform
    - account
    - tenant
    - runtime state
  - 输出：
    - `selected_skill_ids`
    - `selection_reason`
    - `dropped_skill_ids`
    - `fallback_mode`

- `surface.py`
  - 代表某次请求的 `RequestSkillSurface`
  - 本质是当前请求被允许看到的 skill 快照

- `loader.py`
  - 在 runtime 中加载 skill 正文、references、assets、scripts 或附加工具

- `telemetry.py`
  - 记录：
    - 哪些 skill 进入 candidate set
    - 哪些 skill 被真正激活
    - 哪些 skill 虽然可见但从未使用
    - 哪些请求因为缺 skill 或错选 skill 失败

## 4. Request Flow

推荐请求流程如下：

1. `Intent / playbook routing`
   - 先确定当前请求的大类目标和 playbook

2. `Skill preselection`
   - `SkillSelector` 根据任务、平台、账号、租户和 playbook 选出一个小的 candidate set
   - 第一阶段建议把 candidate set 控制在一个小范围内，而不是几十上百个

3. `Agent construction`
   - 为本次请求构造一个 request-scoped agent
   - agent 初始上下文只包含 candidate set 的 metadata

4. `Runtime activation`
   - agent 判断某个 skill relevant
   - 加载该 skill 的 instructions
   - 必要时进一步读取 references / assets
   - 如有附加工具，再在此时暴露

5. `Execution and reflection`
   - 执行完成后记录：
     - 选中的 skill surface
     - 实际激活的 skill
     - 未使用的 skill
     - 缺失 skill 信号

6. `Feedback loop`
   - 如果某类任务经常 miss 某个 skill，回调 selector / registry 配置

这里最重要的边界是：

- `registry` 是全局的
- `surface` 是请求级的
- `activation` 是运行级的

## 5. Error Handling and Safety

### 5.1 Selector miss

如果 selector 没把正确 skill 选进 candidate set，运行期就不可能命中。

因此需要显式处理：

- `skill_missing_for_request`
- `selector_low_confidence`
- `fallback_to_generic_capability`

推荐做法：

- 如果 selector 置信度低，不直接给一个过窄 skill surface
- 可以退回到一个更宽但仍有限的 default bundle

### 5.2 Skill activation failure

运行期可能遇到：

- skill 元数据正确，但正文缺失
- references 路径损坏
- assets 不可读
- 附加工具未注册

这些都不应表现成 agent 的“神秘失败”，而应变成可观测事件：

- `skill_load_failed`
- `skill_resource_missing`
- `skill_tool_resolution_failed`

### 5.3 Overlap and ambiguity

对 `PTSM` 来说，真正危险的通常不是 skill 数量，而是 skill 之间描述重叠。

因此 registry 设计上应强制每个 skill 提供：

- 清晰的适用边界
- 典型命中场景
- 典型误命中场景

否则 selector 和 runtime activation 都会变得不稳定。

## 6. Testing Strategy

这套设计至少要有三类测试：

### 6.1 Registry tests

- skill metadata 是否完整
- tag / scope / version 是否合法
- 目录结构是否符合规范

### 6.2 Selector tests

- 给定任务和上下文，是否选出合理 candidate set
- top-k recall 是否足够
- 是否存在明显的误排除

### 6.3 Runtime integration tests

- candidate set 是否正确注入 agent
- skill 是否能按需加载
- references / assets / tools 是否能在激活后被访问
- 失败事件是否被正确记录

第一阶段最值得优先做的是 selector 回归测试。  
因为这层最直接决定 skill surface 是否可靠。

## 7. Phase Recommendation

### Phase 1

- 固定 registry
- 规则驱动 selector
- request-scoped skill surface
- runtime 按需加载正文和 references

### Phase 2

- 引入 embedding / retrieval 辅助 selector
- 增加 tenant-specific skill bundles
- 增加 skill 使用 telemetry 和离线评测

### Phase 3

- 视需求再考虑更动态的 registry retrieval
- 只在确实出现长尾技能爆炸时，再讨论更复杂的 runtime discovery

## 8. Final Recommendation

`PTSM` 当前最合适的方案不是：

- “给一个强 agent 装很多 skill，然后期待它在运行中动态生长”

而是：

- “维护一个全局 skill registry”
- “每次请求前构造一个小而准的 request-scoped skill surface”
- “进入执行后再按需激活和加载 skill 内容”

一句话总结：

> 对 `PTSM` 来说，正确的扩展点应该是 `selector`，而不是 `running agent hot-plug catalog`。
