---
title: XHS Domain Opportunity And PTSM Workflow Review
status: active
owner: ptsm
last_verified: 2026-05-30
source_of_truth: false
related_paths:
  - docs/xhs-topics/index.md
  - docs/xhs-topics/verticals.md
  - docs/xhs-topics/skills-landscape.md
  - docs/xhs-topics/harness-integration.md
  - docs/playbooks.md
  - docs/skills.md
  - integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
---

# XHS Domain Opportunity And PTSM Workflow Review

## Scope

This review answers three questions:

- Which current PTSM domains look easiest to turn into high-performing XHS posts?
- Which new domains or subdomains are worth adding next?
- What should improve in the skill + PTSM workflow so trend research becomes repeatable rather than manual browsing?

Evidence is intentionally mixed:

- live XHS search-level samples from local `xiaohongshu-mcp` on 2026-05-30;
- existing PTSM topic-radar reports and local XHS research notes from May 2026;
- public trend reports from QianGua and public news sources.

The live sample is search-level evidence only. It did not pull detail pages or comments, and it sampled the first five results per keyword. Treat the absolute engagement values as directional, not as a full platform benchmark.

## Current PTSM Domain Baseline

PTSM currently has nine XHS playbooks:

| playbook | domain | current opportunity read |
| --- | --- | --- |
| `modern_psychology_post` | 现代心理困境观察 | Very high demand around emotion, boundaries, sleep, relationship uncertainty, and factual reframing. Strongest when it gives a saveable tool without diagnosis. |
| `fengkuang_daily_post` | 发疯文学 / 职场情绪 | Still useful, but raw "发疯文学" is saturated. It needs concrete objects, social scripts, and a repair turn. |
| `human_enrichment_daily_post` | 人类丰容 / daily variables | Strong share/save shape and visual-first fit. Best current bridge into handcraft, low-cost repair, and sleep/life routine experiments. |
| `sushi_poetry_daily_post` | 苏轼诗词赏析 | Healthy culture signal, but needs more lanes than 怀民: 黄州自救、赤壁大江、东坡烟火、月亮想念、定风波. |
| `wuxia_character_post` | 武侠人物评述 | Niche and lower search-level heat in this sample. Keep as deep commentary, not a volume-growth domain. |
| `ai_tech_daily_post` | AI / tech / workflow | Public trend support is strong. XHS sample shows utility posts win through collectable workflows rather than model news. |
| `daily_english_post` | 每日英语学习 | High save/share potential when it is a routine, follow-along, or sentence-template post. Crowded but viable. |
| `world_cup_daily_post` | 世界杯 | Highest short-term heat because XHS announced 2026 World Cup rights on 2026-05-28. Very time-sensitive. |
| `reddit_curation_daily_post` | Reddit英文讨论转译 | Useful as a source-differentiated angle, but not itself a visible XHS domain. Best used to feed AI anxiety, workflow, and social observation posts. |

## 2026-05-30 Live XHS Search Probe

Commands attempted:

```bash
uv run python -m ptsm.bootstrap xhs-login-status
uv run python -m ptsm.bootstrap collect-xhs-patterns \
  --lane xhs_domain_opportunity \
  --keywords "人类丰容,修复系手作,普通人用AI,轻养生,睡眠恢复,宠物户外,文博非遗,情绪疗愈,发疯文学,苏轼,武侠,每日英语,世界杯" \
  --sample-limit-per-keyword 5 \
  --delay-seconds 0.8 \
  --output-dir outputs/artifacts/xhs-domain-opportunity-2026-05-30
```

`xhs-login-status` eventually returned `status: ready`, but `collect-xhs-patterns` failed in login preflight because the MCP `check_login_status` call repeatedly took about 19 seconds and sometimes returned 500. A one-off read-only probe then skipped the preflight and called `search_feeds` directly with a 70 second timeout.

The score below follows PTSM topic-radar's existing search-level engagement formula:

`score = likes + comments * 4 + collects * 2 + shares * 6`

| keyword | strongest sample title | top score | signal read |
| --- | --- | ---: | --- |
| 世界杯 | 小红书成为2026年美加墨世界杯持权转播商！ | 507601 | Massive immediate platform-event heat. Time-sensitive, not evergreen. |
| 情绪疗愈 | 跳过情绪，看见事实。 | 135047 | Strongest evergreen emotional/tool signal. Needs safety and non-diagnosis. |
| 睡眠恢复 | 睡觉大于天 睡觉是成本最低收益最高的投资 | 36068 | Very strong, save/share heavy, suitable for a new recovery/wellness line. |
| 轻养生 | 夏日100件轻养生小事清单丨养出健康好气韵~ | 26145 | Very strong checklist format; overlaps sleep, office health, low-cost routines. |
| 每日英语 | 英语跟读第14期：我需要的是更好的自己！ | 20834 | Strong collectable learning routine. Existing playbook can keep improving. |
| 文博非遗 | 44项！中国世界非遗总数世界第一！收藏 | 14197 | Good culture/save signal. Better as culture/outing lane than standalone first. |
| 人类丰容 | 人，你该“丰容”了! | 11850 | Strong share signal and exact match to existing human enrichment. |
| 苏轼 | 苏轼的十首豁达之作，你最喜欢哪一首？ | 9317 | Strong culture evergreen. Needs topic breadth and comment-role hooks. |
| 修复系手作 | 文物修复师—— i人最理想的工作 | 6563 | Strong but search results skew to文物修复 jobs; handcraft repair needs better queries. |
| 发疯文学 | 笑死了哈哈哈哈哈… | 5077 | Still works as humor, but generic query is noisy. Must anchor in scenes/objects. |
| 普通人用AI | 我是如何深度使用 AI 的 | 5053 | Useful workflow signal; stronger with specific tool/task queries. |
| 宠物户外 | 广东省内带狗去哪玩-宠物友好汇总帖 | 2435 | Moderate but highly practical and visual. Needs real pet/travel asset supply. |
| 武侠 | 你读过最江湖味的一句诗【诗念诗词】 | 795 | Lowest in this probe. Keep as niche depth rather than growth bet. |

## Public Trend Support

- QianGua's 2026 XHS hotword report lists 抽象力、主体性、活人感、边界感、AI人格、代入感、文化力 and says the key is reading the concrete people behind hotspots, not only chasing hot words: <https://www.qian-gua.com/information/detail/3318>
- QianGua's handcraft report says 钩织 has moved into broader daily scenarios, with related topic traffic above 30B and related note count up 8400%+ after an official activity: <https://www.qian-gua.com/information/detail/3322>
- QianGua's health report frames XHS health as a broader life attitude, with monthly estimated interaction around 300M+ in health daily content: <https://www.qian-gua.com/information/detail/3277>
- QianGua's sleep-scene report says sleep content spans smell, sound, touch, light, sleep ritual, and gentle exercise, not only "help me sleep" products: <https://www.qian-gua.com/information/detail/3269>
- QianGua's 2026 Q1 hotspot report says AI is becoming a "life companion" rather than only a cold tool: <https://www.qian-gua.com/Home/ArticleDetail?id=3324>
- On 2026-05-28, public reports said XHS announced it became a 2026 FIFA World Cup rights holder and CCTV strategic live-event partner: <https://cn.chinadaily.com.cn/a/202605/28/WS6a17a532a310942cc49aeadc.html>

## Opportunity Ranking

### Tier 1: act now

1. **轻养生 / 睡眠恢复 / 办公室恢复**
   This is the clearest new-domain candidate. The live probe produced multiple high-score, save-heavy posts, and public trend support is strong. It has repeatable formats: sleep experiments, summer health lists, office recovery, body signal checklists, and micro-routines.

2. **情绪疗愈 / 现代心理 tools**
   This is already covered by `modern_psychology_post`, but the live score is too strong to ignore. Keep it inside psychology because safety boundaries matter. Push the domain toward factual reframing, body grounding, relationship uncertainty, and sleep-adjacent recovery rather than mechanism-first psychology explainers.

3. **世界杯**
   Short-term opportunity is exceptional because XHS itself just became a World Cup rights holder. PTSM already has `world_cup_daily_post`; the next move is a rapid content calendar, not a new domain. It should emphasize watch guides, sleep-friendly viewing, fan rituals, and platform-native discussion while still avoiding betting and score-prediction claims.

### Tier 2: invest as sublanes first

4. **人类丰容 + 修复系手作**
   Keep under `human_enrichment_daily_post` first. It has strong visual shape and can absorb handcraft, low-cost repair, desk/bedside/commute variables, and material-process posts.

5. **苏轼 / 文博非遗 / culture experience**
   Keep under `sushi_poetry_daily_post` and expand lanes. The current code changes that add 黄州、赤壁、东坡烟火、中秋月亮 and negated keyword handling are aligned with this evidence.

6. **AI workflow**
   Keep `ai_tech_daily_post`, but optimize for one task, one workflow, and one boundary. Public trend support is stronger than the generic live keyword score.

7. **每日英语**
   Keep improving as a saveable routine and follow-along domain. It is crowded but structurally fit for PTSM because deterministic evals can check examples, comment prompts, and title specificity.

### Tier 3: keep, but do not expand first

8. **宠物户外**
   Viable only if the operator can supply real routes, pet photos, or product/testing context. Without that, PTSM risks producing generic route lists.

9. **发疯文学**
   Keep as a persona and emotion outlet. Do not scale raw "发疯文学"; scale concrete object scripts and "崩溃 -> 修复" arcs.

10. **武侠**
   Keep as a niche commentary domain. It can create loyal depth, but the search-level signal does not justify prioritizing new runtime investment.

## Recommended Additions

### 1. Add a light wellness / sleep recovery domain

Recommended playbook shape:

- id: `light_wellness_daily_post` or `sleep_recovery_daily_post`
- account: a separate local account if real operation is planned; otherwise begin as lanes in psychology and human enrichment
- core lanes: sleep reset, office recovery, summer light wellness, phone-off wind-down, micro movement, food/drink boundary, body signal check
- image forms: iPhone notes checklist, bedside/desk scene, low-text routine card
- safety: no diagnosis, no treatment promises, no supplement/medical claims, redirect severe or persistent insomnia to professional help

This should be implemented as a new domain only if the user wants a sustained account line. Otherwise, make it a cross-domain guide-post sublane first.

### 2. Treat handcraft repair as a human-enrichment subseries

Do not add a full playbook yet. Improve `human_enrichment_daily_post` topic pack with:

- material-process lane
- repair / old-object renewal lane
- commute or bedside handcraft lane
- image recommendation defaulting to provider/real visual evidence, not dense text cards

### 3. Treat culture/local experience as a Sushi + enrichment bridge

Do not add a full 文博/非遗 playbook yet. Add more guidance lanes under Sushi and human enrichment:

- local exhibition / county walk / small museum
- non-heritage "one object, one season" culture note
- Su Shi text connected to a route, food, or seasonal object

### 4. Keep pet outdoors as a later optional domain

Only add it if the operator can collect authentic route/equipment/pet context. It is a better commerce/community domain than a generic PTSM writing-only domain.

## Workflow Findings

### What is working

- `guide-post` is the right front door. It forces a direction choice before generation and keeps raw research/provenance out of the user-facing response.
- The OpenClaw skills are correctly thin wrappers. They call PTSM guidance first and do not duplicate topic logic.
- Topic packs are local and deterministic, which keeps normal generation stable even when live XHS access is slow or blocked.
- The `xhs_human_voice` and playbook-local eval contracts already push posts toward concrete hooks, saveable units, and comment handoffs.

### What should improve

1. **MCP timeout behavior**
   `collect-xhs-patterns` currently fails before sampling when `check_login_status` is slow. Today's direct `search_feeds` probe worked with a 70 second timeout. The collection use case should support configurable login/search timeouts and persist partial evidence even when login preflight is slow.

2. **Domain opportunity should become a first-class artifact**
   Today this analysis required an ad hoc script. PTSM should expose a `xhs-domain-opportunity` or `xhs-topic-scan --mode domain-opportunity` command that:
   - accepts candidate domains and keywords;
   - collects bounded search-level samples;
   - computes engagement summary with the existing score formula;
   - maps each keyword to current playbooks or new-domain candidates;
   - writes a JSON artifact and a Markdown brief.

3. **Vertical routing should happen inside PTSM, not OpenClaw skills**
   The OpenClaw wrapper should not learn all future domains. PTSM should own a `xhs_vertical_router` or equivalent application use case that maps "sleep recovery", "pet outdoors", "文博非遗" and similar scenes to:
   - existing playbook;
   - candidate sublane;
   - new-domain recommendation;
   - safety or asset requirements.

4. **Non-psychology guidance confirmation should be observable**
   Psychology has a hard `--guidance-ack` runtime gate. Non-psychology wrapper guidance is currently a convention, not a runtime fact. It does not need to block all calls, but `run-playbook` should be able to receive a confirmed `topic_direction_id` and write it into the artifact. That would make "skill + PTSM workflow" auditable.

5. **Research evidence age should be visible to operators**
   `guide-post` output should continue hiding raw sources from end users, but operator-facing JSON can include an internal evidence freshness field such as `evidence_level: local_pack | pattern_snapshot | live_scan` and `evidence_collected_at`. This prevents old static packs from looking like fresh platform evidence.

## Recommended Next Plan

Implement in two tracks:

1. **Short track:** finish and verify the current Sushi breadth change, then update docs so Sushi is no longer described as 怀民-default.
2. **Main track:** build a domain-opportunity research surface and decide whether to add `light_wellness_daily_post` as a real tenth playbook or first as a cross-domain sublane.

The next major implementation should start in an isolated worktree because adding a new domain or research use case touches runtime, docs, tests, and harness surfaces.
