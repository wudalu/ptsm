# Prompt Builder Sublane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a PTSM topic-guidance lane for Xiaohongshu posts that teach ordinary users how to build useful AI prompts.

**Architecture:** Treat prompt-building as a sublane of `ai_tech_daily_post`, not a new standalone playbook. The domain-opportunity scan mapped AI asking/workflow keywords to the existing AI workflow playbook and did not produce new-domain evidence; therefore this change stays additive in topic guidance, AI tech prompt assets, deterministic dry-run behavior, evaluation contracts, and docs.

**Tech Stack:** Python 3.12, pytest, YAML/Markdown playbook assets, deterministic `guide-post`, deterministic draft backend, `harness-check`.

## Current Docs Summary

- `docs/development-workflow.md` requires major work to happen in an isolated worktree, with a plan before implementation, task-level `verify:` and `done_when:`, source-of-truth docs updates, dry-run proof, and final `harness-check`.
- `docs/harness-engineering.md` says new domains/playbooks need the 完整文档面. For this change, the evidence supports a sublane under `ai_tech_daily_post`; the plan still reviews the complete docs surface and records unchanged surfaces explicitly.
- `docs/playbooks.md` says `guide-post` is the local-first pre-post topic guidance surface for nine playbooks, and `ai_tech_daily_post` already covers AI model updates, ordinary workflow, tool choice, and ordinary-person impact.
- `docs/runtime.md` says ordinary `guide-post` does not live-scan XHS by default; it uses local topic packs and deterministic selection. New prompt-building guidance belongs in `topic_guidance_packs.py` unless runtime behavior truly changes.
- `docs/skills.md` says `ai_tech_style` owns ordinary AI workflow framing, concrete tasks, boundaries, saveable checklists, and non-PR tone.

## Evidence And Constraints

- XHS note URL: browser and web attempts could not read the note content. Browser reached XHS safety restriction / login error, so this plan must not claim copied content from the source note.
- PTSM scan command:
  `uv run python -m ptsm.bootstrap xhs-domain-opportunity --keywords "提示词,prompt,AI提问,普通人用AI,AI工具,AI工作流" --sample-limit-per-keyword 5 --skip-login-check --tool-timeout-seconds 70`
- Scan result: MCP sampling failed with `search_feeds` errors, but deterministic keyword mapping put `AI提问`, `普通人用AI`, `AI工具`, and `AI工作流` under `ai_tech_daily_post`; no new domain candidates were returned.
- Scope: add a prompt-building sublane and deterministic dry-run support; do not add a tenth playbook, new account, new publish path, or live XHS dependency.
- Non-goal: real Xiaohongshu publishing.

### Task 1: Lock Prompt-Building Guide-Post Behavior

**Files:**
- Modify: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write the failing test**

Add a test that calls `run_guide_post()` with:

```python
GuidePostRequest(
    playbook_id="ai_tech_daily_post",
    account_id="acct-ai-tech-local",
    scene="想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出",
)
```

Assert:

- `topic_guidance.matched_direction_id == "ai_prompt_context_card"`
- first direction id is `ai_prompt_context_card`
- first direction mentions `prompt` or `提示词`
- `saveable_tool` includes `任务 / 背景 / 输出格式`
- `comment_prompt` asks readers to submit a prompt or failed example
- `image_recommendation.recommended_backend == "local_social_screenshot"`
- `image_recommendation.local_style == "iphone_notes"`

**Step 2: Run the test to verify it fails**

verify: `uv run pytest tests/unit/application/use_cases/test_guide_post.py -q -k "prompt"`

done_when: the new test fails because the prompt-building direction/lane is not implemented yet.

### Task 2: Add The Prompt-Building Topic Lane

**Files:**
- Modify: `src/ptsm/application/use_cases/topic_guidance_packs.py`

**Step 1: Implement minimal topic-pack additions**

Add a new `TopicLane` to `AI_TECH_PACK`:

- name: `提示词构建 / 好用 prompt`
- default scene: ordinary user wants AI to ask clarifying questions before output
- default saveable tool: `任务 / 背景 / 输出格式 / 反例`
- keywords: `prompt`, `提示词`, `提问`, `追问`, `输出格式`, `背景`, `反例`, `指令`

Add curated directions:

- `ai_prompt_context_card`: context card for task/background/output format
- `ai_prompt_clarifying_questions`: make AI ask before answering
- optional `ai_prompt_failure_replay`: turn a bad output into a retry prompt

**Step 2: Run the guide-post test**

verify: `uv run pytest tests/unit/application/use_cases/test_guide_post.py -q -k "prompt"`

done_when: the prompt-building guide-post test passes and no internal source/URL leaks appear.

### Task 3: Lock Prompt-Building Dry-Run Output

**Files:**
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/e2e/test_ai_tech_publish_dry_run.py`

**Step 1: Write failing deterministic backend test**

Add a deterministic backend test for a prompt-building scene. Assert the draft body contains:

- `任务`
- `背景`
- `输出格式`
- `反例` or `失败样例`
- `评论区`
- `非投资建议`
- `#AI资讯`

Assert it does not expose internal labels such as `save_tool`, `comment_chain`, or `模板要求`.

**Step 2: Write failing CLI dry-run test**

Add an e2e CLI dry-run test with the prompt-building scene and assert the final content contains the same prompt-building structure plus the existing AI tech contract terms `是什么`, `为什么重要`, and `普通人`.

**Step 3: Run the tests to verify failure**

verify: `uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_ai_tech_publish_dry_run.py -q -k "prompt or ai_tech"`

done_when: new prompt-building assertions fail before implementation.

### Task 4: Implement Prompt-Building Draft Support

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/skills/builtin/ai_tech_style/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/evaluation.yaml`

**Step 1: Implement minimal deterministic scene branch**

Teach `_build_ai_tech_draft()` to detect prompt-building scenes and produce a short XHS-native post that:

- keeps the existing `是什么 -> 为什么重要 -> 普通人影响` contract
- gives a saveable prompt card: `任务 / 背景 / 输出格式 / 反例`
- asks readers to post a prompt or failed output in comments
- keeps `#AI资讯`
- stays under 650 chars and avoids template/meta leakage

**Step 2: Update AI tech prompt assets**

Add prompt-building wording to AI tech style/planner/persona/reflection without changing playbook routing.

**Step 3: Tighten evaluation where needed**

If tests show title/body constraints block legitimate prompt-building output, update `evaluation.yaml` additively.

**Step 4: Run task verification**

verify: `uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_ai_tech_publish_dry_run.py -q`

done_when: existing and prompt-building AI tech deterministic dry-runs pass.

### Task 5: Update Complete Source-Of-Truth Docs Surface

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`

**Step 1: Update docs**

Record this as a sublane of `ai_tech_daily_post`, not a new playbook/domain:

- `architecture.md`: note no new domain count; AI tech guide-post has a prompt-building sublane.
- `runtime.md`: note `guide-post` can route prompt-building scenes to local prompt directions and dry-run stays deterministic.
- `playbooks.md`: update AI tech playbook description and guidance examples.
- `skills.md`: update `ai_tech_style` scope with prompt construction.
- `harness-engineering.md`: add the new deterministic prompt-building guide/dry-run coverage.
- `docs/operations.md`: add representative `guide-post` and `run-playbook` commands.
- `docs/operations/local-runbook.md`: add prompt-building examples near AI tech guide/run commands.

**Step 2: Run docs tests**

verify: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q`

done_when: docs metadata/map and wrapper contract tests pass.

### Task 6: Final Verification

**Files:**
- No new files unless command artifacts are generated under ignored `outputs/`.

**Step 1: Run targeted guide-post command**

verify:

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id ai_tech_daily_post \
  --account-id acct-ai-tech-local \
  --scene "想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出" \
  --non-interactive \
  --format json
```

done_when: JSON includes `ai_prompt_context_card`, prompt-building saveable tool, and `topic_guidance.image_recommendation.local_style == "iphone_notes"`.

**Step 2: Run targeted dry-run command**

verify:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出" \
  --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post \
  --publish-mode dry-run
```

done_when: command exits 0 with `status == completed`, `publish_result.status == dry_run`, final content includes `任务 / 背景 / 输出格式`, and no raw XHS URL/source provenance is exposed.

**Step 3: Run full gates**

verify:

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py --changed-path src/ptsm/infrastructure/llm/contextual_drafts.py --changed-path docs/playbooks.md --changed-path docs/skills.md
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

done_when: all commands pass, or any skipped/unavailable command is recorded with the exact reason.
