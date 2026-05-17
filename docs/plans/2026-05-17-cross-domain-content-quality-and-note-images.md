# Cross Domain Content Quality And Note Images Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the four non-optimized Xiaohongshu playbooks up to the same content-quality standard as `fengkuang_daily_post` and `modern_psychology_post`, and add a code-native Xiaohongshu note-card cover image generator.

**Architecture:** Keep content strategy in playbook assets and builtin skills, keep deterministic enforcement in `evaluation.yaml` plus contract evaluators, and make the runtime discover LLM content-quality gates from playbook eval contracts instead of a hard-coded playbook list. Add a local image backend under `src/ptsm/infrastructure/images` that renders a 3:4 notes-style PNG from final content when provider image generation is not configured.

**Tech Stack:** Python 3.12, LangGraph runtime, YAML playbook contracts, pytest, Pillow for local raster image rendering, existing PTSM artifact/run/eval surfaces.

## Current Docs Summary

- `docs/development-workflow.md` requires major feature work to happen in a feature branch/worktree, with a plan under `docs/plans`, task-level `verify:` and `done_when:`, source-of-truth docs updates, and final `harness-check`.
- `docs/harness-engineering.md` says XHS content-quality judge output is a required gate when enabled/configured, and deterministic contracts should catch required tags, comment prompts, save triggers, forbidden leaked experiment instructions, and generic title/cover patterns.
- `docs/playbooks.md` shows only `fengkuang_daily_post` and `modern_psychology_post` currently have rich quality gates and `evaluation.yaml`; the remaining playbooks are `sushi_poetry_daily_post`, `wuxia_character_post`, `ai_tech_daily_post`, and `daily_english_post`.
- `docs/skills.md` says `xhs_trend_scan` now extracts interaction mechanisms such as `comment_chain`, `save_tool`, `copyable_line`, and `identity_conflict`; the four remaining domain skills exist but are still thin.
- `docs/runtime.md` says runtime memory is read before drafting, the reflector can use LLM judge failures as retry feedback, artifacts include `content_review`, and image generation currently uses provider-backed backends.
- `docs/observability.md` says artifacts persist `image_generation`, `step_outputs`, eval results, and `content_review`; this must also cover local note-card images after implementation.

## Scope

- Optimize these playbooks: `sushi_poetry_daily_post`, `wuxia_character_post`, `ai_tech_daily_post`, `daily_english_post`.
- Add deterministic eval contracts and required LLM content-quality judge declarations for those four playbooks.
- Expand their planner/persona/reflection/skill assets so generation has domain-specific “hook + save/comment mechanism + persona + safety/platform fit” guidance.
- Extend deterministic fallback drafts so offline dry-runs and harness tests exercise the new constraints.
- Add local code-rendered Xiaohongshu cover images in a notes-style layout.

## Non-Goals

- No real Xiaohongshu publishing experiment in this branch.
- No separate human review console. Human review stays as `content_review` in the artifact plus operator conversation.
- No new external image provider.
- No scraping or copying high-interaction Xiaohongshu posts in this implementation. Logged-in sampling can be a later calibration task.

## Baseline Note

`uv run pytest -q --ignore=tests/e2e` was started in the fresh worktree and interrupted after running far longer than expected. `pytest --collect-only tests/unit -q` and `pytest --collect-only tests/integration -q` both completed, so collection is healthy. Before implementation, run the targeted tests listed below; before merge, run the final harness gate and investigate any remaining full-suite hang with `superpowers:systematic-debugging`.

## Task 1: Extend Deterministic Contract Evaluators

**Files:**
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`

**Step 1: Write failing tests**

Add tests for body length constraints:

```python
def test_node_contract_fails_when_body_shorter_than_min_chars() -> None:
    target = _target(
        phase="executor",
        output_ref={"final_content": {"body": "太短", "title": "t", "image_text": "i", "hashtags": ["#x"]}},
    )
    contract = PlaybookEvalContract(
        suite_id="demo.default",
        node_contracts={"executor": {"constraints": {"body_min_chars": 10}}},
    )

    result = contract_playbook_node_contract(target, contract)

    assert result.status == "failed"
    assert "body_min_chars" in result.reason
```

Add a paired `body_max_chars` test.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py -q
```

Expected: the new tests fail because `body_min_chars` / `body_max_chars` are not implemented.

**Step 3: Implement evaluator support**

In `_constraint_failures()`, when `body` is a string:

```python
body_min_chars = constraints.get("body_min_chars")
if isinstance(body_min_chars, int) and len(body) < body_min_chars:
    failures.append({...})

body_max_chars = constraints.get("body_max_chars")
if isinstance(body_max_chars, int) and len(body) > body_max_chars:
    failures.append({...})
```

Keep evidence shape consistent with the existing title/hashtag/body failures.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py -q
```

Expected: pass.

**done_when:** Contract evaluators can enforce minimum and maximum body length without adding playbook-specific code branches.

## Task 2: Add Evaluation Contracts For The Four Remaining Domains

**Files:**
- Create: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/evaluation.yaml`
- Create: `src/ptsm/playbooks/definitions/wuxia_character_post/evaluation.yaml`
- Create: `src/ptsm/playbooks/definitions/ai_tech_daily_post/evaluation.yaml`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Write failing tests**

Parametrize contract loading for all six playbooks and assert these four now have:

- `node_contracts.executor.required_fields` containing `title`, `image_text`, `body`, `hashtags`
- `quality_judges.executor_content_quality.gate_level == "required"`
- required domain hashtag constraints
- comment prompt and save trigger constraints
- forbidden leaked instruction tokens: `变体要求`, `模板要求`, `comment_chain`, `save_tool`, `identity_conflict`

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py -q
```

Expected: fail because the four `evaluation.yaml` files do not exist.

**Step 3: Add evaluation contracts**

Use the existing fengkuang/psychology schema. Domain-specific executor constraints:

- `sushi_poetry_daily_post`: require `#苏轼`, body includes `苏轼`, include a save phrase such as `存` / `记下来` / `这一句`, include a comment phrase such as `评论区` / `你读到哪句`, avoid encyclopedia/lecture phrasing.
- `wuxia_character_post`: require `#金庸` or `#古龙`, body includes a named source such as `《笑傲江湖》` or `《射雕英雄传》`, includes `原文` / quoted line marker, body length `800-1500`, include screenshot/save phrasing and a reader comment prompt.
- `ai_tech_daily_post`: require `#AI资讯`, body length at least `220`, include `是什么` / `为什么重要` / `普通人`, include `收藏` / `清单` / `记住`, include `评论区` / `你会用吗`, forbid hype or investment advice leakage.
- `daily_english_post`: require `#每日英语`, body includes `音标`, `词性`, `例句`, `翻译`, include `存` / `收藏` / `句型`, include `评论区` / `造句`, forbid dictionary-only or classroom leakage phrases.

Each file must declare:

```yaml
quality_judges:
  executor_content_quality:
    evaluator_id: llm.executor.content_quality
    gate_level: required
    threshold: 0.7
```

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py -q
```

Expected: pass.

**done_when:** All six real XHS playbooks have loadable eval contracts and the four newly optimized domains declare required executor content-quality judges.

## Task 3: Make Runtime Judge Activation Contract-Driven

**Files:**
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Create or modify: `tests/unit/agent_runtime/test_runtime_quality_judge.py`

**Step 1: Write failing tests**

Add a helper-level test that verifies judge activation is now based on playbook `evaluation.yaml`:

```python
def test_quality_judge_required_by_eval_contract_for_ai_tech() -> None:
    assert _playbook_requires_content_quality_judge("ai_tech_daily_post") is True
```

Add a missing-contract case with a temporary definitions root if the helper accepts one.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/agent_runtime/test_runtime_quality_judge.py -q
```

Expected: fail because runtime currently hard-codes only `fengkuang_daily_post` and `modern_psychology_post`.

**Step 3: Implement contract-driven helper**

Add a private helper in `runtime.py`:

```python
def _playbook_requires_content_quality_judge(playbook_id: str) -> bool:
    contract = load_playbook_eval_contract(PLAYBOOK_ROOT, playbook_id)
    judge = None if contract is None else contract.quality_judges.get("executor_content_quality")
    return isinstance(judge, dict) and judge.get("gate_level") == "required"
```

Use it in `build_playbook_workflow()`:

```python
if content_quality_judge_backend is None and _playbook_requires_content_quality_judge(playbook_id):
    content_quality_judge_backend = build_llm_judge_backend(settings)
```

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/agent_runtime/test_runtime_quality_judge.py tests/unit/agent_runtime/test_reflector_node.py -q
```

Expected: pass.

**done_when:** Adding `quality_judges.executor_content_quality` to a playbook contract is enough for runtime to attempt judge-backed reflection when credentials are configured.

## Task 4: Expand Domain Prompt, Reflection, And Skill Assets

**Files:**
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml`
- Modify: `src/ptsm/skills/builtin/sushi_poetry_style/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/wuxia_character_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/wuxia_character_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/wuxia_character_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/wuxia_character_post/playbook.yaml`
- Modify: `src/ptsm/skills/builtin/wuxia_commentary_style/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/playbook.yaml`
- Modify: `src/ptsm/skills/builtin/ai_tech_style/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/daily_english_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/daily_english_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/daily_english_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/daily_english_post/playbook.yaml`
- Modify: `src/ptsm/skills/builtin/daily_english_style/SKILL.md`
- Modify: `tests/unit/playbooks/test_playbook_loader.py`
- Modify: `tests/unit/skills/test_skill_registry.py`

**Step 1: Write failing tests**

Assert each target skill text includes the new strategy markers:

- Sushi: `生活瞬间`, `可收藏`, `评论区`, `不要讲义`
- Wuxia: `当代切口`, `原文`, `截图`, `评论区`
- AI tech: `3秒核心信息`, `普通人影响`, `收藏清单`, `非投资建议`
- Daily English: `真实场景`, `造句`, `可收藏`, `不要词典式`

Assert playbook reflection rules include required domain tags and deterministic anti-leak lists.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py -q
```

Expected: fail on missing strategy markers.

**Step 3: Update assets**

For each domain, make the generation instruction explicit:

- Hook: specific, concrete, one-scene opening.
- Borrowed XHS mechanism: one saveable line/tool/template and one comment prompt.
- Persona: real creator voice, not lecture, not generic SEO article.
- Variation: avoid repeating identical title/cover/body structures across runs.
- Safety/platform: avoid unsupported claims, medical/legal/financial overreach, and experiment instruction leakage.

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py -q
```

Expected: pass.

**done_when:** The four domain skills and playbook reflection assets give the LLM concrete content mechanisms to learn from, not just topic labels.

## Task 5: Upgrade Offline Deterministic Drafts And Domain E2E Coverage

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Create: `tests/e2e/test_ai_tech_publish_dry_run.py`
- Create: `tests/e2e/test_daily_english_publish_dry_run.py`
- Modify: `tests/e2e/test_sushi_poetry_publish_dry_run.py`
- Modify: `tests/e2e/test_wuxia_publish_dry_run.py`

**Step 1: Write failing tests**

Add deterministic backend tests for:

- Sushi output includes `苏轼`, `#苏轼`, a save/comment cue, and does not look like a lecture note.
- Wuxia output is long enough, includes character/source/original quote, screenshotable thesis, and comment prompt.
- AI tech output includes concrete event/product/data, `是什么/为什么重要/普通人`, save cue, comment prompt, `#AI资讯`.
- Daily English output includes word/phonetic/POS/meaning/example/translation/practice, save cue, comment prompt, `#每日英语`.

Add CLI dry-run e2e for AI tech and daily English like the existing sushi/wuxia tests.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_sushi_poetry_publish_dry_run.py tests/e2e/test_wuxia_publish_dry_run.py tests/e2e/test_ai_tech_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py -q
```

Expected: fail for the new/stricter assertions.

**Step 3: Implement deterministic drafts**

Move sushi handling into `contextual_drafts.py` with richer structure, and add AI tech / daily English contextual draft builders. Keep the generic fengkuang fallback in `factory.py`.

Minimum deterministic draft shape:

- `title`: non-generic and domain-specific.
- `image_text`: short cover line that can render cleanly.
- `body`: satisfies the new contract constraints.
- `hashtags`: includes the required domain tag plus 2-4 relevant tags.

**Step 4: Verify**

Run the same command from Step 2.

Expected: pass.

**done_when:** Offline dry-run can generate representative, contract-satisfying candidates for all six real playbooks without real LLM credentials.

## Task 6: Add Local Notes-Style Image Backend

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ptsm/infrastructure/images/note_card_backend.py`
- Modify: `src/ptsm/infrastructure/images/__init__.py`
- Create: `tests/unit/infrastructure/images/test_note_card_backend.py`

**Step 1: Write failing tests**

Add tests that call:

```python
backend = NoteCardImageBackend(width=1080, height=1440)
result = backend.generate(
    prompt=json.dumps(
        {
            "title": "周日晚上怕周一消息，不是你没用",
            "image_text": "脑子提前打卡上班",
            "body": "可以先存一个 5分钟落地练习...",
            "hashtags": ["#心理学", "#情绪管理"],
        },
        ensure_ascii=False,
    ),
    output_dir=tmp_path,
    output_stem="cover",
)
```

Assert:

- result `provider == "local_note_card"`
- generated path exists and ends with `.png`
- dimensions are `1080x1440`
- pixel data is not blank
- metadata includes `style == "xhs_note_card_v1"`

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q
```

Expected: fail because the backend does not exist.

**Step 3: Add Pillow dependency**

Add:

```toml
"Pillow>=10.4.0,<12.0.0",
```

Then run:

```bash
uv sync
```

**Step 4: Implement backend**

Implement a deterministic renderer:

- 3:4 vertical canvas, default `1080x1440`.
- warm off-white note background, black/dark-gray text, subtle separators.
- top bar that evokes a notes app without using Apple trademarks.
- title and cover text from final content.
- wrapped Chinese text using Pillow.
- local font discovery for common macOS/Linux CJK fonts, with fallback to Pillow default.
- no hashtags/watermarks on the image unless future settings explicitly ask for them.

**Step 5: Verify**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q
```

Expected: pass.

**done_when:** The repo can generate a nonblank local PNG cover without external image APIs.

## Task 7: Integrate Local Note Images Into Run Playbook

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add a test for real publish or explicit `auto_generate_images=True` with no Jimeng/Bailian config:

```python
def test_run_fengkuang_playbook_uses_local_note_card_when_provider_missing(...):
    monkeypatch.setattr("ptsm.application.use_cases.run_playbook.build_image_backend", lambda _settings: None)
    ...
    result = run_fengkuang_playbook(... auto_generate_images=True ...)
    assert result["image_generation"]["provider"] == "local_note_card"
    assert publisher.received_image_paths
```

Keep the existing dry-run-without-flag behavior unchanged: no image generation unless explicitly requested.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q
```

Expected: new test fails because current behavior records `backend_not_configured`.

**Step 3: Implement integration**

When auto image generation is requested and provider backend is missing, instantiate `NoteCardImageBackend` and pass a JSON prompt built from `final_content`, `scene`, and runtime context. Preserve provider prompt behavior for Jimeng/Bailian.

Suggested helper:

```python
def _build_note_card_image_payload(...)-> str:
    return json.dumps({...}, ensure_ascii=False)
```

Artifact metadata should include:

- `status: "generated"`
- `provider: "local_note_card"`
- `style: "xhs_note_card_v1"`
- `generated_image_paths`
- `runtime_context_summary`

**Step 4: Verify**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/images/test_note_card_backend.py -q
```

Expected: pass.

**done_when:** `run-playbook --auto-generate-image` can produce a notes-style local cover and persist the generated path into the artifact when external image providers are absent.

## Task 8: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`

**Step 1: Update docs**

Document:

- all six playbooks now have quality contracts and required content-quality judge declarations
- the four newly optimized domain skills now encode XHS hook/save/comment mechanics
- runtime judge activation is contract-driven
- local note-card image backend is the fallback when auto image generation is requested but provider credentials are absent
- artifacts persist `provider: local_note_card` and `style: xhs_note_card_v1`

Update `last_verified` on touched active source-of-truth docs to `2026-05-17` after verification passes.

**Step 2: Verify docs sync**

Run:

```bash
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
```

Expected: pass.

**done_when:** Source-of-truth docs describe the actual implementation and docs-sync accepts the code/doc mapping.

## Task 9: End-To-End Evaluation And Harness Gate

**Files:**
- No new files expected unless command output reveals missing docs/tests.

**Step 1: Run targeted suite**

Run:

```bash
uv run pytest tests/unit/evaluations tests/unit/agent_runtime tests/unit/infrastructure/llm tests/unit/infrastructure/images tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_sushi_poetry_publish_dry_run.py tests/e2e/test_wuxia_publish_dry_run.py tests/e2e/test_ai_tech_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py -q
```

Expected: pass.

**Step 2: Generate one local note-card dry-run artifact**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook --scene "今天只想快速看懂一个AI产品更新，对普通人到底有没有用" --account-id acct-ai-tech-local --playbook-id ai_tech_daily_post --auto-generate-image
```

Expected: JSON status `completed`, `image_generation.provider == "local_note_card"`, generated PNG under `outputs/generated_images/`.

**Step 3: Eval the artifact**

Run:

```bash
uv run python -m ptsm.bootstrap eval-artifact --artifact <artifact_path_from_step_2>
```

Expected: deterministic contract evaluators pass; LLM judge remains disabled unless credentials are explicitly configured.

**Step 4: Run full verification**

Run:

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict
```

Expected: all pass. If full pytest hangs again, apply `superpowers:systematic-debugging` to identify the stuck test and do not claim full-suite success until the root cause is understood.

**done_when:** Targeted domain/image tests pass, a real CLI dry-run produces a local note-card image, eval-artifact confirms deterministic contracts, docs-sync passes, and strict harness-check passes.
