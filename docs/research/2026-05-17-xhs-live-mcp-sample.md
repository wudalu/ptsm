---
title: XHS Live MCP Sample
status: active
owner: ptsm
last_verified: 2026-05-17
source_of_truth: false
related_paths:
  - docs/plans/2026-05-17-xhs-live-data-optimization.md
  - docs/research/2026-05-16-xhs-new-theme-research.md
  - docs/xhs-topics/verticals.md
  - src/topic_radar/cli.py
  - src/topic_radar/mcp_client.py
  - src/topic_radar/platforms/xiaohongshu.py
---

# XHS Live MCP Sample

This note records the 2026-05-17 live Xiaohongshu MCP sampling pass. It
supersedes the earlier web-only theme read for optimization planning, while
keeping the earlier public-source research as background context.

## Method

Environment:

- Worktree: `.worktrees/xhs-new-theme-optimization`
- MCP server: `http://localhost:18060/mcp`
- `uv run python -m ptsm.bootstrap xhs-login-status` initially returned
  `status: ready`.
- `uv run topic-radar scan --platforms xiaohongshu --mcp-check` returned
  `xiaohongshu: 13 tools`.

Successful live scans:

```bash
TOPIC_RADAR_SAMPLE_LIMIT=60 \
  uv run topic-radar scan \
  --platforms xiaohongshu \
  --keywords "人类丰容,家的丰容计划,低成本改造,活人感,反精致" \
  --output-dir outputs/artifacts/xhs-live-theme-a-2026-05-17

TOPIC_RADAR_SAMPLE_LIMIT=60 \
  uv run topic-radar scan \
  --platforms xiaohongshu \
  --keywords "观鸟,钩织,拼豆,普通人用AI,睡前仪式感" \
  --output-dir outputs/artifacts/xhs-live-theme-b-2026-05-17
```

Artifacts:

- `outputs/artifacts/xhs-live-theme-a-2026-05-17/topic-scan-2026-05-17.json`
- `outputs/artifacts/xhs-live-theme-a-2026-05-17/topic-brief-2026-05-17.md`
- `outputs/artifacts/xhs-live-theme-b-2026-05-17/topic-scan-2026-05-17.json`
- `outputs/artifacts/xhs-live-theme-b-2026-05-17/topic-brief-2026-05-17.md`

One direct MCP probe before the larger scans also returned 22 feeds for
`人类丰容`. The first result was `人，你该“丰容”了!` with a 1080x1440 cover
payload, which confirms the 3:4 vertical cover pattern on live XHS data.

## MCP Reliability Notes

The live MCP path is usable, but not robust enough for unattended broad scans.

Observed behavior:

- Sequential `topic-radar` scans worked for theme batches A and B.
- Parallel scans failed with `connection timeout` or `unhandled errors in a
  TaskGroup`.
- Broad form searches such as `工位改造,卧室改造,书桌改造,...` later triggered
  HTTP 500 from the MCP server.
- After repeated 500s, `xhs-login-status` changed from `ready` to
  `login_required`, and QR retrieval also returned HTTP 500.

Root-cause hypothesis:

- The server and account were initially valid.
- The failure happens inside MCP tool execution, not tool discovery.
- xiaohongshu-mcp appears sensitive to concurrent or repeated heavy search
  sessions. The research pipeline should use bounded sequential calls, retry
  per keyword, and persist partial results immediately.

## Live Topic Findings

### 人类丰容 / 家的丰容计划

High-signal live rows:

| keyword | title | engagement score | likes | collects | comments | shares |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 人类丰容 | 突然意识到人类也需要丰容 | 29993 | 10749 | 3187 | 333 | 1923 |
| 家的丰容计划 | 空无一物的家vs丰容后的家🛋️ | 26769 | 7449 | 1592 | 680 | 2236 |
| 人类丰容 | 人，你该“丰容”了! | 11221 | 1573 | 656 | 26 | 1372 |
| 人类丰容 | 成年人低成本的丰荣有哪些？ | 8777 | 1789 | 1548 | 82 | 594 |
| 家的丰容计划 | 人，你该给家丰容了！ | 5892 | 1214 | 590 | 255 | 413 |

Pattern:

- Hook language often uses second-person address or sudden realization:
  `人，你该...`, `突然意识到...`.
- The strongest home example uses explicit before/after tension:
  `空无一物的家vs丰容后的家`.
- Save value is framed as low-cost methods, not purely emotional prose.
- Comment value comes from self-identification and sharing personal variants:
  "我也需要", "我的家/桌面/路线也可以这样".

### 低成本改造

High-signal live rows:

| title | engagement score | likes | collects | comments | shares |
| --- | ---: | ---: | ---: | ---: | ---: |
| pdd低成本租房改造分享💡｜美不需花大💰 | 52566 | 14318 | 11893 | 386 | 2153 |
| 改造结束，2w改成这样已经很满意了🥹 | 23005 | 5887 | 3314 | 560 | 1375 |
| 二手房局部改造个人经验总结 | 16156 | 2524 | 3792 | 396 | 744 |
| 男生请这样低成本爆改自己（建议收藏 | 10484 | 2726 | 3221 | 62 | 178 |

Pattern:

- Clear cost framing drives saves: `低成本`, `2w`, `个人经验总结`, `建议收藏`.
- Before/after and cost curiosity are the dominant hook mechanics.
- This can support `家的丰容计划`, but PTSM should avoid becoming a shopping-list
  account; the playbook should require action variables and low-cost
  substitutes.

### 观鸟

High-signal live rows:

| title | engagement score | likes | collects | comments | shares |
| --- | ---: | ---: | ---: | ---: | ---: |
| 观鸟让我意识到过去的我失去了什么。 | 58076 | 26996 | 5787 | 1557 | 2213 |
| 观鸟，毁了我的女儿 | 13589 | 3903 | 642 | 347 | 1169 |
| 观鸟这个爱好特别适合三分钟热度的人 | 8856 | 4432 | 884 | 262 | 268 |

Pattern:

- The strongest hooks are identity/realization hooks, not species-name hooks.
- Comment density is high because the topic invites experience sharing and
  debate.
- This remains a later playbook because image/species accuracy needs real
  observation evidence.

### 钩织 / 拼豆

High-signal live rows:

| keyword | title | engagement score | likes | collects | comments | shares |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 钩织 | 新手必看 \| 钩织入门基础针法大揭秘🧶2 | 30802 | 9854 | 9386 | 19 | 350 |
| 钩织 | 小老外怎么这么喜欢蔬菜啊！ | 25970 | 11050 | 2136 | 826 | 1224 |
| 钩织 | 每天一个设计—水果帽子猫猫钩织 | 21255 | 3277 | 2503 | 423 | 1880 |
| 拼豆 | 哇声一片的烫豆过程 | 801319 | 404055 | 48717 | 7417 | 45027 |
| 拼豆 | 烫豆完成！共130小时，97000颗拼豆我的祖国 | 786355 | 505223 | 35481 | 8051 | 29661 |
| 拼豆 | 拼豆做寿司？原来这么简单 | 186672 | 75016 | 22279 | 1305 | 10313 |

Pattern:

- Handcraft has very strong visual virality, especially process reveal and
  material transformation.
- `新手必看`, `入门`, `每天一个设计`, `原来这么简单` are save-friendly formats.
- PTSM can use handcraft as a sub-series inside human enrichment: "ten-minute
  material variable", not necessarily a standalone product tutorial account.

### 普通人用 AI / 睡前仪式感

The rule-based brief detected AI efficiency from the batch:

- `普通人用AI{tool}搞定{task}，附上步骤`
- Discussion reason: practical value, save/share incentive.

The raw exported `raw_trending` currently keeps only the first 30 rows per
platform, so later keywords in a large keyword batch can be dropped from the
artifact. This is a data-pipeline issue and should be fixed before relying on
large batch ordering.

## Recommended Content Direction

Keep `人类丰容 / 零成本日常变量实验` as the first new theme, but tighten it with
live XHS mechanics:

1. Use realization hooks: `突然意识到...`, `人，你该...`.
2. Use explicit contrast when visual evidence exists: `空无一物 vs 丰容后`.
3. Attach a concrete low-cost mechanism: desk, home corner, route, light,
   material, handcraft, storage, plant, walking route.
4. Add a saveable mini format: cost, time, three steps, material list, before
   and after.
5. Use comment prompts that ask for a concrete object or corner, not a generic
   opinion.
6. Keep AI-generated images as mood/reference only; real before/after and
   handcraft evidence should come from actual images.

## Recommended Operating Model

Do not search live high-engagement XHS posts during every content generation
run. The MCP path is useful for research, but it is too slow and unstable to sit
on the ordinary publish path.

Use this operating model instead:

1. Run a bounded collection job on a cadence, such as daily for active lanes or
   weekly for slower lanes.
2. Store raw samples with titles, engagement fields, keyword, identifiers,
   cover dimensions, and collection timestamp.
3. Analyze the raw samples into reusable format patterns:
   - title hook
   - body structure
   - save trigger
   - comment trigger
   - image/carousel sequence
   - examples and source sample IDs
4. Review or auto-approve a small current snapshot for each lane.
5. During generation, read the latest local pattern snapshot and record which
   pattern IDs influenced the artifact.

This keeps generation deterministic and fast while still letting the project
learn from real Xiaohongshu post formats.
