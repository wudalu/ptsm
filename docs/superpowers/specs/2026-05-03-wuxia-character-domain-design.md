# Wuxia Character Commentary Domain Design

**Date:** 2026-05-03
**Status:** draft

## Goal

Add a 武侠人物评述 (Wuxia Character Commentary) domain to PTSM. Long-form Xiaohongshu posts analyzing Jin Yong/Gu Long characters through a contemporary pop-culture lens, starting with Jin Yong.

## Design Principle

**Add files, don't modify existing ones.** No changes to runtime nodes, existing playbooks, existing skills, or infrastructure code. New behavior is injected through extension points.

## What We're Building

### New Files (all additive)

```
src/ptsm/playbooks/definitions/wuxia_character_post/
  playbook.yaml        # domain: 武侠人物评述, required_skills, reflection rules
  planner.md           # long-form character analysis constraints
  persona.md           # C-style voice: pop-culture lens + genuine reader credibility
  reflection.md        # checks: character name, original text quote, contemporary hook

src/ptsm/skills/builtin/wuxia_commentary_style/
  SKILL.md             # style rules for C+B blend

src/ptsm/skills/builtin/xhs_wuxia_hashtagging/
  SKILL.md             # hashtags: #武侠 #金庸 #[人物名] #[当代切口]

src/ptsm/accounts/definitions/acct-wuxia-local.yaml
                       # account_id: acct-wuxia-local, domain: 武侠人物评述

tests/unit/skills/test_wuxia_skills.py
tests/unit/playbooks/test_wuxia_playbook.py
tests/e2e/test_wuxia_publish_dry_run.py
```

### One Extension Point: Domain Keyword Registry

`_derive_keywords` currently hardcodes domain checks (`domain == "发疯文学"`). To support new domains without adding more hardcoded branches, add a module-level registry dict that new domains can register into at import time:

```python
# runtime_context.py
_DOMAIN_SEARCH_KEYWORDS: dict[str, list[str]] = {}

def register_domain_keywords(domain: str, keywords: list[str]) -> None:
    _DOMAIN_SEARCH_KEYWORDS[domain] = keywords
```

Wuxia skills call `register_domain_keywords("武侠人物评述", ["金庸群侠", "武侠人物", "令狐冲 性格", "射雕英雄传 人物"])` at import time. `_derive_keywords` checks this registry first before falling through to existing hardcoded logic.

**This is the only change to an existing file.** It replaces an if-chain with a registry lookup — existing domains continue working identically.

## Playbook Design

### playbook.yaml

```yaml
playbook_id: wuxia_character_post
version: 1
domain: 武侠人物评述
platforms:
  - xiaohongshu
required_skills:
  - xhs_trend_scan
  - wuxia_commentary_style
  - xhs_wuxia_hashtagging
optional_skills: []
reflection:
  required_hashtag: "#金庸"
  must_include_phrase: ""
```

### planner.md

Target: Write a long-form (800-1500 words) Xiaohongshu post analyzing a Jin Yong/Gu Long character through a contemporary lens.

Requirements:
1. Open with a specific, relatable contemporary situation that mirrors the character's dilemma.
2. Name the character and novel early. Quote at least one original passage as evidence.
3. Draw a clear parallel between the character's situation and a modern reader's experience (workplace, relationships, self-growth, societal pressure).
4. Voice: personal, opinionated, conversational. Write like someone who's read the books deeply but talks like a friend over drinks.
5. Closing: a punchy insight that makes the reader want to save or share.
6. Output: title, image_text, body (800-1500 words), hashtags.

### persona.md

You're a seasoned wuxia reader who also lives in the real world. Not a scholar, not a wiki editor.

1. Lead with a contemporary hook — a workplace dynamic, a social dilemma, a life choice — then arrive at the character.
2. Have opinions. Dare to say "黄蓉其实是金庸宇宙里最被低估的 CEO" or "令狐冲是古代版职场自由人".
3. Back opinions with original text quotes, not vague summaries. One precise quote per post.
4. Tone: smart but not pedantic, passionate but not ranty. Like a long WeChat message from a well-read friend.
5. No AI listicle structure. No "首先/其次/最后". No generic "告诉我们一个道理".
6. Title should feel like a hot take from a human, not a search result.

### reflection.md

Checklist:
1. Does the post name a specific Jin Yong/Gu Long character and novel?
2. Does it include at least one original text quote?
3. Does it draw a clear contemporary parallel that a non-wuxia reader could relate to?
4. Is the body between 800-1500 words?
5. Does the hashtags contain the required domain tag?
6. If any of 1-3 fail, require rewrite.

## Skill Design

### wuxia_commentary_style (SKILL.md)

```markdown
---
skill_name: wuxia_commentary_style
display_name: Wuxia Commentary Style
description: 用当代流行文化视角评述金庸古龙小说人物，有原文功底、有主观辣评、有现代共鸣。
display_order: 50
domain_tags: 武侠人物评述
platform_tags: xiaohongshu
playbook_tags: wuxia_character_post
token_budget_hint: 220
assets_present: false
---

# Wuxia Commentary Style

When writing wuxia character commentary:

1. Pick ONE contemporary lens per post (职场, 亲密关系, 成长焦虑, 边缘感, ...).
2. Quote at least one original passage — precise, not paraphrased.
3. Voice: a seasoned reader with opinions, not a lecturer.
4. Make the character feel relevant to someone who's never read wuxia.
5. Closing insight should be sticky — the kind readers screenshot and share.
```

### xhs_wuxia_hashtagging (SKILL.md)

```markdown
---
skill_name: xhs_wuxia_hashtagging
display_name: XHS Wuxia Hashtagging
description: 为武侠人物评述长文生成小红书标签组合。
display_order: 60
domain_tags: 武侠人物评述
platform_tags: xiaohongshu
playbook_tags: wuxia_character_post
token_budget_hint: 100
assets_present: false
---

# XHS Wuxia Hashtagging

For wuxia character posts:

1. Always include domain tag #金庸 or #古龙 based on the author.
2. Include the character name as a tag: #令狐冲, #黄蓉, etc.
3. Include the contemporary lens tag: #职场隐喻, #女性成长, #边缘人格, etc.
4. Include 1-2 platform discovery tags: #武侠, #读书笔记, #人物评述.
5. 5-7 tags total. Natural language, not SEO stuffing.
```

## Account Design

```yaml
account_id: acct-wuxia-local
nickname: 武侠人物深度评述
platform: xiaohongshu
domain: 武侠人物评述
publish_mode: dry-run
```

## Image Generation

No code changes needed. The existing `_build_image_generation_prompt` already injects `persona_prompt` and `runtime_skill_contents`. The wuxia persona will carry the visual aesthetic ("封面要像读书博主的深度内容配图，有古风意境但不像课本插图").

## Reflection Rules

The current reflector hardcodes two checks:
```python
required_hashtag = rules["required_hashtag"]
required_phrase = rules["must_include_phrase"]
passed = required_hashtag in draft["hashtags"] and required_phrase in body
```

For wuxia, the character name varies per scene (令狐冲 one day, 黄蓉 the next) — can't hardcode it in playbook.yaml. And we don't want to modify `reflector.py`.

**Decision:**
- `required_hashtag: "#金庸"` — static, valid hard check ✅
- `must_include_phrase: ""` — empty string always passes the hard check
- Soft constraints (character name, original quote, contemporary hook) are enforced by the persona + planner prompts at the LLM level — the real quality gate

The reflector is a catch-fail safety net, not the primary quality enforcer. The LLM with well-written prompts is the real enforcement for content quality rules.

## Excluded (YAGNI)

- No content_format enum or schema changes
- No new CLI commands (uses `run-playbook`)
- No new image backend or prompt logic
- No database or persistence changes
- No new LangGraph nodes or state fields
- Gu Long support is just a different scene prompt — same playbook, different author tag

## Testing Strategy

1. **Unit:** registry/selector recognize wuxia skills and playbook
2. **Integration:** dry-run produces long-form body with character name, quote, contemporary hook
3. **E2E:** full `run-playbook` dry-run with scene "分析令狐冲的自由人格与当代职场"
4. **Architecture:** no boundary violations from new files

## Implementation Order

1. Update `_derive_keywords` with extensible registry (one existing-file change)
2. Create account definition
3. Create playbook definition (yaml + planner/persona/reflection)
4. Create two builtin skills (SKILL.md)
5. Register wuxia keywords at skill import time
6. Dry-run test
7. E2E real publish test
8. Update docs (playbooks.md, skills.md, local-runbook.md)
