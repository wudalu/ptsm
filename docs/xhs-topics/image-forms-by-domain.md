---
title: XHS Image Forms By Domain
status: active
owner: ptsm
last_verified: 2026-08-14
source_of_truth: false
related_paths:
  - docs/xhs-topics/index.md
  - docs/skills.md
  - docs/runtime.md
  - src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md
  - src/ptsm/infrastructure/images/note_card_backend.py
  - src/ptsm/application/services/image_carousel_transaction.py
  - src/ptsm/domain/psychology_carousel.py
---

# XHS Image Forms By Domain

这份文档回答一个运行时策略问题：不同领域的小红书图片应该采用什么形式，且尽量简单。

核心结论：封面图不是正文截图。它只承担一个任务：让用户一眼知道“我为什么要点开、保存或评论”。因此图片先定 `role`，再定 `text_density`，最后才定 `backend/style`。现代心理学是唯一的自动多图例外：一组 4–7 张语义文字卡共同讲清一个主题，但第一页仍遵守低密度封面规则，inner pages 也不是正文截图。

`guide-post` 会在 `topic_guidance.image_recommendation` 中把这些规则提前变成选题确认后的操作建议：普通心理学返回 `format_archetype=text_carousel`、`local_style=psychology_text_card_v1`、page range、ordered roles 和 `command_hint=--auto-generate-image`；其他本地截图返回 single style，外部图返回 provider/model。OpenClaw/Codex wrapper 只展示该 payload，不自行决定模型、样式或页面文案。

## Shared Defaults

- 单张封面默认 `text_density=low`；心理学 carousel parent 为 `medium`，但 cover page 仍低密度。
- 封面最多 1 到 3 个文字单元，用 `max_text_units` 表达。
- 本地截图式图片只放短句、清单项或聊天气泡，不放完整正文段落。
- 本地截图可以用 `golden_line` / `quote_line` 提供一句可保存短句；微信聊天可以用结构化 `chat_messages` 提供真实昵称、关系和对话逻辑。
- 有真实物件、空间、材料、过程、界面或人物氛围时，优先视觉证据，不做纯文字海报。
- AI/provider 生成图只能做氛围参考，不能伪装成真实前后对比、真实数据截图或真实观察证据；prompt 应明确手机随手拍、自然光或室内环境光、不完美构图、边缘轻微裁切和真实物件/空间/过程，避免营销海报感、塑料皮肤和 fake UI。

## Domain Matrix

| 领域 | 首选图片角色 | 推荐形式 | 文字上限 | 避免 |
| --- | --- | --- | --- | --- |
| 现代心理学 | `text_carousel` | 4–7 张本地 `psychology_text_card_v1`：cover、scene、light mechanism、save tool、boundary、comment | cover 最多 1 条 supporting line；inner 每页 1–4 条短行 | 把正文盲切分页；一组里换多个主题；写入 hashtag/source/诊断/治疗主张；部分图片继续发布 |
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
- `psychology_text_card_v1`: 仅由 validated `modern_psychology_post` carousel plan 自动选择，不是 `--local-image-style` 参数。renderer 逐页只绘制 `headline` 与 `body_lines`，并由应用层把整组 staging + manifest 原子提交。ordinary 显式选择上面三个 legacy local styles 时仍只生成单封面；learning-series 禁止 override。
- `provider_image`: 当用户需要看见空间、物件、材料、人物氛围、过程、设备或界面感时使用。`role=evidence_or_scene`，`max_text_units=0` 到 `1`。

## Psychology Default

现代心理学最容易误用“备忘录截图”：把正文摘要、机制解释、边界声明塞进一张图，会变成密密麻麻的小字；把 body 按字符数切成多页则会破坏语义。默认策略是同一次 drafting pass 产出一个主题的 semantic carousel：

- 4–7 页，`slides.order` 连续从 1 开始并作为发布顺序，`slide_id` 唯一。
- 第一页必须是 `cover_hook`：一个用户能认出的困境 headline，加最多一条短 supporting line。
- inner roles 从 `concrete_scene`、`light_mechanism`、`save_tool`、`scope_boundary`、`professional_boundary`、`comment_prompt` 选择；每页一个短 headline 和 1–4 条短行。
- 全组只讲同一主题；slide text 不含 hashtags、URL/source locator、诊断、治疗承诺、药物建议或内部指令。
- 本地 renderer 固定 `psychology_text_card_v1`，不调用 raster image provider，也不做第二次模型 rewrite。
- 任一页或 manifest 无效时整组状态为 `psychology_carousel_generation_failed`；不进入 watermark、asset ledger 或 publisher。完整 set 提交后若外部 publish 失败，则保留 immutable set 供重试。
- ordinary 用户明确要求单张封面时，可用 `--local-image-style iphone_notes|note_card|wechat_chat` 走旧路径；learning-series 不能覆盖 catalog-owned image plan。
- historic learning controlled-template-v1 继续验证原单卡；builtin 与新确认 custom revision 使用 template v2 的 7 张 catalog-derived pages，wrapper 只能展示 PTSM 返回文案。

示例结构：

```json
{
  "backend": "local_social_screenshot",
  "style": "psychology_text_card",
  "role": "text_carousel",
  "text_density": "medium",
  "max_text_units": "4",
  "cover_text_strategy": "封面只放一个困境钩子和一条短支持句",
  "reason": "用语义卡逐步展开同一心理学主题",
  "prompt_focus": "只排版本次已验证的页面文字",
  "carousel_style": "psychology_text_card_v1",
  "slides": [
    {
      "slide_id": "cover",
      "order": 1,
      "role": "cover_hook",
      "headline": "凌晨两点，我还在改那句话",
      "body_lines": ["先别急着给这次沉默下结论"]
    }
  ]
}
```

上例只展示字段 shape；有效 plan 仍必须有 4–7 张完整 slides。parent 精确字段为
`backend/style/role/text_density/max_text_units/cover_text_strategy/reason/prompt_focus/carousel_style/slides`，
每个 slide 精确字段只有 `slide_id/order/role/headline/body_lines`。
