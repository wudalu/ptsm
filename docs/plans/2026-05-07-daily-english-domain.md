# Daily English Learning Domain Implementation Plan

**Date:** 2026-05-07
**Status:** in-progress

## Goal

Add the 每日英语学习 (Daily English Learning) vertical domain as specified in PRD.md
section "3. 每日英语学习账号策略".

## Scope

- New playbook: `daily_english_post`
- New account: `acct-daily-english-local`
- New skills: `daily_english_style`, `daily_english_hashtagging`
- Docs update: `docs/playbooks.md`, `docs/skills.md`

## Non-goals

- No runtime code changes (registry auto-discovers new files)
- No learning progress tracking (P3 feature per PRD)
- No interactive exercises (P3 feature per PRD)
- No WeChat/Bilibili platform support (P3 feature per PRD)

## Architecture

Follow the established additive pattern: add definition files only, no changes to
existing runtime, infrastructure, or playbook/skill registry code. The
PlaybookRegistry, AccountRegistry, and SkillRegistry all auto-discover from their
respective directories.

## Tech Stack

Same as existing domains: YAML definitions, markdown assets, LangGraph runtime.

---

### Task 1: Create playbook definition

**Files to create:**
- `src/ptsm/playbooks/definitions/daily_english_post/playbook.yaml`
- `src/ptsm/playbooks/definitions/daily_english_post/planner.md`
- `src/ptsm/playbooks/definitions/daily_english_post/persona.md`
- `src/ptsm/playbooks/definitions/daily_english_post/reflection.md`

**verify:**
```bash
uv run python -c "
from pathlib import Path
from ptsm.playbooks.registry import PlaybookRegistry
r = PlaybookRegistry(Path('src/ptsm/playbooks/definitions'))
pb = r.get('daily_english_post')
assert pb.domain == '每日英语学习'
assert pb.platforms == ['xiaohongshu']
print('OK')
"
```

**done_when:** playbook loads via registry and all 4 fields match PRD spec

### Task 2: Create account definition

**Files to create:**
- `src/ptsm/accounts/definitions/acct-daily-english-local.yaml`

**verify:**
```bash
uv run python -c "
from ptsm.accounts.registry import AccountRegistry
acct = AccountRegistry().get('acct-daily-english-local')
assert acct.domain == '每日英语学习'
assert acct.platform == 'xiaohongshu'
print('OK')
"
```

**done_when:** account loads via registry

### Task 3: Create skills

**Files to create:**
- `src/ptsm/skills/builtin/daily_english_style/SKILL.md`
- `src/ptsm/skills/builtin/daily_english_hashtagging/SKILL.md`

**verify:**
```bash
uv run python -c "
from pathlib import Path
from ptsm.skills.registry import SkillRegistry
r = SkillRegistry(Path('src/ptsm/skills/builtin'))
names = {s.skill_name for s in r.list_skills()}
assert 'daily_english_style' in names
assert 'daily_english_hashtagging' in names
# Check domain_tags prevent cross-domain leakage
style = next(s for s in r.list_skills() if s.skill_name == 'daily_english_style')
assert '每日英语学习' in style.domain_tags
print('OK')
"
```

**done_when:** both skills discoverable with correct domain_tags

### Task 4: Add tests

**Files to modify:**
- `tests/unit/playbooks/test_playbook_registry.py` — add test for daily_english_post
- `tests/unit/accounts/test_account_registry.py` — add test for acct-daily-english-local
- `tests/unit/skills/test_skill_registry.py` — add tests for daily English skills

**verify:**
```bash
uv run pytest -q tests/unit/playbooks/test_playbook_registry.py \
  tests/unit/accounts/test_account_registry.py \
  tests/unit/skills/test_skill_registry.py
```

**done_when:** all new tests pass

### Task 5: Update source-of-truth docs

**Files to modify:**
- `docs/playbooks.md` — list daily_english_post
- `docs/skills.md` — list daily_english_style, daily_english_hashtagging

**verify:**
```bash
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
```

**done_when:** docs-sync passes

### Task 6: End-to-end dry-run and harness gate

**verify:**
```bash
# Full test suite
uv run pytest -q

# Dry-run the new playbook
uv run python -m ptsm.bootstrap run-playbook \
  --scene "今日单词学习" \
  --account-id acct-daily-english-local \
  --playbook-id daily_english_post

# Harness gate
uv run python -m ptsm.bootstrap harness-check --strict
```

**done_when:** all tests pass, dry-run completes with status=completed, harness gate passes
