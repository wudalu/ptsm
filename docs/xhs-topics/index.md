---
title: XHS Topic Index
status: active
owner: ptsm
last_verified: 2026-04-23
source_of_truth: false
related_paths:
  - docs/index.md
  - docs/skills.md
  - docs/playbooks.md
  - docs/research/xhs-mcp-spike.md
  - src/ptsm/skills/builtin
  - src/ptsm/playbooks/definitions
---

# XHS Topic Index

这个目录不是新的 playbook，也不是新的 builtin skill；它是给人和 agent 共用的小红书选题索引层。

目标有两个：

- 把“现在值得追的热点/垂类”整理成可持续更新的主题地图。
- 把“怎么把这些主题接进 PTSM 的 skill/playbook/harness”写成明确的下一步。

## 当前结论

- 2026-04-22 复核时，官方 OpenAI curated skills 里没有小红书专项 skill，不能直接拿来做热点分析。
- 当前仓库已经落地 `xhs_trend_scan` 作为第一个小红书 research builtin skill；帖子拆解和垂类路由仍未产品化。
- 真正可复用的外部能力在小红书 MCP / OpenClaw skill 生态；PTSM 更适合在这些能力之上做自己的 research skill，而不是直接照搬外部 workflow。

## 阅读顺序

1. 先看 [`skills-landscape.md`](skills-landscape.md)，明确现成能力和当前缺口。
2. 再看 [`verticals.md`](verticals.md)，决定后续 1 到 2 个季度要主攻的垂类。
3. 最后看 [`harness-integration.md`](harness-integration.md)，把热点研究接到 PTSM 的 artifacts、planner 输入和 future skills。

## 适用场景

- 规划新的小红书主题线或账号方向。
- 判断一个新帖子应该落在哪个垂类，而不是只靠临时灵感发散。
- 设计新的 `xhs_*` skill 或后续 playbook 时，先统一选题方法和证据来源。

## 目录约定

- 这里优先记录“当前有效的研究框架”和“建议执行的主题方向”。
- 历史验证或一次性排障仍留在 [`docs/research/`](../research/)。
- 真正进入运行时约束的 skill / playbook 事实，仍以 [`docs/skills.md`](../skills.md) 和 [`docs/playbooks.md`](../playbooks.md) 为准。
