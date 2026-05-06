# AI科技资讯 Playbook — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增 AI科技资讯 领域 playbook，以专业解读+结构化总结的形式产出小红书内容，消费 topic-radar 的实时热点选题。

**Architecture:** 纯增量——新增 playbook 定义 + 1 个 builtin skill + 1 个 account 定义。不改运行时逻辑。

**Tech Stack:** Python 3.12, existing playbook/skill/account infrastructure.

**Non-goals:** 不修改 runtime graph，不修改 planner/executor/reflector 逻辑。

---

### Task 1: ai_tech_style builtin skill

**Files:**
- Create: `src/ptsm/skills/builtin/ai_tech_style/SKILL.md`

**What:** 定义 AI科技资讯 的语气和内容规范："专业但不枯燥，有观点但不偏激，信息密度高但可读性强"

**verify:**
```bash
uv run pytest tests/unit/skills/test_skill_registry.py -q -k "ai_tech"
```

**done_when:** SkillRegistry 发现 `ai_tech_style`，platform_tags 为 xiaohongshu

---

### Task 2: AI科技资讯 playbook definition

**Files:**
- Create: `src/ptsm/playbooks/definitions/ai_tech_daily_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/ai_tech_daily_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/ai_tech_daily_post/persona.md`
- Create: `src/ptsm/playbooks/definitions/ai_tech_daily_post/reflection.md`

**What:** 完整 playbook 四件套。domain: "AI科技资讯"，platform: xiaohongshu，skills: `[xhs_trend_scan, topic_research, ai_tech_style, xhs_hashtagging]`。reflection 要求 must_include_hash: "#AI资讯"，字数 ≥ 200。

**verify:**
```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py -q -k "ai_tech"
```

**done_when:** PlaybookRegistry 发现 `ai_tech_daily_post`，解析正确

---

### Task 3: AI科技资讯 account definition

**Files:**
- Create: `src/ptsm/accounts/definitions/acct-ai-tech-local.yaml`

**What:** account_id=acct-ai-tech-local, domain="AI科技资讯", platform=xiaohongshu, publish_mode=dry-run

**verify:**
```bash
uv run pytest tests/unit/accounts/test_account_registry.py -q -k "ai_tech"
```

**done_when:** AccountRegistry 可 get("acct-ai-tech-local")

---

### Task 4: E2E dry-run validation

**Files:** No new files

**What:** 跑一次完整 dry-run，验证 playbook 能产出符合 AI科技资讯 风格的内容

**verify:**
```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "AI付费趋势" \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post \
  --fresh-topic-research
```

**done_when:** status=completed, 正文含 AI/科技相关话题, 标签含 #AI资讯

---

### Task 5: Docs and harness

**Files:**
- Modify: `docs/playbooks.md` — add ai_tech_daily_post
- Modify: `docs/skills.md` — add ai_tech_style

**verify:**
```bash
uv run pytest -q --ignore=tests/e2e
```

**done_when:** 全部测试通过，docs-sync 无报错
