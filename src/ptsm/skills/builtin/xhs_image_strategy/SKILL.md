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
- `style`: 当 `backend=local_social_screenshot` 时，单图只能选 `wechat_chat`、`iphone_notes` 或 `note_card`；现代心理学自动轮播固定为 `psychology_text_card`。
- `role`: 单图只能选 `cover_hook`、`save_tool`、`comment_prompt`、`evidence_or_scene` 或 `shareable_line`；现代心理学自动轮播固定为 `text_carousel`。
- `text_density`: 单图默认选 `low`；现代心理学轮播为 `medium`，但封面仍保持低密度。
- `max_text_units`: 单图封面通常为 `1`、`2` 或 `3`；现代心理学轮播每页最多 `4` 个正文短行。
- `cover_text_strategy`: 一句话说明封面只放哪些短文字。
- `reason`: 一句话说明为什么这个图片形式适合当前主题。
- `prompt_focus`: 可选，一句话告诉图片生成器应该突出什么。
- `golden_line` / `quote_line`: 可选。当本地 `note_card` 或 `iphone_notes` 只需要一句短金句时填写，必须是读者可直接保存或转发的一句话，不要带“金句：”标签。
- `chat_messages` / `messages`: 可选。当 `style=wechat_chat` 时优先输出结构化消息，每条包含 `speaker` 和 `text`；speaker 用真实感昵称或关系名，如 `林主管`、`小周`、`阿晴`、`我`，不要只写 `other`。
- `chat_times` / `status_time`: 可选。只有场景里有明确时间或时间张力时填写，例如 `18:57`、`23:22`；没有时可省略，renderer 会确定性生成不同时间。
- `carousel_style` / `slides`: 只用于现代心理学自动轮播。固定 `carousel_style=psychology_text_card_v1`，并在同一次写作中给出 4-7 张有序 `slides`；每页只能有 `slide_id`、`order`、`role`、`headline`、`body_lines`。

选择规则：

- 微信聊天记录：适合领导/老板/同事/群聊/在吗/消息草稿/可复制回复这类内容，`role=comment_prompt`，`text_density=low`，`max_text_units=2`，`backend=local_social_screenshot`，`style=wechat_chat`。如果输出聊天内容，尽量给 `chat_messages`，使用像真实用户的昵称或关系名，并让对话有因果：触发消息 -> 我的反应/回复 -> 对方补充或评论引子。
- iPhone 记事本：适合清单、三栏工具、5分钟练习、边界句、英语句型、小纸条、可收藏模板，`role=save_tool`，`text_density=low`，`max_text_units=3`，`backend=local_social_screenshot`，`style=iphone_notes`。
- 小红书笔记卡：适合短金句、强封面句、标题和封面语已经能撑住点击的内容，`role=cover_hook` 或 `shareable_line`，`text_density=low`，`max_text_units=1` 到 `2`，`backend=local_social_screenshot`，`style=note_card`。可填写 `golden_line`，但必须是正文自然抽出的短句。
- 外部图片模型：适合真实物件、空间、材料、手作过程、桌面角落、路线感、生活氛围图，`role=evidence_or_scene`，`text_density=low`，`max_text_units=1`，`backend=provider_image`。`prompt_focus` 要写清楚真实物件、空间或过程；不要要求外部模型伪造聊天截图、备忘录截图、真实产品界面或新闻截图。
- 现代心理学文字轮播：默认用本地 `psychology_text_card_v1`，`backend=local_social_screenshot`、`style=psychology_text_card`、`role=text_carousel`。用 4-7 张卡只讲一个主题，语义顺序为封面钩子、具体场景、轻机制、可保存工具、范围/专业边界、评论入口；可以按主题合并边界页，但不能按正文长度机械分页，也不能再调用模型改写页文案。

领域默认：

- 现代心理学：自动生成默认输出本地 `psychology_text_card_v1` 轮播。封面只保留一个生活化钩子和至多一条辅助句；内页每页只承载一个语义任务，以短标题和 1-4 条短行为上限，不做密集心理学讲义。用户明确指定既有 `--local-image-style` 时，保留原来的 `iphone_notes`、`note_card` 或 `wechat_chat` 单图行为。学习系列必须使用目录返回的精确 `slides`，不得自行写、拆、补或重排。
- 每日英语：优先一句场景句、一个对照句型或聊天式误区纠正；图片上不放完整讲义。
- AI/科技资讯：优先一个关键变化、一个界面/设备场景或证据式视觉；真实界面和设备更重要时选 `provider_image`。
- 人类丰容、手作、食物和寿司诗意内容：真实过程、材料平铺、完成细节优先；除非没有视觉证据，否则不要做纯文字海报。
- 武侠/人物评述：氛围、人物姿态、场景隐喻优先，通常用 `provider_image`；文字只放短判断。

图片约束：

- 图片上不要放话题标签、水印、密集小字。
- 不要把 AI 图伪装成真实前后对比、真实观察证据或真实截图证据。
- 本地单图样式优先承载正文里的可复制句、聊天语境或保存工具；低密度封面只允许 1 到 3 个短文字单元。心理学轮播封面仍低密度，内页可以中密度但必须遵守逐页短行上限。
- `psychology_text_card_v1` 只走本地 renderer；任何一页失败都让整组失败，不能把部分图片交给水印、资产台账或发布器。
- provider 图优先像真人手机随手拍：自然光或室内环境光、不完美构图、边缘轻微裁切、真实物件/空间/过程；不要营销海报感、塑料皮肤或 fake UI。
