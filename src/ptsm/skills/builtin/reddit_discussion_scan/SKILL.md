---
skill_name: reddit_discussion_scan
display_name: Reddit Discussion Scan
description: 读取当前 Reddit 英文高互动讨论，优先筛选 AI 热点、心理困境和效率工作流等适合中文读者转译的选题。
display_order: 24
domain_tags: Reddit英文讨论转译
platform_tags: xiaohongshu
playbook_tags: reddit_curation_daily_post
token_budget_hint: 260
assets_present: false
---

# Reddit Discussion Scan

在规划 Reddit 英文讨论转译内容时：

1. 如果 runtime context 显示 `status: available`，优先从 `Selected English discussions` 中选一个最适合中文小红书读者的角度。
2. 只借讨论现象、问题结构和评论冲突，不复制英文原文长段，不展示 Reddit 用户名。
3. 如果 context 显示 `missing_credentials` 或 `unavailable`，不要声称看到了最新 Reddit 热帖；改写成常青英文讨论转译角度，并提示需要配置 Reddit 读取权限。
4. AI 方向优先选普通人能理解的工具变化、模型使用焦虑、工作流改变和隐私/权限问题。
5. 心理方向优先选注意力压力、burnout、关系边界、信息过载和可保存的小练习。
6. 输出必须保留来源边界，例如“Reddit英文讨论里有个现象”，然后翻成中文语境。
