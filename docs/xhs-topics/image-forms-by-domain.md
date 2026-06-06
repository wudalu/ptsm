---
title: XHS Image Forms By Domain
status: active
owner: ptsm
last_verified: 2026-05-25
source_of_truth: false
related_paths:
  - docs/xhs-topics/index.md
  - docs/skills.md
  - docs/runtime.md
  - src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md
  - src/ptsm/infrastructure/images/note_card_backend.py
---

# XHS Image Forms By Domain

这份文档回答一个运行时策略问题：不同领域的小红书封面应该采用什么图片形式，且尽量简单。

核心结论：封面图不是正文截图。它只承担一个任务：让用户一眼知道“我为什么要点开、保存或评论”。因此图片先定 `role`，再定 `text_density`，最后才定 `backend/style`。

`guide-post` 会在 `topic_guidance.image_recommendation` 中把这些规则提前变成选题确认后的操作建议：本地截图返回 `recommended_backend=local_social_screenshot` 和 `local_style`，外部图返回 `recommended_backend=provider_image`、`provider=bailian`、`model=qwen-image-2.0-pro` 和 `command_hint=--auto-generate-image`。OpenClaw/Codex wrapper 只展示该 payload，不自行决定模型或样式。

## Shared Defaults

- 默认 `text_density=low`。
- 封面最多 1 到 3 个文字单元，用 `max_text_units` 表达。
- 本地截图式图片只放短句、清单项或聊天气泡，不放完整正文段落。
- 本地截图可以用 `golden_line` / `quote_line` 提供一句可保存短句；微信聊天可以用结构化 `chat_messages` 提供真实昵称、关系和对话逻辑。
- 有真实物件、空间、材料、过程、界面或人物氛围时，优先视觉证据，不做纯文字海报。
- AI/provider 生成图只能做氛围参考，不能伪装成真实前后对比、真实数据截图或真实观察证据；prompt 应明确手机随手拍、自然光或室内环境光、不完美构图、边缘轻微裁切和真实物件/空间/过程，避免营销海报感、塑料皮肤和 fake UI。

## Domain Matrix

| 领域 | 首选图片角色 | 推荐形式 | 文字上限 | 避免 |
| --- | --- | --- | --- | --- |
| 现代心理学 | `save_tool` 或 `cover_hook` | iPhone 记事本式三栏/5分钟工具卡；或一句重构的笔记卡 | 1 到 3 | 把心理机制解释、诊断边界和长正文画进图里；只因正文出现“消息”就误用聊天截图 |
| 发疯文学/职场情绪 | `comment_prompt` 或 `shareable_line` | 微信聊天气泡、短金句卡、可复制回复 | 1 到 2 | 大段吐槽截图、过密备忘录 |
| 每日英语 | `save_tool` | 一句场景句 + 一个替换句型；必要时聊天式对照 | 2 到 3 | 词典页、讲义页、密集语法说明 |
| AI/科技资讯 | `evidence_or_scene` 或 `cover_hook` | 一个关键变化、界面/设备场景、简短对比 | 1 到 2 | 假装真实产品截图、信息图堆字 |
| 人类丰容/生活变量 | `evidence_or_scene` | 原本状态、材料平铺、完成细节、三步清单页 | 1 到 3 | 只有标题没有生活证据的文字海报 |
| 世界杯/看球笔记 | `save_tool`、`cover_hook` 或 `evidence_or_scene` | 赛前看点卡、看球清单、赛后复盘顺序、球衣围巾/客厅看球氛围 | 1 到 3 | 伪造真实比分截图、官方赛程/首发图、媒体新闻截图、赌球或预测比分导向 |
| 手作/食物/寿司诗意内容 | `evidence_or_scene` | 材料、过程、完成品、细节特写 | 0 到 1 | 用文字卡替代可看的过程或成品 |
| 武侠人物评述 | `evidence_or_scene` 或 `cover_hook` | 氛围图、人物姿态、场景隐喻、短判断 | 1 | 设定说明书式海报 |

## Local Style Selection

- `wechat_chat`: 当正文核心是消息、群聊、可复制回复或评论接龙时使用。`role=comment_prompt`，`max_text_units=2`。当前本地 renderer 画的是内容区聊天转录，不画完整手机头部、输入栏或头像；需要像真实对话时，正文或 `image_plan` 应提供结构化 `chat_messages` / `messages`，或 `同事：...`、`我：...` 这类 speaker-prefixed 多行文本。speaker 应尽量是模拟真实用户的昵称或关系名，例如 `林主管`、`小周`、`阿晴`、`我`；`theme=dark`、`status_time` 和 `chat_times` 可用于复刻深色聊天截图与时间分隔。没有显式时间时，renderer 会按 scene 时间或 payload hash 确定性生成，不固定为 `9:41`。
- `iphone_notes`: 当正文核心是可保存工具、三步练习、英语句型或小纸条时使用。`role=save_tool`，`max_text_units=3`。可用 `golden_line` / `quote_line` 指定一条短句；缺省 note 时间也会随 payload 确定性变化。
- `note_card`: 当正文核心是一句强判断或短金句时使用。`role=cover_hook` 或 `shareable_line`，`max_text_units=1` 到 `2`。优先用正文自然抽出的 `golden_line`，不要显示“金句：”这类内部标签。
- `provider_image`: 当用户需要看见空间、物件、材料、人物氛围、过程、设备或界面感时使用。`role=evidence_or_scene`，`max_text_units=0` 到 `1`。

## Psychology Default

现代心理学最容易误用“备忘录截图”：把正文摘要、机制解释、边界声明都塞进图里，会变成密密麻麻的小字。默认策略应改成：

- 封面标题：一个用户能认出的困境。
- 封面语：一句非诊断化重构。
- 图片正文：最多三条短工具句。
- 默认样式：三栏工具、5分钟练习、边界句和消息草稿用 `iphone_notes`；单句重构用 `note_card`；只有真实聊天对话、群聊或可复制回复是首屏资产时才用 `wechat_chat`。
- 选题轮换：职场复盘、关系边界、数字生活、孤独/比较焦虑、情绪调节和热点心理化重构都可以做成工具卡，不要每篇都做成同一个反刍思维封面。

示例结构：

```json
{
  "role": "save_tool",
  "text_density": "low",
  "max_text_units": "3",
  "cover_text_strategy": "只放一个问题和三条急救句",
  "backend": "local_social_screenshot",
  "style": "iphone_notes"
}
```
