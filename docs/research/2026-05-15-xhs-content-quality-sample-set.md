# XHS Content Quality Sample Set

Date: 2026-05-15

## Purpose

补上登录后的真实小红书采样，验证“浏览量低不是没贴热点，而是内容缺少参与/收藏机制”这个判断。

本次只把搜索级样本作为稳定证据。`get_feed_detail` / `topic-radar teardown` 在本地 MCP 上仍不稳定，详情级正文和评论拆解需要后续修复后再补。

## Commands Run

Login status:

```bash
uv run python -m ptsm.bootstrap xhs-login-status
```

Result: `status: ready`, MCP reported logged in.

Topic scan:

```bash
uv run topic-radar scan \
  --platforms xiaohongshu \
  --keywords "发疯文学,打工人发疯,职场发疯,心理学,情绪管理,职场焦虑,反刍思维" \
  --output-dir outputs/artifacts
```

Result:

- `outputs/artifacts/topic-scan-2026-05-15.json`
- `outputs/artifacts/topic-brief-2026-05-15.md`
- LLM analysis found one high-confidence vertical: `职场发疯学`

Direct MCP search sample:

```text
outputs/artifacts/xhs-content-quality-search-2026-05-15.json
```

This direct sample keeps `feed_id`, `xsec_token`, titles, authors, and interaction counts.

## Collection Summary

Scanned keywords:

- `发疯文学`
- `打工人发疯`
- `职场发疯`
- `心理学`
- `情绪管理`
- `职场焦虑`
- `反刍思维`

Collected candidates:

| Metric | Value |
| --- | ---: |
| total candidates | 117 |
| candidates with comments or collects | 115 |
| highest engagement score | 217039 |
| scoring formula | `likes + comments*4 + shares*6 + collects*2` |

Keyword distribution:

| keyword | count | top engagement_score | median engagement_score |
| --- | ---: | ---: | ---: |
| 情绪管理 | 18 | 217039 | 5416 |
| 发疯文学 | 18 | 186603 | 620 |
| 职场焦虑 | 18 | 151249 | 4100 |
| 反刍思维 | 18 | 18275 | 176 |
| 心理学 | 17 | 20832 | 4193 |
| 打工人发疯 | 17 | 11950 | 910 |
| 职场发疯 | 11 | 4513 | 1045 |

Immediate read:

- `情绪管理` and `职场焦虑` produce the strongest save/share signals.
- `发疯文学` can produce very high comments and shares, but its median is much lower, meaning the format is volatile: generic “发疯” does not automatically起量.
- `反刍思维` has strong top samples but a low median. Mechanism terms need a strong scene or tool; the term alone is not enough.

## Search-Level Sample Rows

These are not full post-body teardowns. They are stable search-result rows with title, interaction metrics, and inferred mechanics from title + keyword + metric shape.

### High-Interaction Samples

| lane | title | engagement_score | likes | comments | collects | shares | inferred mechanic | likely reason |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 心理学/情绪管理 | 迄今为止，对我影响最大的视频之一 | 217039 | 55199 | 752 | 51003 | 9471 | 高情绪承诺 + 强收藏 | 标题制造“值得反复看”的权威感，收藏和转发远高，适合视频/图文工具型内容借鉴 |
| 发疯文学 | 看一次笑一次 | 186603 | 42385 | 7187 | 2604 | 18377 | 笑点循环 + 转发 | 评论和分享极高，说明“可转发给同类人”的情绪笑点比泛泛吐槽更强 |
| 职场焦虑 | 建议工资3w以下工作很烦躁的反复观看 | 151249 | 35193 | 1017 | 19340 | 12218 | 明确人群 + 反复观看 | 直接点名人群和状态，提供强保存理由，但“工资阈值”有争议感 |
| 情绪管理 | 跳过情绪，看见事实。 | 134786 | 51244 | 529 | 28077 | 4212 | 一句话认知重评 | 标题短、可截图、可记忆，收藏强；适合心理内容做封面金句 |
| 发疯文学 | 以为是归宿，却是迷途 | 54735 | 22319 | 594 | 12350 | 890 | 反差句 | 情绪故事感强，收藏高于评论，说明“可代入的反差表达”不只靠搞笑 |
| 职场焦虑 | 强女思维 \| 工作越来越顺的一些Tips： | 33931 | 9801 | 230 | 7414 | 1397 | 身份标签 + Tips | `强女思维` 是身份钩子，`Tips` 是收藏钩子 |
| 情绪管理 | 如何判断一个人的认知在你之上？ | 29804 | 5800 | 88 | 7383 | 1481 | 判断框架 | 问句 + 认知差距，天然适合收藏和转发 |
| 职场焦虑 | 为什么优秀的员工最后都会躺平，尤其是当 | 25050 | 3782 | 194 | 3547 | 2233 | 反常识身份冲突 | “优秀员工/躺平”冲突明确，容易引发职场经验讨论 |
| 情绪管理 | 你有多久没有真正地放松了 | 23052 | 6382 | 166 | 5117 | 962 | 自我检查式共鸣 | 问句直接指向身体/情绪状态，收藏和分享都高 |
| 心理学 | 如何给自己养出「蓬勃的生命力」？ | 20832 | 5650 | 51 | 4825 | 888 | 成长型结果承诺 | 心理内容不必病理化，也能靠“生命力”这种正向结果获得收藏 |
| 发疯文学 | 神金，笑死人了哈哈哈哈哈 | 20808 | 11500 | 516 | 1195 | 809 | 短笑点 + 情绪释放 | 强口语感能拿赞，但收藏较弱；适合互动，不适合作为长期内容资产 |
| 反刍思维 | 思维反刍🔥或许是你内耗的最大原因🔥 | 18275 | 4757 | 156 | 3297 | 1050 | 机制命名 + 痛点归因 | 机制词能起量，但必须连到“内耗”这种用户自我感知词 |
| 反刍思维 | 为什么你必须学会“事过翻篇”？情绪反刍的 | 17945 | 4127 | 76 | 3886 | 957 | 行动目标 + 机制解释 | “事过翻篇”比单独讲反刍更像可执行目标，收藏强 |

### Low-Interaction Controls

| lane | title | engagement_score | likes | comments | collects | shares | likely issue |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 职场焦虑 | 确诊重度职场焦虑的第二天，我不再硬抗 | 0 | 0 | 0 | 0 | 0 | 诊断化标题有风险；即使是真人经历，也不适合作为 PTSM 心理账号的流量模板 |
| 打工人发疯 | 当代打工人抽象发疯实录 3.0（玩梗） | 11 | 5 | 0 | 3 | 0 | 标题泛化，缺少具体物件、场景或评论接龙入口 |
| 反刍思维 | 每次社交后总忍不住思维反刍怎么办？ | 11 | 5 | 0 | 0 | 1 | 问题真实，但标题太像泛科普问答；缺少新鲜场景和可保存工具 |
| 职场发疯 | 在职场“平静地发疯”，是成年人的顶级智慧 | 22 | 2 | 0 | 4 | 2 | 抽象判断多，缺少具体话术、模板或反差句 |

## Pattern Findings

### 发疯文学

High-signal posts are not winning because they contain the word `发疯`. They win when they create a reusable social object:

- `个签`
- `文案`
- `话术`
- `请假条`
- `工牌`
- `截图`
- `清单`

The stronger format is:

```text
具体职场对象 + 一句可复制疯话 + 评论区补一句
```

For PTSM, weak outputs like `打工人地铁生存实录` and `今日已疯` should be rejected. They identify the mood but do not give users anything to copy, complete, save, or send to a friend.

Better directions:

- `领导18:57发「在吗」的那一秒`
- `我的工牌先替我发疯`
- `评论区接一句你最想写在工牌背面的疯话`
- `打工人请假条文学：表面请假，实际灵魂离职`

Safety note:

Do not use mental illness, therapy, hospitals, or medication as joke material. The high-signal pattern can be absurd without stigmatizing psychology terms.

### 现代心理困境观察

High-signal psychology posts cluster around two mechanics:

1. **Save-worthy cognition tools:** `看见事实`, `Tips`, `判断`, `法则`, `反复观看`.
2. **Mechanism + felt pain:** `反刍思维` works when paired with `内耗`, `事过翻篇`, `焦虑`, or a concrete scene.

The stronger format is:

```text
一个可代入场景 + 一个机制名 + 一个可保存小工具
```

For PTSM, safe but flat outputs like `下班后还在复盘那句话` need a stronger first screen:

- `下班后还在复盘一句话，不是你太敏感`
- `脑子在替尴尬加班`
- `事实 / 猜测 / 下一步：今晚用这三栏停一下反刍`
- `你最容易反复复盘哪类瞬间？`

Safety note:

The low-control row with `确诊重度职场焦虑` reinforces the boundary: do not use diagnosis as a click hook. Use "这可能和某个机制有关" instead of "你就是某种问题".

## Tooling Findings

### What Worked

- `xhs-login-status` confirmed MCP login.
- `search_feeds` returned 117 candidates across 7 keywords.
- The search results included enough engagement fields for ranking.
- `topic-radar scan` produced a useful LLM summary for `职场发疯学`.

### What Did Not Work

- `topic-radar scan` with LLM analysis wrote `raw_trending: []`, even though the LLM saw XHS titles. The LLM conversion path currently drops raw trending rows.
- `topic-radar teardown 6942bd1b0000000019027bd5 ...` failed because the note was not accessible through detail fetch.
- Parallel `topic-radar teardown` attempts for several high-score rows triggered timeout / MCP 500 errors.
- Direct raw `get_feed_detail` can return payloads shaped like `{"data": {"note": ...}}`, while the current parser expects `note` nearer the top-level. This can make CLI teardown print `Failed to fetch detail` even when raw detail exists.
- A serial batch detail script spent several minutes in `get_feed_detail` timeouts and was terminated. Search-level sampling is usable today; detail-level teardown needs a fix or stricter retry budget.

## Product Implications

### Immediate Prompt Changes

For `fengkuang_daily_post`, require:

- concrete object
- exact collapse moment
- copyable line
- comment completion prompt
- no psychology stigma jokes

For `modern_psychology_post`, require:

- micro-scene before concept
- mechanism name after scene
- one screenshot-worthy tool
- example-based comment prompt
- concise professional boundary

### Immediate Eval Changes

Add warning-only quality checks for:

- generic title
- absent save_trigger
- absent comment_trigger
- diagnosis bait
- mental-health terms used as jokes in 发疯文学

### Next Research Step

Fix or work around `get_feed_detail` before the next sample round:

1. Preserve raw XHS rows in `TopicScanResult` even when LLM analysis succeeds. Done in code on 2026-05-16; XHS rows now keep `feed_id`, `xsec_token`, interaction counts, author, and source keyword for teardown.
2. Update XHS detail parser to read `data.note`.
3. Add bounded teardown retry: one note should fail fast instead of blocking the whole batch.
4. Re-run detail teardown on the 13 rows above and add comment-theme evidence.

### 2026-05-16 Rescan Status

Follow-up MCP health check returned 13 XHS tools, but `check_login_status` returned `❌ 未登录`.
The scan path now treats this as a platform error instead of a valid empty sample:

```text
No data collected from any platform. Errors: {'xiaohongshu': 'login required; run ptsm xhs-login-qrcode'}
```

Next step is to scan the QR code again, then re-run the keyword scan and detail teardown.
