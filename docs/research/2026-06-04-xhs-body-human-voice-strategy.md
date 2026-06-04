---
title: XHS Body Human Voice Strategy
status: active
owner: ptsm
last_verified: 2026-06-04
source_of_truth: false
related_paths:
  - docs/plans/2026-06-04-xhs-body-human-voice.md
  - docs/research/2026-05-15-xhs-content-quality-sample-set.md
  - docs/research/2026-05-17-xhs-live-mcp-sample.md
  - src/ptsm/skills/builtin/xhs_human_voice/SKILL.md
  - src/ptsm/evaluations/contracts_eval.py
  - src/ptsm/playbooks/definitions
---

# XHS Body Human Voice Strategy

## Purpose

This note records the evidence and strategy behind the 2026-06-04 request:

> 优化现在帖子正文的质量，增加人味，可以去抓下小红书热门帖，整理策略

The target is not another title-only pass. PTSM already has short title,
body-length, save-trigger, comment-trigger, and anti-template contracts. The
remaining gap is body texture: generated posts can be valid but still feel like
an organized content brief rather than a real person posting from a lived scene.

## 2026-06-04 Live XHS Grab Attempt

I attempted a bounded current XHS sample with the local MCP server:

```bash
COOKIES_PATH=/Users/wudalu/llm-app/ptsm/cookies/fk-local.json \
  /Users/wudalu/llm-app/ptsm/.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64

uv run python -m ptsm.bootstrap collect-xhs-patterns \
  --lane body_human_voice \
  --keywords "活人感,小红书文案,发疯文学,情绪管理,人类丰容" \
  --sample-limit-per-keyword 3 \
  --delay-seconds 0.5 \
  --skip-login-check \
  --tool-timeout-seconds 20 \
  --output-dir outputs/artifacts/xhs-body-human-voice
```

Result artifact:

```text
outputs/artifacts/xhs-body-human-voice/samples-2026-06-04.json
```

Artifact summary:

```json
{
  "lane": "body_human_voice",
  "sample_count": 0,
  "keyword_errors": {
    "活人感": "MCP connection failed — check if server is healthy",
    "小红书文案": "MCP connection failed — check if server is healthy"
  }
}
```

MCP logs showed:

- `活人感` search reached `search_feeds` and returned HTTP 500 after about 20 seconds.
- `小红书文案` search reached `search_feeds` and returned HTTP 500 after about 20 seconds.
- `发疯文学` reached `search_feeds`, but the process was stopped before any usable sample rows were persisted.

This attempt is evidence that live MCP sampling is currently unstable. It is
not evidence of current hot-post content patterns. The implementation must not
claim a fresh 2026-06-04 XHS hot-post sample was collected.

## Usable Repository Evidence

### 2026-05-15 Search-Level Sample

`docs/research/2026-05-15-xhs-content-quality-sample-set.md` and
`/Users/wudalu/llm-app/ptsm/outputs/artifacts/xhs-content-quality-search-2026-05-15.json`
record 117 real XHS search-level candidates across:

- `发疯文学`
- `打工人发疯`
- `职场发疯`
- `心理学`
- `情绪管理`
- `职场焦虑`
- `反刍思维`

High-signal rows:

| title | signal | implication |
| --- | --- | --- |
| `跳过情绪，看见事实。` | high collect/share | short, screenshot-worthy reframes are stronger than textbook explanation |
| `看一次笑一次` | high comment/share | repeatable social jokes beat generic emotional venting |
| `强女思维 | 工作越来越顺的一些Tips：` | identity + tips | identity hook plus saveable unit gives both click and collect reasons |
| `为什么优秀的员工最后都会躺平...` | role conflict | specific social identity creates commentable tension |

Low controls:

| title | issue |
| --- | --- |
| `当代打工人抽象发疯实录 3.0（玩梗）` | broad mood label, no object or participation |
| `平静地发疯，是成年人的顶级智慧` | abstract judgment, no scene or reusable unit |
| `每次社交后总忍不住思维反刍怎么办？` | real problem, but too much like generic Q&A without scene/tool |

### 2026-05-17 Live MCP Sample

`docs/research/2026-05-17-xhs-live-mcp-sample.md` records a successful live
sample for human-enrichment adjacent lanes. Useful body/format signals:

- realization hooks: `突然意识到...`
- direct second-person entry: `人，你该...`
- before/after contrast when visual evidence exists
- low-cost method framing
- material/process hooks for handcraft
- concrete comment prompts around a corner, material, route, or personal variant

## Public 2026 Trend Refresh

Public sources align with the local sample direction, but they are weaker than
repository-local samples and should not override tests:

- 千瓜's 2026 XHS hotword summary lists `抽象力`, `痛文化`, `主体性`, `活人感`,
  `边界感`, `反精致`, `AI人格`, `柔软力`, `代入感`, and `文化力`, plus signals
  such as `丝瓜汤` and `爱你老己`:
  https://www.qian-gua.com/information/detail/3318
- A recent public interpretation of the same report describes `活人感` as a
  preference for real-life texture over perfect filtered persona, and connects
  `丝瓜汤` / `三明治拒绝法` to boundary and self-positioning content:
  https://wwwsrc.wsdsocial.com/zh-cn/article/Top%2010%20Hot%20Words%20on%20Xiaohongshu
- A 2026 public guide says high-performing notes should trigger screenshot/save,
  long comments, and high-contribution interaction rather than only likes:
  https://www.php.cn/faq/1956111.html

## Strategy: Five Body Human-Voice Rules

### 1. 现场锚点

The body should open from a visible or audible scene:

- exact time: `18:57`, `下班路上`, `睡前`, `今晚`
- object: `工牌`, `群聊`, `书桌`, `材料`, `便签`
- relationship: `领导`, `朋友`, `同事`, `旧友`, `普通球迷`
- line: `在吗`, `这一句`, `这句话`
- action: `刚关电脑`, `把旧材料摊开`, `走到地铁口`

Bad pattern:

```text
职场压力需要被合理释放。
```

Better pattern:

```text
领导18:57发来一句“在吗”，我刚摘下来的工牌又被迫上班。
```

### 2. 真人视角

Use first-person or direct-reader perspective often enough that the body feels
posted by a person:

- `我`, `你`, `我们`
- `今天`, `刚刚`, `今晚`
- `路上`, `桌上`, `手边`, `那一秒`

This does not mean every post must be memoir. It means the body should not read
like a neutral explainer detached from a person.

### 3. 少总述

Avoid abstract essay framing:

- `本文`
- `本篇`
- `建议大家`
- `我们应该`
- `从本质上`
- `核心逻辑是`
- `总体来说`

Some domains need structure, but the visible body should still sound like a
note, not a document.

### 4. 自然保存

Keep saveable mechanics, but hide internal labels:

Bad pattern:

```text
可保存单元：事实 / 猜测 / 下一步。
```

Better pattern:

```text
我会把它写成三栏：事实 / 猜测 / 下一步。
```

### 5. 可接话结尾

End with a concrete handoff:

- `评论区接一句你最想写在工牌背面的疯话`
- `你会先丰容哪个角落？`
- `你读到苏轼哪一句会想到自己？`
- `这句英文你会放在哪个场景里？`
- `你现在更像是在用 AI，还是在照看 AI？`

Avoid ending with a broad opinion prompt like `你怎么看？` when a concrete
example, line, role, or scene can be requested.

## Implementation Implication

Use a generic deterministic contract instead of runtime branching:

- `body_must_include_scene_signal: true`
- `body_scene_signal_any: [...]`
- `body_human_anchor_any: [...]`

Each playbook owns its own scene signals because "human" looks different by
domain. The shared evaluator only checks for the configured signal/anchor; it
does not know playbook-specific taste.

The shared prompt asset should carry the five strategy rules so DeepSeek/live
generation has the same target as deterministic evals.
