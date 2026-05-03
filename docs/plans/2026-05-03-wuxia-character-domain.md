# Wuxia Character Commentary Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 武侠人物评述 domain — long-form Xiaohongshu posts analyzing Jin Yong/Gu Long characters through a contemporary pop-culture lens. Add files only, no changes to existing runtime nodes.

**Architecture:** The platform is already generalized (generic CLI, generic runtime, generic drafting backend). This is a pure vertical-slice addition: playbook + 2 skills + account, same pattern as sushi_poetry_daily_post. One extension point: add `trend_keywords` to playbook.yaml and thread it through the keyword derivation so new domains control their own hotspot search terms without hardcoding.

**Tech Stack:** YAML playbook/skill/account definitions, markdown prompts, existing pytest harness, existing DeepSeek drafting backend, existing Jimeng image gen.

---

### Task 1: Add trend_keywords Extension Point

**Files:**
- Modify: `src/ptsm/playbooks/registry.py:11-22` — PlaybookDefinition dataclass
- Modify: `src/ptsm/playbooks/registry.py:64-80` — _load_playbooks parsing
- Modify: `src/ptsm/skills/runtime_context.py:25-29` — RuntimeContextBuilder Protocol
- Modify: `src/ptsm/skills/runtime_context.py:47-72` — SkillContextResolver.resolve
- Modify: `src/ptsm/skills/runtime_context.py:75-97` — XhsTrendScanContextBuilder
- Modify: `src/ptsm/skills/runtime_context.py:144-171` — _derive_keywords

```yaml
verify:
  - uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/playbooks/test_playbook_registry.py -q
done_when:
  - PlaybookDefinition accepts optional trend_keywords: list[str], default empty
  - playbook.yaml can include `trend_keywords:` list (backwards-compatible, existing playbooks unchanged)
  - _derive_keywords prepends trend_keywords hints to derived keywords when provided
  - existing keyword derivation for 发疯文学 and 苏轼诗词赏析 is unchanged
```

- [ ] **Step 1: Add trend_keywords to PlaybookDefinition**

In `src/ptsm/playbooks/registry.py`, add the field:

```python
@dataclass(frozen=True)
class PlaybookDefinition:
    """Structured playbook definition loaded from YAML."""

    playbook_id: str
    version: str
    domain: str
    platforms: list[str]
    required_skills: list[str]
    optional_skills: list[str] = field(default_factory=list)
    reflection: dict[str, str] = field(default_factory=dict)
    trend_keywords: list[str] = field(default_factory=list)  # ← new
    source_path: Path | None = None
```

In `_load_playbooks`, parse the new field:

```python
def _load_playbooks(self) -> list[PlaybookDefinition]:
    playbooks: list[PlaybookDefinition] = []
    for path in sorted(self.playbook_root.rglob("playbook.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        playbooks.append(
            PlaybookDefinition(
                playbook_id=payload["playbook_id"],
                version=str(payload["version"]),
                domain=payload["domain"],
                platforms=list(payload["platforms"]),
                required_skills=list(payload["required_skills"]),
                optional_skills=list(payload.get("optional_skills", [])),
                reflection=dict(payload.get("reflection", {})),
                trend_keywords=list(payload.get("trend_keywords", [])),  # ← new
                source_path=path,
            )
        )
    return playbooks
```

- [ ] **Step 2: Add keyword_hints to RuntimeContextBuilder Protocol**

In `src/ptsm/skills/runtime_context.py`, update the Protocol:

```python
class RuntimeContextBuilder(Protocol):
    """Build dynamic skill context for a planner pass."""

    def build(self, *, scene: str, domain: str, playbook_id: str, keyword_hints: list[str] | None = None) -> str | None:
        """Return dynamic context text or `None` when unavailable."""
```

- [ ] **Step 3: Thread keyword_hints through SkillContextResolver.resolve**

In `src/ptsm/skills/runtime_context.py`, update `resolve`:

```python
def resolve(
    self,
    *,
    state: dict[str, Any],
    playbook: PlaybookDefinition,
    loaded_skills: Sequence[LoadedSkill],
) -> dict[str, str]:
    contexts: dict[str, str] = {}
    keyword_hints = list(playbook.trend_keywords) if playbook.trend_keywords else None
    for loaded_skill in loaded_skills:
        builder = self._builders.get(loaded_skill.skill.skill_name)
        if builder is None:
            continue
        context = builder.build(
            scene=state["scene"],
            domain=playbook.domain,
            playbook_id=playbook.playbook_id,
            keyword_hints=keyword_hints,
        )
        if context:
            contexts[loaded_skill.skill.skill_name] = context
    return contexts
```

- [ ] **Step 4: Thread keyword_hints through XhsTrendScanContextBuilder**

```python
def build(self, *, scene: str, domain: str, playbook_id: str, keyword_hints: list[str] | None = None) -> str | None:
    try:
        return asyncio.run(
            self._build_async(scene=scene, domain=domain, playbook_id=playbook_id, keyword_hints=keyword_hints)
        )
    except RuntimeError as exc:
        if "asyncio.run()" in str(exc):
            raise
        return None
    except Exception:
        return None

async def _build_async(
    self,
    *,
    scene: str,
    domain: str,
    playbook_id: str,
    keyword_hints: list[str] | None = None,
) -> str | None:
    tool_names = await self.tool_runner.list_tool_names()
    if "check_login_status" not in tool_names or "search_feeds" not in tool_names:
        return None

    login_payload = await self.tool_runner.invoke_tool("check_login_status", {})
    login_text = _extract_text(login_payload).strip()
    if "已登录" not in login_text or "未登录" in login_text:
        return None

    keywords = _derive_keywords(scene=scene, domain=domain, playbook_id=playbook_id, hints=keyword_hints)
    ...
```

- [ ] **Step 5: Add hints parameter to _derive_keywords**

```python
def _derive_keywords(*, scene: str, domain: str, playbook_id: str, hints: list[str] | None = None) -> list[str]:
    keywords: list[str] = []
    if hints:
        keywords.extend(hints)
    day_token = next((token for token in _WEEKDAY_TOKENS if token in scene), None)
    is_work_scene = any(cue in scene for cue in _WORK_CUES) or domain == "发疯文学"
    is_poetry_scene = any(cue in scene for cue in _POETRY_CUES) or domain == "苏轼诗词赏析"
    # ... rest unchanged
```

- [ ] **Step 6: Run existing tests to verify no regression**

```bash
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/playbooks/test_playbook_registry.py -q
```

Expected: PASS — existing fengkuang and sushi playbooks have no `trend_keywords` field, default to empty list, behavior unchanged.

- [ ] **Step 7: Commit**

```bash
git add src/ptsm/playbooks/registry.py src/ptsm/skills/runtime_context.py
git commit -m "feat: add trend_keywords extension point for domain-specific hotspot search"
```

---

### Task 2: Add wuxia_character_post Vertical Slice

**Files:**
- Create: `src/ptsm/accounts/definitions/acct-wuxia-local.yaml`
- Create: `src/ptsm/playbooks/definitions/wuxia_character_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/wuxia_character_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/wuxia_character_post/persona.md`
- Create: `src/ptsm/playbooks/definitions/wuxia_character_post/reflection.md`
- Create: `src/ptsm/skills/builtin/wuxia_commentary_style/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_wuxia_hashtagging/SKILL.md`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`
- Modify: `tests/integration/test_playbook_selection.py`

```yaml
verify:
  - uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/integration/test_playbook_selection.py -q
done_when:
  - PlaybookRegistry can load wuxia_character_post
  - acct-wuxia-local selects the wuxia playbook on xiaohongshu
  - skill selector exposes wuxia_commentary_style and xhs_wuxia_hashtagging for this playbook
  - planner, persona, reflection markdown assets are loadable through PlaybookLoader
```

- [ ] **Step 1: Write failing registry and selector tests**

In `tests/unit/playbooks/test_playbook_registry.py`, add:

```python
def test_registry_loads_wuxia_playbook():
    registry = PlaybookRegistry(playbook_root=PLAYBOOK_ROOT)
    playbook = registry.get("wuxia_character_post")
    assert playbook.domain == "武侠人物评述"
    assert "xiaohongshu" in playbook.platforms
    assert "wuxia_commentary_style" in playbook.required_skills
    assert "xhs_wuxia_hashtagging" in playbook.required_skills
    assert playbook.trend_keywords == ["金庸群侠", "武侠人物", "令狐冲 性格分析", "射雕英雄传 人物"]


def test_registry_selects_wuxia_by_account():
    registry = PlaybookRegistry(playbook_root=PLAYBOOK_ROOT)
    account = AccountProfile(
        account_id="acct-wuxia-local",
        nickname="武侠人物深度评述",
        platform="xiaohongshu",
        domain="武侠人物评述",
    )
    playbook = registry.select_for_account(account=account)
    assert playbook.playbook_id == "wuxia_character_post"
```

In `tests/unit/skills/test_skill_registry.py`, add:

```python
def test_registry_discovers_wuxia_skills():
    registry = SkillRegistry(skill_root=SKILL_ROOT)
    skill_names = {skill.skill_name for skill in registry.list_skills()}
    assert "wuxia_commentary_style" in skill_names
    assert "xhs_wuxia_hashtagging" in skill_names


def test_wuxia_skills_have_correct_tags():
    registry = SkillRegistry(skill_root=SKILL_ROOT)
    skills = {skill.skill_name: skill for skill in registry.list_skills()}
    commentary = skills["wuxia_commentary_style"]
    assert "武侠人物评述" in commentary.domain_tags
    assert "wuxia_character_post" in commentary.playbook_tags
```

In `tests/unit/skills/test_selector.py`, add:

```python
def test_selector_exposes_wuxia_skills():
    registry = SkillRegistry(skill_root=SKILL_ROOT)
    loader = SkillLoader(registry)
    selector = SkillSelector(registry=registry, loader=loader)
    surface = selector.select(
        domain="武侠人物评述",
        platform="xiaohongshu",
        playbook_id="wuxia_character_post",
    )
    skill_names = {skill.skill_name for skill in surface.list_summaries()}
    assert "wuxia_commentary_style" in skill_names
    assert "xhs_wuxia_hashtagging" in skill_names
    assert "xhs_trend_scan" in skill_names  # platform-scoped
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py -q -k "wuxia"
```

Expected: FAIL — wuxia playbook, skills, and account do not exist yet.

- [ ] **Step 3: Create account definition**

`src/ptsm/accounts/definitions/acct-wuxia-local.yaml`:

```yaml
account_id: acct-wuxia-local
nickname: 武侠人物深度评述
platform: xiaohongshu
domain: 武侠人物评述
publish_mode: dry-run
```

- [ ] **Step 4: Create playbook.yaml**

`src/ptsm/playbooks/definitions/wuxia_character_post/playbook.yaml`:

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
  must_include_phrase: ""
  required_hashtag: "#金庸"
trend_keywords:
  - 金庸群侠
  - 武侠人物
  - 令狐冲 性格分析
  - 射雕英雄传 人物
```

- [ ] **Step 5: Create planner.md**

`src/ptsm/playbooks/definitions/wuxia_character_post/planner.md`:

```markdown
# 武侠人物评述 Planner

目标：围绕金庸小说中的一个人物，写一篇适合小红书的长文评述（800-1500字），用当代视角重新解读。

要求：

1. 必须以一个当代生活场景或困境切入（如职场、人际关系、成长焦虑），再接到武侠人物。
2. 必须明确点出人物姓名和出处（哪部小说），至少引用一段原文。
3. 当代视角要清晰可辨：这个人物在今天是什么处境？对应什么人群？
4. 语气：有观点的资深读者，不是百科词条，不是论文。
5. 结尾要有一个能引发收藏欲的观点收束。
6. 输出结构：标题、封面文案、正文（800-1500字）、标签。
```

- [ ] **Step 6: Create persona.md**

`src/ptsm/playbooks/definitions/wuxia_character_post/persona.md`:

```markdown
# 武侠人物评述 Persona

你是一个读过金庸古龙多年的资深读者，也是一个活在当代世界里的普通人。你不是学者，不是百科编辑。

1. 先用当代话题切口（职场、社交、成长困境）引入，再落到人物。
2. 有观点、敢辣评。可以说"黄蓉是金庸宇宙里最被低估的CEO"，但要拿原文佐证。
3. 每篇至少引用一段原文——精准、不曲解、不过度堆砌。
4. 语气：像给朋友发一条长微信，聪明但不卖弄，有热情但不咆哮。
5. 不要AI腔。不要"首先/其次/最后"。不要"告诉我们一个道理"。
6. 标题要有热感有态度，像一个真实的人发的，不像是搜索结果。
7. 封面要像读书博主的深度内容配图，有古风意境但不像课本插图。
```

- [ ] **Step 7: Create reflection.md**

`src/ptsm/playbooks/definitions/wuxia_character_post/reflection.md`:

```markdown
# 武侠人物评述 Reflection

检查标准：

1. 是否明确提到了金庸/古龙人物姓名和出处小说。
2. 是否至少引用了一段原文。
3. 是否有清晰的当代视角勾连（非武侠读者也能产生共鸣）。
4. 正文字数是否在800-1500字区间。
5. 标签是否包含 `#金庸` 或 `#古龙` 的领域标签。
6. 如果不满足第 1、2、3 条，必须要求重写。
```

- [ ] **Step 8: Create wuxia_commentary_style skill**

`src/ptsm/skills/builtin/wuxia_commentary_style/SKILL.md`:

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

在武侠人物评述长文中：

1. 每篇只选一个当代视角切口（职场、亲密关系、边缘感、成长焦虑...）。
2. 至少引用一段原文——精确到句，不要含糊其辞。
3. 语气：像一个读过很多但愿意好好说话的老读者，不是老师。
4. 让一个没读过武侠的人也能被这个人物触动。
5. 收尾要有金句感——让人想截图转发的那种。
```

- [ ] **Step 9: Create xhs_wuxia_hashtagging skill**

`src/ptsm/skills/builtin/xhs_wuxia_hashtagging/SKILL.md`:

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

在武侠人物评述帖子中：

1. 必须包含领域标签 `#金庸` 或 `#古龙`。
2. 包含人物名标签：`#令狐冲`、`#黄蓉` 等。
3. 包含当代视角标签：`#职场隐喻`、`#女性成长`、`#边缘人格` 等。
4. 补充 1-2 个发现类标签：`#武侠`、`#读书笔记`、`#人物评述`。
5. 共 5-7 个标签，像人写的，不像SEO堆砌。
```

- [ ] **Step 10: Run tests to verify they pass**

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/integration/test_playbook_selection.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/ptsm/accounts/definitions/acct-wuxia-local.yaml \
        src/ptsm/playbooks/definitions/wuxia_character_post \
        src/ptsm/skills/builtin/wuxia_commentary_style \
        src/ptsm/skills/builtin/xhs_wuxia_hashtagging \
        tests/unit/playbooks/test_playbook_registry.py \
        tests/unit/skills/test_skill_registry.py \
        tests/unit/skills/test_selector.py \
        tests/integration/test_playbook_selection.py
git commit -m "feat: add wuxia character commentary playbook slice"
```

---

### Task 3: Add E2E Smoke Test and Operator Docs

**Files:**
- Create: `tests/e2e/test_wuxia_publish_dry_run.py`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

```yaml
verify:
  - uv run pytest tests/e2e/test_wuxia_publish_dry_run.py tests/unit/application/use_cases/test_run_playbook.py -q
done_when:
  - one CLI dry-run smoke test for wuxia_character_post passes
  - source-of-truth docs cover the new playbook, skills, and operation commands
```

- [ ] **Step 1: Write the failing E2E smoke test**

`tests/e2e/test_wuxia_publish_dry_run.py`:

```python
from __future__ import annotations

import json
import subprocess


def test_wuxia_dry_run_completes():
    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "ptsm.bootstrap", "run-playbook",
            "--scene", "分析令狐冲的自由人格与当代职场人不愿被体制化的挣扎",
            "--account-id", "acct-wuxia-local",
            "--playbook-id", "wuxia_character_post",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    output = json.loads(result.stdout)
    assert output["status"] == "completed"
    assert output["playbook_id"] == "wuxia_character_post"
    assert "令狐冲" in output["final_content"]["body"]
    assert "#金庸" in output["final_content"]["hashtags"]
    assert len(output["final_content"]["body"]) >= 400  # long-form signal
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/e2e/test_wuxia_publish_dry_run.py -v
```

Expected: FAIL if playbook/account not yet loadable, or PASS if the dry-run works.

- [ ] **Step 3: Update operator docs**

In `docs/playbooks.md` — add to "Current State" section after sushi entry:

```markdown
- `wuxia_character_post` 是第三个 playbook，专门输出长篇武侠人物评述（800-1500字），用当代流行文化视角解读金庸古龙人物。默认绑定 `acct-wuxia-local`。
```

In `docs/skills.md` — add to builtin skills list:

```markdown
- `wuxia_commentary_style` / `xhs_wuxia_hashtagging` 只服务 `wuxia_character_post`
```

In `docs/operations.md` — add to stable commands:

```markdown
- `uv run python -m ptsm.bootstrap run-playbook --scene "分析令狐冲的自由人格与当代职场" --account-id acct-wuxia-local --playbook-id wuxia_character_post`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --auto-generate-image`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "公开" --wait-for-publish-status`
```

In `docs/operations/local-runbook.md` — add wuxia dry-run example after sushi example:

```bash
# Wuxia character commentary dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "分析令狐冲的自由人格与当代职场人不愿被体制化" \
  --account-id acct-wuxia-local \
  --playbook-id wuxia_character_post
```

- [ ] **Step 4: Update playbook selection integration test**

In `tests/integration/test_playbook_selection.py`, add:

```python
def test_wuxia_playbook_is_selected_for_wuxia_account():
    accounts = AccountRegistry()
    playbooks = PlaybookRegistry(playbook_root=PLAYBOOK_ROOT)
    account = accounts.get("acct-wuxia-local")
    playbook = playbooks.select_for_account(account=account)
    assert playbook.playbook_id == "wuxia_character_post"
    assert playbook.domain == "武侠人物评述"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/e2e/test_wuxia_publish_dry_run.py tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_playbook_selection.py -q
```

Expected: PASS.

- [ ] **Step 6: Run docs-sync on changed paths**

```bash
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path docs/playbooks.md \
  --changed-path docs/skills.md \
  --changed-path docs/operations.md \
  --changed-path docs/operations/local-runbook.md \
  --changed-path src/ptsm/playbooks/definitions/wuxia_character_post/playbook.yaml \
  --changed-path src/ptsm/skills/builtin/wuxia_commentary_style/SKILL.md \
  --changed-path src/ptsm/skills/builtin/xhs_wuxia_hashtagging/SKILL.md
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/e2e/test_wuxia_publish_dry_run.py \
        tests/integration/test_playbook_selection.py \
        tests/unit/application/use_cases/test_run_playbook.py \
        docs/playbooks.md \
        docs/skills.md \
        docs/operations.md \
        docs/operations/local-runbook.md
git commit -m "docs: add wuxia smoke test and operator documentation"
```

---

### Task 4: Final Harness Verification

```yaml
verify:
  - uv run pytest -q
  - uv run python -m ptsm.bootstrap doctor
  - uv run python -m ptsm.bootstrap run-playbook --scene "分析黄蓉的处世智慧与当代女性的向上管理" --account-id acct-wuxia-local --playbook-id wuxia_character_post
done_when:
  - full pytest passes
  - doctor stays green
  - wuxia playbook completes one end-to-end dry-run through the generic CLI
  - output contains character name, #金庸 tag, and 400+ char body
```

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run doctor**

```bash
uv run python -m ptsm.bootstrap doctor
```

Expected: settings/artifacts/MCP status green.

- [ ] **Step 3: Run final dry-run smoke**

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "分析黄蓉的处世智慧与当代女性的向上管理" \
  --account-id acct-wuxia-local \
  --playbook-id wuxia_character_post
```

Record the artifact path and confirm:
- `playbook_id == "wuxia_character_post"`
- `status == "completed"`
- body contains "黄蓉"
- hashtags contains "#金庸"
- body length >= 400 chars

- [ ] **Step 4: Run harness gate**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-05-03-wuxia-character-domain.md
git commit -m "chore: finalize wuxia domain implementation plan"
```
