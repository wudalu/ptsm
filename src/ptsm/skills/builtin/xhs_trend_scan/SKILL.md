---
skill_name: xhs_trend_scan
display_name: XHS Trend Scan
description: 在小红书内容规划前先做热点扫描；优先消费本地 MCP 的实时结果，不可用时回退到静态切口判断。
display_order: 25
platform_tags: xiaohongshu
token_budget_hint: 180
assets_present: false
---

# XHS Trend Scan

在开始写小红书内容前：

1. 如果 planner 已经注入了实时站内热点扫描结果，优先基于这些结果判断当前最适合的切口、情绪模板和讨论点。
2. 如果当前 playbook 已经限定主题，就保留主题主线，只补一个更具体的热点切口，不要改写成别的赛道。
3. 把热点扫描落到一个可写的角度：具体情境、动作、情绪张力、评论区会讨论的问题。
4. 只借用一个热点语言线索，不要堆热词，不要复写检索样本标题，不要假装自己看到了比上下文里更多的实时结果。
5. 如果实时扫描不可用，退回静态判断：先看场景更贴近哪个垂类，例如情绪修复、AI 效率、轻养生、宠物陪伴或文化体验。
6. 如果当前场景没有明显热点价值，就退回常青表达，优先保留真实感和可共鸣细节。
