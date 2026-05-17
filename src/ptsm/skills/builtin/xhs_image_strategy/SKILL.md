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

决策顺序必须是：先定图片承担的任务，再定文字密度，最后定后端和样式。不要把正文搬进图里。

`image_plan` 字段：

- `backend`: 只能选 `local_social_screenshot` 或 `provider_image`。
- `style`: 当 `backend=local_social_screenshot` 时，只能选 `wechat_chat`、`iphone_notes` 或 `note_card`。
- `role`: 图片承担的任务，只能选 `cover_hook`、`save_tool`、`comment_prompt`、`evidence_or_scene` 或 `shareable_line`。
- `text_density`: 图片文字密度，默认选 `low`；只有清单页才可选 `medium`。
- `max_text_units`: 封面最多可见文字单元数，低密度封面通常为 `1`、`2` 或 `3`。
- `cover_text_strategy`: 一句话说明封面只放哪些短文字。
- `reason`: 一句话说明为什么这个图片形式适合当前主题。
- `prompt_focus`: 可选，一句话告诉图片生成器应该突出什么。

选择规则：

- 微信聊天记录：适合领导/老板/同事/群聊/在吗/消息草稿/可复制回复这类内容，`role=comment_prompt`，`text_density=low`，`max_text_units=2`，`backend=local_social_screenshot`，`style=wechat_chat`。
- iPhone 记事本：适合清单、三栏工具、5分钟练习、边界句、英语句型、小纸条、可收藏模板，`role=save_tool`，`text_density=low`，`max_text_units=3`，`backend=local_social_screenshot`，`style=iphone_notes`。
- 小红书笔记卡：适合短金句、强封面句、标题和封面语已经能撑住点击的内容，`role=cover_hook` 或 `shareable_line`，`text_density=low`，`max_text_units=1` 到 `2`，`backend=local_social_screenshot`，`style=note_card`。
- 外部图片模型：适合真实物件、空间、材料、手作过程、桌面角落、路线感、生活氛围图，`role=evidence_or_scene`，`text_density=low`，`max_text_units=1`，`backend=provider_image`。

领域默认：

- 现代心理学：优先低密度、可保存的平实贴图，不做心理学讲义海报。三栏工具、5分钟练习、边界句和消息草稿默认 `local_social_screenshot` + `iphone_notes` + `role=save_tool`；单句重构用 `note_card` + `role=cover_hook`；只有真实聊天对话、群聊或可复制回复是首屏资产时才用 `wechat_chat`。不要把机制解释、诊断边界和正文段落放进图里。
- 每日英语：优先一句场景句、一个对照句型或聊天式误区纠正；图片上不放完整讲义。
- AI/科技资讯：优先一个关键变化、一个界面/设备场景或证据式视觉；真实界面和设备更重要时选 `provider_image`。
- 人类丰容、手作、食物和寿司诗意内容：真实过程、材料平铺、完成细节优先；除非没有视觉证据，否则不要做纯文字海报。
- 武侠/人物评述：氛围、人物姿态、场景隐喻优先，通常用 `provider_image`；文字只放短判断。

图片约束：

- 图片上不要放话题标签、水印、密集小字。
- 不要把 AI 图伪装成真实前后对比、真实观察证据或真实截图证据。
- 本地截图样式优先承载正文里的可复制句、聊天语境或保存工具；低密度封面只允许 1 到 3 个短文字单元。
