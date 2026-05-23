---
title: XHS Topic Index
status: active
owner: ptsm
last_verified: 2026-05-23
source_of_truth: false
related_paths:
  - docs/index.md
  - docs/skills.md
  - docs/playbooks.md
  - docs/research/xhs-mcp-spike.md
  - src/ptsm/skills/builtin
  - src/ptsm/playbooks/definitions
  - src/topic_radar
  - docs/topic-radar.md
  - docs/xhs-topics/image-forms-by-domain.md
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
---

# XHS Topic Index

这个目录不是新的 playbook，也不是新的 builtin skill；它是给人和 agent 共用的小红书选题索引层。

目标有两个：

- 把“现在值得追的热点/垂类”整理成可持续更新的主题地图。
- 把“怎么把这些主题接进 PTSM 的 skill/playbook/harness”写成明确的下一步。

## 当前结论

- 2026-04-22 复核时，官方 OpenAI curated skills 里没有小红书专项 skill，不能直接拿来做热点分析。
- 当前仓库已经落地 `xhs_trend_scan` 作为第一个小红书 research builtin skill；帖子拆解和垂类路由仍未产品化。
- 当前仓库已经落地周期性 XHS pattern library：`collect-xhs-patterns` 负责 bounded live MCP 采样，`analyze-xhs-patterns` 负责把原始样本变成可复用格式 snapshot，普通 `run-playbook` 读取本地 `current.json` 而不是每次实时搜索高互动帖子。
- 2026-05-23 爆品梗调研已经进入现有 playbook/skill 资产层：共享 `xhs_human_voice` 负责温暖、真人、不格式化的横向语气，各领域 style/persona/prompt 再把丝瓜汤、爱你老己、三明治拒绝法、适我主义、AI 生活搭子、文化力、老款人格等机制消化成自己的主题表达。该研究现已进一步收敛为“角色认领、可保存工具、低成本动作、评论续写”的产品化 hook 框架，特别补充了苏轼/怀民这类文化角色梗如何把评论区变成关系入口。详见 [`docs/research/2026-05-23-xhs-viral-meme-product-hooks.md`](../research/2026-05-23-xhs-viral-meme-product-hooks.md)。
- 真正可复用的外部能力在小红书 MCP / OpenClaw skill 生态；PTSM 更适合在这些能力之上做自己的 research skill，而不是直接照搬外部 workflow。

## 阅读顺序

1. 先看 [`skills-landscape.md`](skills-landscape.md)，明确现成能力和当前缺口。
2. 再看 [`verticals.md`](verticals.md)，决定后续 1 到 2 个季度要主攻的垂类。
3. 看 [`image-forms-by-domain.md`](image-forms-by-domain.md)，把不同领域的封面图角色、文字密度和本地/外部图片形式定下来。
4. 看 [`../research/2026-05-23-xhs-viral-meme-product-hooks.md`](../research/2026-05-23-xhs-viral-meme-product-hooks.md)，把近一年爆品梗、可保存结构、评论接龙和现有 playbook 的承接关系读清楚。
5. 最后看 [`harness-integration.md`](harness-integration.md)，把热点研究接到 PTSM 的 artifacts、planner 输入和 future skills。

## 适用场景

- 规划新的小红书主题线或账号方向。
- 判断一个新帖子应该落在哪个垂类，而不是只靠临时灵感发散。
- 设计新的 `xhs_*` skill 或后续 playbook 时，先统一选题方法和证据来源。

## 目录约定

- 这里优先记录“当前有效的研究框架”和“建议执行的主题方向”。
- 历史验证或一次性排障仍留在 [`docs/research/`](../research/)。
- 真正进入运行时约束的 skill / playbook 事实，仍以 [`docs/skills.md`](../skills.md) 和 [`docs/playbooks.md`](../playbooks.md) 为准。
