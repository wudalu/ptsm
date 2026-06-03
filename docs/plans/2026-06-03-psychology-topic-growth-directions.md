# Psychology Topic Growth Directions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the psychology `guide-post` topic guidance surface more directly useful for improving Xiaohongshu views, likes, saves, and comments by adding concrete high-intent directions rather than only post-publish metrics.

**Architecture:** Keep this inside the existing `modern_psychology_post` guidance system. Add authored curated `TopicDirection` entries and lane keywords in `src/ptsm/application/use_cases/guide_post.py`, keep selection deterministic through the existing score/rerank engine, and update playbook/skill docs so generation and OpenClaw wrappers know these are psychology directions, not a new domain or live research result.

**Tech Stack:** Python 3.12, pytest, PTSM `guide-post`, deterministic local topic guidance data, markdown playbook/skill assets.

## Current Docs Summary

- `docs/development-workflow.md` requires an isolated worktree, docs-first planning, TDD, source-of-truth docs updates, and `harness-check` for behavior changes.
- `docs/playbooks.md` says `modern_psychology_post` already covers职场复盘、亲密关系不确定感、关系边界、数字生活、孤独/比较、情绪调节、睡眠恢复/轻养生和热点心理化重构. It also says `guide-post` returns 4 dynamic directions with `direction_type`, `scene_fit`, trend signal, hook, save tool, comment prompt, and image recommendation.
- `docs/runtime.md` defines `guide-post` as a local, deterministic, no-publish, no-live-scan selector. The first curated direction becomes the compatible `matched_direction_id`, so relevance depends on authored direction keywords, lane affinity, priority, and diversity.
- `docs/skills.md` says psychology content should start with a concrete moment, lightly explain one mechanism, end with a saveable unit and role/A-B/fill-in comment entry, and keep safety boundaries intact.
- Current code already has broad directions for AI companion boundary, sleep scroll closing ritual, office recovery, relationship uncertainty, and message boundary. The gap is more concrete high-comment/high-click direction variants for ambiguous relationship signals, social battery/cancel-plan guilt, and after-hours message body alarm.

## Task 1: Add failing guide-post tests for high-growth psychology directions

**Files:**
- Modify: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write the failing tests**

Add tests for these scene-to-direction contracts:

```python
def test_psychology_topic_guidance_routes_relationship_mixed_signal_camp_vote():
    result = run_guide_post(
        GuidePostRequest(scene="对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队")
    )
    assert result["topic_guidance"]["matched_direction_id"] == "relationship_mixed_signal_camp_vote"
    first = result["topic_guidance"]["directions"][0]
    assert first["id"] == "relationship_mixed_signal_camp_vote"
    assert "A." in first["comment_prompt"] and "B." in first["comment_prompt"]
    assert "事实" in first["saveable_tool"]
```

Add equivalent tests for:

- `social_battery_cancel_plan_boundary`: scene `约好的局临时不想去了，怕扫兴又很累，想写社交电量边界`
- `after_hours_message_body_alarm`: scene `领导18:57发来一句在吗，下班后身体被消息拉回工位`

Assert each first direction has an A/B or multi-option comment prompt and a concrete saveable tool. Assert image recommendation stays local (`iphone_notes` or `wechat_chat`, depending on the scene) and internal source leakage helper still passes.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_relationship_mixed_signal_camp_vote -q
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_social_battery_cancel_plan_boundary -q
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_after_hours_message_body_alarm -q
```

Expected: FAIL because the direction ids do not exist or are not ranked first.

`done_when:` The tests prove the current guidance layer does not yet expose these concrete growth directions.

## Task 2: Implement the topic direction additions

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`

**Step 1: Extend lane keywords**

Add high-intent keywords:

- 亲密关系 / 不确定感: `忽冷忽热`, `突然冷淡`, `暧昧`, `要不要问`, `站队`, `怕烦`
- 孤独 / 比较焦虑: `社交耗竭`, `社交电量`, `取消`, `约好的局`, `扫兴`, `不想去`
- 职场复盘 / 低控制感 if needed: `18:57`, `下班消息`, `在吗`, `拉回工位`, `领导`

**Step 2: Add curated directions**

Add three `TopicDirection` entries:

- `relationship_mixed_signal_camp_vote`
  - trend: `关系不确定感 / A-B 阵营`
  - hook: `评论区站队`
  - tool: `事实 / 信号 / 我要不要确认一句`
  - prompt: `你是哪派：A.问清楚 B.先观察？`
  - avoid: no mind-reading, no diagnosis, no forcing confrontation.

- `social_battery_cancel_plan_boundary`
  - trend: `社交耗竭 / 低成本边界`
  - hook: `A/B 角色认领`
  - tool: `取消局三句：承认约定、说明状态、给下一次选项`
  - prompt: `你是哪派：A.硬着头皮去 B.愧疚地取消？`
  - avoid: do not shame socializing or encourage disappearing.

- `after_hours_message_body_alarm`
  - trend: `下班消息 / 身体警报`
  - hook: `A/B/C 工位身份评论`
  - tool: `下班消息三步：先看紧急度、给处理时间、把身体带回来`
  - prompt: `你是哪派：A.秒回 B.装没看见 C.先写明天再回？`
  - avoid: do not teach disappearing, do not normalize unsafe workplace conflict.

Use `base_priority` high enough for exact scenes to rank first, but keep `diversity_key` distinct so the dynamic breadth selector still shows varied follow-up directions.

**Step 3: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_relationship_mixed_signal_camp_vote tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_social_battery_cancel_plan_boundary tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_after_hours_message_body_alarm -q
```

Expected: PASS.

`done_when:` `guide-post` reliably puts the new growth directions first for their matching scenes.

## Task 3: Keep generation assets aligned

**Files:**
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify if needed: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Test if contextual draft changes: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**Step 1: Update prompt assets**

Mention the three new concrete direction families as examples under existing lanes:

- 亲密关系 / 不确定感: 忽冷忽热、要不要问清楚、A/B 阵营讨论
- 孤独 / 社交耗竭: 临时不想去约好的局、社交电量、取消局边界
- 职场复盘 / 低控制感: 18:57 在吗、下班消息把身体拉回工位

Keep the existing guardrails: no diagnosis, no treatment promises, no public claim that these are proven winners.

**Step 2: Add deterministic draft coverage only if tests require it**

If e2e dry-run does not already produce a coherent psychology post for one of the new scenes, add one minimal deterministic branch for `社交电量` / `取消局` with body length, comment prompt, save tool, and professional boundary.

`done_when:` The generation prompts can naturally turn selected directions into posts without leaking internal growth strategy language.

## Task 4: Update source-of-truth docs and wrapper skill

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/runtime.md` only if selector mechanics or runtime behavior changed
- Modify: `docs/operations.md` if adding representative commands
- Modify: `docs/harness-engineering.md` if adding harness coverage summary
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Update external skill if needed: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`

**Step 1: Document the new selection guidance**

Document that psychology `guide-post` now has concrete growth-oriented directions for ambiguous relationship signals, social battery/cancel-plan guilt, and after-hours message body alarm. Clarify that these are hypotheses to test, not proven uplift.

**Step 2: Verify docs sync**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_skill.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/planner.md --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/persona.md --changed-path src/ptsm/skills/builtin/psychology_style/SKILL.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/harness-engineering.md --changed-path docs/operations.md --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md --changed-path tests/unit/application/use_cases/test_guide_post.py
```

`done_when:` docs-sync reports `status: ok`, `missing_updates: []`, and `unmapped_changes: []`.

## Task 5: End-to-end verification

**Files:**
- No production edits expected.

**Step 1: Run targeted tests**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**Step 2: Run CLI smoke**

```bash
uv run python -m ptsm.bootstrap guide-post --scene "对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --scene "约好的局临时不想去了，怕扫兴又很累，想写社交电量边界" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --scene "领导18:57发来一句在吗，下班后身体被消息拉回工位" --non-interactive --format json
```

Expected: `status == completed`; first curated direction ids match the new direction ids.

**Step 3: Run project gate**

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

`done_when:` Tests pass, harness top-level status is `ok`, and any warnings are identified as pre-existing run-store warnings rather than new failures.

## Execution Notes

- 2026-06-03: Added the three guide-post direction tests and verified RED before implementation.
- 2026-06-03: Added `relationship_mixed_signal_camp_vote`, `social_battery_cancel_plan_boundary`, and `after_hours_message_body_alarm` to the psychology selector with lane keywords, saveable tools, and A/B or A/B/C prompts.
- 2026-06-03: Added deterministic dry-run coverage for `忽冷忽热` and `社交电量取消局` so selected directions do not fall back to generic workplace replay copy.
- 2026-06-03: Updated psychology prompt assets, builtin skill guidance, OpenClaw wrapper text, source-of-truth docs, and local runbook examples.
- 2026-06-03: Verification passed for targeted pytest, CLI smoke, `docs-sync`, `pytest -q --ignore=tests/e2e`, and `harness-check --changed-path ...`.
