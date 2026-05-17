---
title: XHS New Theme Research
status: active
owner: ptsm
last_verified: 2026-05-16
source_of_truth: false
related_paths:
  - docs/plans/2026-05-16-human-enrichment-theme.md
  - docs/xhs-topics/index.md
  - docs/xhs-topics/verticals.md
  - docs/skills.md
  - docs/playbooks.md
---

# XHS New Theme Research

This note records the research pass for a new Xiaohongshu theme after the
2026-05-16 `main` baseline.

## Local Baseline

- `main` matched `origin/main` at `e9f5168 merge: xhs content quality improvements`.
- Worktree: `.worktrees/xhs-new-theme-optimization`, branch `feature/xhs-new-theme-optimization`.
- `uv sync` succeeded.
- `uv run pytest -q --ignore=tests/e2e` did not finish. A `-vv` rerun showed
  collection/test startup was dominated by importing `langchain_mcp_adapters`,
  which imports `mcp.types`; a faulthandler dump showed the stack in
  `mcp/types.py` while Python 3.12 was constructing typing unions.
- `uv run topic-radar scan --platforms xhs --mcp-check` reported
  `xiaohongshu: 13 tools`.
- `uv run topic-radar scan --platforms xiaohongshu --keywords "人类丰容,家的丰容计划,观鸟,钩织,普通人用AI,睡前仪式感"`
  failed with `connection timeout (not logged in or server unreachable)`.

## Recommended Theme

Recommended first new theme: **人类丰容 / 零成本日常变量实验**.

Why this should be first:

- It is current. A 2026 Q1 trend readout says `#人你该丰容了` crossed 100 million
  views in 90 days and `#家的丰容计划` crossed 800 million views.
  Source: <https://www.growthhk.cn/cgo/product/157745.html>
- It is repeatable: desk/home micro-changes, sensory walks, handcraft flow,
  routine variables, and "适我主义" can all become series.
- It is visually native: before/after corners, material flat lays, step cards,
  `一周变量` diaries, color walks, plant corners, and desk/home updates map well
  to XHS image carousels.
- It is distinct from existing domains. It can absorb the emotional curve after
  `发疯文学`, but avoids psychology diagnosis territory and avoids duplicating
  `ai_tech_daily_post`.

Supporting signals:

- A 2026 "freshness" summary frames `零成本丰容计划` as space, senses, and spirit.
  It cites `#家的丰容计划` above 500 million views and highlights `拼豆` and
  `钩织` as flow-state examples.
  Source: <https://www.sohu.com/a/996108079_121988268>
- A 2026 hot-word summary lists `活人感`, `代入感`, `柔软力`, `反精致`, and
  `AI人格`, and describes content logic shifting from function display to
  emotional resonance and real-person perspective.
  Source: <https://www.fxbaogao.com/detail/5374285>
- A 2026 new-living trend article says `对我友好的旅行` has reached 230 million
  views and frames "适我主义" as a broader lifestyle shift.
  Source: <https://www.52de.cc/articles/%E8%B5%9B%E4%BA%8B%E5%8A%A8%E6%80%81/20.4%E4%BA%BF%E6%B5%8F%E8%A7%88%E8%83%8C%E5%90%8E-%E5%B0%8F%E7%BA%A2%E4%B9%A6%E5%8F%91%E5%B8%832026%E5%B9%B4%E5%BA%A6%E5%B1%85%E4%BD%8F%E8%B6%8B%E5%8A%BF>

## Secondary Theme

`城市观鸟 / 慢户外观察` is promising but should come later:

- One Q1 trend readout says `#观鸟` saw more than 120 million views in 90 days
  and note volume grew more than 70%.
  Source: <https://www.growthhk.cn/cgo/product/157745.html>
- A 2026-05-11 Beijing Youth Daily / Sina article says the Xiaohongshu `观鸟`
  topic exceeded 820 million views and frames it as a slower, immersive outdoor
  outlet.
  Source: <https://finance.sina.com.cn/jjxw/2026-05-11/doc-inhxmuxx2362828.shtml>

It needs real species/photo accuracy. PTSM should not use generated bird images
as factual observation evidence.

## Post Forms To Encode

- `before -> variable -> after`
- `零成本清单`
- `一周变量日记`
- `工位/卧室/通勤动线微改`
- `Colorwalk / sensory walk`
- `手作心流`

Each note should include a concrete location or object, one named "变量", one
saveable mini checklist, one example-based comment prompt, and low-claim
language. Avoid diagnosis, cure promises, and shopping-list content without a
low-cost action.

## Image Forms To Encode

Recent image guides still recommend 3:4 vertical covers and inner pages, such as
1080x1440 or 1242x1660 equivalents, because they occupy more feed space than
square/horizontal formats.

Sources:

- <https://www.huasheng.ai/insights/xiaohongshu-image-design/>
- <https://focalflow.app/blog/xiaohongshu-image-guide-2026/>
- <https://xiaohongshu.oimi.ai/zh/blog/xiaohongshu-cover-size>

For this theme, the stronger image pattern is creator-like carousel, not a
polished poster:

1. Cover: 3:4 real-life corner, short central line, enough blank area.
2. Before state or "原本的惯性".
3. Variable/material flat lay.
4. One step/checklist card.
5. After state or sensory detail.
6. Optional final page: "评论区交一个你的小变量".

PTSM currently generates one cover image. The near-term improvement is a
structured image brief that guides one generated cover now and can later expand
to carousel generation.
