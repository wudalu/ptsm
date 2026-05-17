---
skill_name: xhs_image_strategy
display_name: XHS Image Strategy
description: 为小红书笔记决定图片后端、图片形式和本地截图样式。
display_order: 35
platform_tags: xiaohongshu
token_budget_hint: 220
assets_present: false
---

# XHS Image Strategy

在生成正文时，同时输出一个可选 `image_plan` 对象。这个对象只负责决策，不负责生成图片。

`image_plan` 字段：

- `backend`: 只能选 `local_social_screenshot` 或 `provider_image`。
- `style`: 当 `backend=local_social_screenshot` 时，只能选 `wechat_chat`、`iphone_notes` 或 `note_card`。
- `reason`: 一句话说明为什么这个图片形式适合当前主题。
- `prompt_focus`: 可选，一句话告诉图片生成器应该突出什么。

选择规则：

- 微信聊天记录：适合领导/老板/同事/群聊/在吗/消息草稿/可复制回复这类内容，`backend=local_social_screenshot`，`style=wechat_chat`。
- iPhone 记事本：适合清单、三栏工具、5分钟练习、边界句、英语句型、小纸条、可收藏模板，`backend=local_social_screenshot`，`style=iphone_notes`。
- 小红书笔记卡：适合强文字首屏、短金句、标题和封面语已经能撑住点击的内容，`backend=local_social_screenshot`，`style=note_card`。
- 外部图片模型：适合真实物件、空间、材料、手作过程、桌面角落、路线感、生活氛围图，`backend=provider_image`。

图片约束：

- 图片上不要放话题标签、水印、密集小字。
- 不要把 AI 图伪装成真实前后对比、真实观察证据或真实截图证据。
- 本地截图样式优先承载正文里的可复制句、聊天语境或保存工具，不要把整篇正文塞进图里。
