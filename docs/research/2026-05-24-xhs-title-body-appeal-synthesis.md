---
title: XHS Title And Body Appeal Synthesis
status: active
owner: ptsm
last_verified: 2026-05-24
source_of_truth: false
related_paths:
  - docs/plans/2026-05-24-xhs-title-body-appeal.md
  - docs/research/2026-05-15-xhs-content-quality-sample-set.md
  - docs/research/2026-05-17-xhs-live-mcp-sample.md
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
  - src/ptsm/playbooks/definitions
  - src/ptsm/skills/builtin/xhs_human_voice/SKILL.md
  - src/ptsm/infrastructure/llm/factory.py
  - src/ptsm/infrastructure/llm/contextual_drafts.py
---

# XHS Title And Body Appeal Synthesis

## Scope

This note turns the latest user request into a working synthesis for PTSM:

- titles need stronger click appeal without losing the account tone;
- body length should vary by domain, but every domain should avoid bloated posts;
- body organization should be more platform-native and less flat while still carrying required domain elements.

This is not a new market-wide Xiaohongshu benchmark. It combines:

- repository-local XHS samples from 2026-05-15 and 2026-05-17;
- the 2026-05-23 productized hook research;
- a 2026-05-24 attempt to run fresh XHS MCP sampling;
- current public trend summaries and a direct browser-access check.

## 2026-05-24 Fresh Check

I tried to refresh live XHS evidence from the current machine:

```bash
COOKIES_PATH=/Users/wudalu/llm-app/ptsm/cookies/fk-local.json \
  /Users/wudalu/llm-app/ptsm/.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64

uv run python -m ptsm.bootstrap xhs-login-status

uv run python -m ptsm.bootstrap collect-xhs-patterns \
  --lane cross_domain_content_appeal \
  --keywords "发疯文学,情绪管理,反刍思维,人类丰容,普通人用AI,苏轼,每日英语,世界杯看球" \
  --sample-limit-per-keyword 6 \
  --delay-seconds 1.2 \
  --output-dir outputs/artifacts/xhs-cross-domain-content-appeal
```

Result:

- `xhs-login-status` first returned `status: ready` with 13 MCP tools.
- `collect-xhs-patterns` then failed before sampling with `connection timeout`.
- A direct one-keyword `search_feeds("人类丰容")` call returned HTTP 500.
- Browser access to `https://www.xiaohongshu.com/explore` redirected to an IP-risk login error.

So the current fresh-check evidence is about access reliability, not content quality. The new implementation should not depend on live XHS calls during ordinary generation or deterministic tests.

## Evidence Still Usable

Repository-local XHS samples remain useful:

- `docs/research/2026-05-15-xhs-content-quality-sample-set.md` found 117 search candidates and showed that high-interaction rows win through reusable jokes, explicit audience/conflict hooks, cognitive tools, and save/comment triggers. It also identified generic controls such as `当代打工人抽象发疯实录 3.0（玩梗）` and `平静地发疯` as weak because they lack concrete scene, object, or tool.
- `docs/research/2026-05-17-xhs-live-mcp-sample.md` showed human-enrichment hooks such as sudden realization, second-person address, before/after tension, low-cost methods, and concrete comment prompts around corners, materials, and routes.
- `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md` turned these observations into the hook stack: recognizable scene, identity claim, saveable tool, repeatable action, share target, correction space, and comment continuation.

Public 2026 trend summaries support the same direction:

- 千瓜's 2026 XHS hotword report summaries emphasize that trend work is not just chasing hot words, but understanding the concrete people behind them. The listed hotword families include 抽象力, 主体性, 活人感, 边界感, AI人格, 代入感, 文化力, plus signals such as 丝瓜汤 and 爱你老己. Sources: https://itopmarketing.com/info21983 and https://www.163.com/dy/article/KNM0F24K0538PWEU.html
- Public reporting on 小红书's 2026 居住趋势 frames `适我主义` as a shift from standard style templates toward "what fits me", with examples grounded in concrete home decisions and usage scenes. Source: https://news.qq.com/rain/a/20260423A07M7500
- Exa search could access individual XHS share pages, but mostly returned fandom or older notes rather than the requested lanes. That confirms public web search is weak for fresh XHS sampling; PTSM should continue to rely on bounded MCP collection snapshots when the local login is healthy.

## Current PTSM Gap

The system already has strong foundations:

- `xhs_human_voice` exists and blocks format/AI voice.
- Most playbooks require save/comment mechanisms.
- Several contracts already block formulaic cross-field markers.
- Deterministic drafts cover all current XHS domains.

The remaining gap is that the rules are still uneven:

- `modern_psychology_post`, `human_enrichment_daily_post`, and `fengkuang_daily_post` do not declare body length bounds in `evaluation.yaml`.
- Existing length bounds for AI, daily English, World Cup, and Reddit allow bodies up to 750-950 chars, which is longer than the user now wants for most domains.
- Title constraints are partly present, but there is no generic deterministic constraint for substring-level generic title markers such as `实录`, `日常`, `干货分享`, `小红书爆款`, or `今日`.
- The DeepSeek hard-requirements prompt does not translate playbook identity into explicit title/body length and organization requirements.
- Some deterministic drafts are valid but still read like compact explainers: the title/cover/body do not always create a first-screen click reason, a save unit, and a concrete comment handoff as one coordinated object.

## Direction

### Title Rule

Every title should combine at least two of these:

- concrete scene, object, person, relationship, or phrase;
- tension or reversal;
- identity claim;
- saveable utility;
- role-pair or comment invitation.

Avoid pure category labels:

- `打工人日常`
- `职场崩溃实录`
- `心理学小知识`
- `AI科技资讯`
- `每日英语单词`
- `苏轼诗词赏析`
- `小红书爆款`

Implementation implication:

- Add `title_must_not_include_any` to the contract evaluator.
- Configure playbook-local title forbidden markers and domain-specific title hook terms.
- Update `xhs_human_voice` and planner prompts with a title formula that preserves tone.

### Body Rule

Every body should have four visible moves, without section labels unless the domain naturally uses them:

1. **First-screen hook:** a micro-scene, question, contradiction, or exact moment in the first one to two sentences.
2. **Domain substance:** mechanism, cultural reading, tool explanation, match context, word meaning, or discussion observation.
3. **Saveable unit:** one sentence, three steps, mini checklist, template, quote, or frame.
4. **Concrete comment handoff:** ask for an example, line, corner, route, character, expression, tool boundary, or match moment.

Implementation implication:

- Keep existing `body_must_include_comment_prompt_any` and `body_must_include_save_trigger_any`.
- Tighten body length bounds by playbook so "要素齐备" does not become long-form padding.
- Update deterministic drafts and prompt assets so the save/comment units are natural rather than appended.

### Length Bands

Use domain-specific bands:

| playbook | body target | reason |
| --- | ---: | --- |
| `fengkuang_daily_post` | 120-380 chars | A joke/social object should be fast, copyable, and easy to comment on. |
| `modern_psychology_post` | 260-620 chars | Needs micro-scene, mechanism, tool, safety boundary, and comment prompt. |
| `human_enrichment_daily_post` | 180-520 chars | Needs variable + low-cost action, but should stay like a note, not a renovation article. |
| `sushi_poetry_daily_post` | 180-520 chars | Needs one text/life bridge and one saveable reading, not a lecture. |
| `daily_english_post` | 180-520 chars | Needs pronunciation, meaning, example, template, and practice prompt. |
| `ai_tech_daily_post` | 220-650 chars | Needs enough context for utility and boundary, but not a product launch recap. |
| `world_cup_daily_post` | 200-620 chars | Needs fan-readable context, 2-3 watch points, save list, and comment prompt. |
| `reddit_curation_daily_post` | 220-700 chars | Needs to translate a discussion into Chinese-reader value without revealing source. |
| `wuxia_character_post` | 700-1100 chars | This is intentionally the longest domain, but should be a tight argument, not 1500-char sprawl. |

## Acceptance Bar

The change should be considered successful only when:

- every XHS playbook has explicit body min/max bounds;
- title generic substring bans exist and are enforced by tests;
- shared and domain prompt assets explain title/body organization;
- DeepSeek hard requirements include title/body length and hook organization guidance;
- deterministic dry-runs for representative domains produce titles with concrete hooks and bodies within the configured bands;
- docs explain that live XHS sampling was attempted on 2026-05-24 but blocked by MCP/browser access instability, so current implementation relies on local samples and public trend sources.
