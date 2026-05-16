---
title: XHS Dry-Run Preview Review
status: active
owner: ptsm
last_verified: 2026-05-16
source_of_truth: false
related_paths:
  - docs/plans/2026-05-15-xhs-content-quality-improvement.md
  - docs/research/2026-05-15-xhs-content-experiment-log.md
  - outputs/artifacts
---

# XHS Dry-Run Preview Review

This review is a no-publish preview. It uses the current 12 dry-run artifacts from
`docs/research/2026-05-15-xhs-content-experiment-log.md` only for local content
judgment. No XiaoHongShu post was published.

## Raw Candidate Readout

### Stronger Current Directions

| playbook | artifact | why it is stronger |
| --- | --- | --- |
| modern_psychology_post | `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-18.json` | Concrete meeting replay scene, clear `事实 / 猜测 / 下一步` tool, low diagnosis risk. |
| modern_psychology_post | `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-19.json` | Strong boundary-pressure scene and saveable boundary sentence. |
| modern_psychology_post | `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-20.json` | Weekend-to-Monday anxiety has broad recognition and a compact 5-minute tool. |
| modern_psychology_post | `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-21.json` | Work-message boundary scene is concrete and likely commentable. |
| modern_psychology_post | `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-55.json` | The "brain meeting" image is memorable after adding an explicit mini-tool. |
| fengkuang_daily_post | `outputs/artifacts/acct-fk-local-fengkuang_daily_post-1-20.json` | Commute scene has a visible object and less office-template sameness. |
| fengkuang_daily_post | `outputs/artifacts/acct-fk-local-fengkuang_daily_post-1-21.json` | Weekend recovery angle has a cleaner identity conflict than generic work complaints. |

### Weak Spots To Fix Before Publish

- Some 发疯文学 bodies still expose planning language, such as "想让评论区接一句" or "想存一组发疯金句清单". This reads like prompt intent rather than a natural post.
- `收到，但灵魂已下班` appears too often across the batch. The phrase is usable once, but repeated use makes the account sound templated.
- Several 发疯文学 drafts rely on label-level phrases (`打工人`, `工牌`, `灵魂`) without adding enough fresh physical detail.
- Psychology drafts are more structurally reliable, but they can still sound instructional if every post follows the same mechanism -> tool -> safety sentence cadence.
- The current deterministic eval catches contract failures, but it does not yet warn on meta-intent wording like "想让评论区" or "想存一组". Keep this as a candidate warning rule after manual review confirms it is recurring.

## Edited Preview Batch

These are review previews derived from the current dry-run artifacts. They are
not published artifacts and should be treated as copy candidates for human
review.

### 发疯文学 1

**Title:** 地铁门关上那秒，我把灵魂落站台  
**Cover:** 灵魂请下一站下车

今天挤进地铁的时候，我突然理解了什么叫身体上车、灵魂补票失败。

门一关，工牌贴在胸口，像一张提醒我还没完全下班的封条。人被挤成省略号，脑子只剩一句：我不是在通勤，我是在把今天剩下的电量运回家。

可复制疯话：人在车厢，心已请假。

评论区接一句你最想写在闸机口的打工人暗号。

**Hashtags:** `#发疯文学` `#打工人日常` `#通勤崩溃实录`

### 发疯文学 2

**Title:** 周六躺平回血实录  
**Cover:** 床批了我的假

周六醒来第一件事，不是看天气，是确认今天没人能用工作消息把我从床上召回。

这一周我已经在工位上表演了五天情绪稳定，周六只想把自己恢复出厂设置。优秀员工和想躺平的我同时在线，最后床宣布：今天由它接管绩效。

可复制疯话：床批了我的假，工位别越权。

评论区接一句你最想贴在床头的周末保命宣言。

**Hashtags:** `#发疯文学` `#周末躺平日记` `#社畜回血现场`

### 发疯文学 3

**Title:** 下班前又被新需求拽回工位  
**Cover:** 工位又开始召唤

最怕的不是忙，是你刚把电脑合上三厘米，新需求像钩子一样把你从下班边缘拽回来。

那一刻我表面还在点头，内心已经把工牌翻到背面写遗言：收到，但这不是确认，这是灵魂自动回复。

可复制疯话：需求可以新增，我的电量不支持热更新。

评论区接一句你最想发在群里但不敢发的下班疯话。

**Hashtags:** `#发疯文学` `#打工人日常` `#职场情绪实录`

### Psychology 1

**Title:** 会议那句话反复倒带，不是你太敏感  
**Cover:** 把猜测放回事实栏

下班路上，我又开始回放会议里那句话。明明对方可能只是随口一说，脑子却自动给它配了十种潜台词。

这更像是反刍思维在补安全感：大脑想确认自己有没有说错、有没有被误解。不是你太敏感，也不是你想太多，只是这件事还没被归档。

可以先存一个 `事实 / 猜测 / 下一步` 三栏：事实=对方原话；猜测=我脑补的评价；下一步=明天是否需要轻确认一句。

如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。评论区可以留一个你最容易在会议后反复回放的瞬间，我们只收集例子，不给自己贴标签。

**Hashtags:** `#心理学` `#情绪管理` `#职场焦虑` `#反刍思维`

### Psychology 2

**Title:** 周日晚上怕周一消息，不是你没用  
**Cover:** 脑子提前打卡上班

周日晚上还没结束，脑子已经开始替周一上班。消息提示音没响，我却先在心里预演了三遍。

这更像是低控制感在工作：未知任务越多，大脑越想提前排雷。不是你没用，也不是你太脆弱，只是身体比日程表更早进入了警戒。

可以先做一个 5 分钟落地练习：写下明天最担心的 1 件事、能做的 1 个动作、暂时不用处理的 1 件事。先把问题从脑内循环挪到纸上。

如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。评论区可以留一个你周日晚上最容易提前焦虑的瞬间，我们只收集例子，不给自己贴标签。

**Hashtags:** `#心理学` `#情绪管理` `#周一焦虑` `#低控制感` `#自我成长`

### Psychology 3

**Title:** 被说想太多后睡不着，不是你矫情  
**Cover:** 边界句先替你站稳

别人一句"你想太多了"，白天听着很轻，晚上却在脑子里反复重播。

这可能和边界压力有关：当你的感受被轻轻带过，大脑会继续确认自己是不是被误解了。不是你矫情，也不是你需要立刻证明什么。

可以先存一句边界句模板：我知道你是好意，但这件事对我确实有影响，我需要一点时间整理。

如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。评论区可以留一句你最常听到、但会反复想很久的话，我们只收集例子，不给自己贴标签。

**Hashtags:** `#心理学` `#情绪管理` `#关系边界` `#自我成长`

## Review Decision

- Do not publish the raw deterministic 发疯文学 batch as-is.
- Psychology candidates can move to human review sooner, but should still be checked for cadence sameness across consecutive posts.
- The next engineering improvement candidate is a warning-only meta-intent detector for phrases such as "想让评论区", "想存一组", "变体要求", and "模板要求" when they appear in final user-facing copy.
- Real publish remains blocked by login state and should wait until the operator explicitly approves publishing.
