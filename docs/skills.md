---
title: PTSM Skills
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - src/ptsm/skills/contracts.py
  - src/ptsm/skills/registry.py
  - src/ptsm/skills/loader.py
  - src/ptsm/skills/selector.py
  - src/ptsm/skills/surface.py
---

# Skills

Skill 层负责让运行时按请求范围暴露合适的 builtin skills，而不是把所有技能一股脑塞进上下文。

## Current Model

- `SkillSpec` 描述技能元数据，包括 domain/platform/playbook tags。
- `SkillRegistry` 发现本地 builtin skills。
- `SkillSelector` 根据请求上下文筛选候选技能。
- `RequestSkillSurface` 负责在单次执行内列出和激活可用技能。
- `SkillLoader` 负责真正读取 skill 内容。

## Builtin Skills

当前 builtin skills 位于 [`src/ptsm/skills/builtin/`](../src/ptsm/skills/builtin/)。

常见用途：

- 风格约束
- 内容后处理
- 平台话题或格式化辅助

## What This Does Not Mean Yet

- 还没有用户自定义 skill 市场。
- 还没有跨会话持久化的 skill activation 历史。
- 还没有复杂 capability negotiation。

## Related Files

- Registry: [`src/ptsm/skills/registry.py`](../src/ptsm/skills/registry.py)
- Selector: [`src/ptsm/skills/selector.py`](../src/ptsm/skills/selector.py)
- Surface: [`src/ptsm/skills/surface.py`](../src/ptsm/skills/surface.py)
