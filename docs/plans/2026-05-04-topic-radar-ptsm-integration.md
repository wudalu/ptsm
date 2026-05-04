# Topic Radar PTSM Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 topic-radar 的选题研究产出可以被 PTSM 的发帖流程消费。遵循 `xhs_trend_scan` 的 builtin skill + runtime context builder 模式，不改旧代码。

**Architecture:** 纯增量——新增 1 个 SKILL.md + 1 个 ContextBuilder + registry 注册 + playbook 挂载。

**Tech Stack:** Python 3.12, existing skill/planner infrastructure, topic-radar artifact JSON.

**Non-goals:** 不修改 planner 逻辑，不修改 executor/reflector，不修改 playbook 运行时。

---

### Task 1: topic_research builtin skill

**Files:**
- Create: `src/ptsm/skills/builtin/topic_research/SKILL.md`

**What:**
- Front matter: `skill_name: topic_research`, `display_name: Topic Research`, `platform_tags: xiaohongshu`, `token_budget_hint: 200`
- Body: 告诉 planner 在发帖前参考 topic-radar 最新选题报告中的垂类、角度和 predict 讨论走向

**verify:**
```bash
uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py -q -k "topic"
```

**done_when:**
- SkillRegistry 发现 `topic_research`
- 可被 `xiaohongshu` playbook 激活

---

### Task 2: Runtime context builder

**Files:**
- Modify: `src/ptsm/skills/runtime_context.py`

**What:**
- 新增 `TopicResearchContextBuilder` 类
- `build()` 方法：读取 `outputs/artifacts/topic-scan-{today}.json`，提取 top 3 垂类 + top 5 角度 + scan_summary，格式化为 Markdown context block
- 如果 artifact 不存在或过期（非今日），返回 None（不阻塞）
- 在 `build_skill_context_resolver()` 中注册

**verify:**
```bash
uv run pytest tests/unit/skills/test_runtime_context.py -q
# E2E: 先跑 topic-radar scan 产出 artifact，再跑 playbook dry-run 验证 context 注入
```

**done_when:**
- 有当日 artifact 时返回选题 context
- 无 artifact 时静默跳过
- planner 在激活 `topic_research` 时能看到注入的 context

---

### Task 3: Playbook wiring

**Files:**
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml`

**What:**
- 在两个现有 `xiaohongshu` playbook 的 `required_skills` 中追加 `topic_research`

**verify:**
```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py -q
```

**done_when:**
- 两个 playbook 加载 `topic_research` 不报错
- dry-run 能看到 planner context 中包含选题建议

---

### Task 4: Docs update

**Files:**
- Modify: `docs/skills.md`
- Modify: `docs/operations/local-runbook.md`

**verify:**
```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

**done_when:**
- docs/skills.md 记录 `topic_research` skill
- runbook 说明 topic-radar + playbook 协作流程
