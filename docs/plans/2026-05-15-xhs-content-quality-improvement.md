# XHS Content Quality Improvement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve Xiaohongshu post views and interaction by upgrading PTSM from "topic-aligned drafting" to "topic + participation + save/comment trigger" content generation for `fengkuang_daily_post` and `modern_psychology_post`.

**Architecture:** Keep the current playbook/skill/runtime boundaries. First build a small evidence set from Xiaohongshu high-engagement samples, then encode the reusable findings into playbook prompts, builtin skills, reflection checks, account memory reuse, and warning-only quality evals. Treat real publish metrics as experiment feedback, not as deterministic harness gates.

**Tech Stack:** Markdown docs, topic-radar, xiaohongshu-mcp, YAML playbook evaluation contracts, builtin `SKILL.md` prompts, pytest, existing `eval-artifact` / `harness-evals` / `harness-check`, optional LLM judge warning path.

## Current Docs Summary

- `docs/index.md` says content and strategy changes should start from `docs/playbooks.md`, `docs/skills.md`, and `docs/xhs-topics/index.md`.
- `docs/development-workflow.md` requires larger playbook/skill/runtime changes to use a plan with `verify:` and `done_when:` checks before implementation.
- `docs/playbooks.md` defines playbooks as the business orchestration layer, with planner/persona/reflection assets and optional `evaluation.yaml`.
- `docs/skills.md` says `xhs_trend_scan` and `topic_research` can inject dynamic trend context, but there is not yet skill-level content quality judgment.
- `docs/topic-radar.md` already models title hooks, content structure, interaction triggers, and comment signals, but current Xiaohongshu scan quality depends on local MCP login.
- `docs/operations/local-runbook.md` ranks XHS search results with `likes + comments*4 + shares*6 + collects*2`, which is a good proxy for "worth studying" posts.

## Current Diagnosis

The local artifacts show that PTSM can satisfy structure and safety contracts, but the generated posts often stop at "valid content" instead of becoming "platform-native social objects."

Examples:

- `outputs/artifacts/acct-fk-local-fengkuang_daily_post-2.json` has a valid scene and tags, but the title "打工人地铁生存实录" and cover "今日已疯" are too generic. They do not create a comment game, a reusable sentence pattern, or a strong reason to save/share.
- `outputs/artifacts/acct-fk-local-fengkuang_daily_post-1.json` has more story detail, but jokes around "精神病院/心理医生/咨询费" are risky when the project also has a psychology lane. This can dilute trust and should be replaced with non-stigmatizing absurdity.
- `outputs/artifacts/acct-psychology-local-modern_psychology_post-1.json` is safe and clear, but reads like a compact explainer. It lacks a stronger first-screen hook, a memorable framework, and an explicit comment prompt.
- `outputs/artifacts/acct-psychology-local-modern_psychology_post-2.json` is much closer: concrete scene, named mechanism, tiny action. It still needs a tighter cover/title pair and a final interaction question.

On 2026-05-15, `ptsm doctor` showed `xhs_preflight` as `login_required`; a `topic-radar scan --platforms xiaohongshu --keywords "发疯文学,心理学,情绪管理,职场焦虑"` produced zero `raw_trending` samples. Do not use that scan as market evidence until MCP login is restored.

After login was restored on 2026-05-15, direct `search_feeds` sampling collected 117 candidates across `发疯文学`, `打工人发疯`, `职场发疯`, `心理学`, `情绪管理`, `职场焦虑`, and `反刍思维`; 115 had comment or collect signals. The stable search-level artifact is `outputs/artifacts/xhs-content-quality-search-2026-05-15.json`; findings are summarized in `docs/research/2026-05-15-xhs-content-quality-sample-set.md`.

## Borrowed Patterns From The Sample

The sample changes the plan from "make posts more emotional" to "make posts more usable by the platform."

| Lane | What High Interaction Borrows | What PTSM Must Generate |
| --- | --- | --- |
| 发疯文学 | Comment/share spikes come from reusable jokes, `个签`, `文案`, `话术`, `请假条`, short laugh loops, and identity forwarding. | A concrete workplace object, one exact collapse moment, one copyable line, and one comment-completion prompt. |
| 心理学 / 情绪管理 | Collect/share spikes come from cognitive reframes, `Tips`, `判断`, `法则`, `反复观看`, and simple mental models. | A micro-scene, one named mechanism, one screenshot-worthy mini-tool, and one example-based comment prompt. |
| 职场焦虑 | Strong posts name a specific audience or conflict: `工资3w以下`, `优秀员工躺平`, `优等生思维`. | A sharper identity/conflict hook, without diagnosis bait or class resentment as the only angle. |
| Low controls | Generic titles like `当代打工人抽象发疯实录` or abstract claims like `平静地发疯是顶级智慧` underperform. | Reject generic titles unless paired with a concrete object, line, or tool. |

## Engineering Gap Analysis

| Layer | Current State | Gap | Required Change |
| --- | --- | --- | --- |
| topic-radar evidence | `search_feeds` can collect candidates; LLM scan can produce trend angles. | LLM conversion drops `raw_trending`; `get_feed_detail` parser misses `data.note`; teardown can hang on inaccessible notes. | Preserve raw XHS rows in `TopicScanResult`, parse `data.note`, and add bounded per-note retry/fail-fast. |
| runtime context skills | `xhs_trend_scan` injects top titles and a loose `主切口/场景张力`; `topic_research` injects selected angles. | Context does not label sample mechanics like `copyable_line`, `save_tool`, `comment_chain`, or `identity_conflict`. | Add a content-mechanics summary to runtime skill context so prompts receive "what to borrow", not only "what is hot". |
| playbook prompts | Fengkuang requires scene, self-mockery, light landing; psychology requires scene, mechanism, safe boundary. | Neither requires save/share/comment mechanics. | Update planner/persona/reflection to require `hook -> mechanism -> save_trigger/comment_trigger -> safety` by lane. |
| reflection node | `src/ptsm/agent_runtime/nodes/reflector.py` only checks `required_hashtag` and `must_include_phrase`. Fengkuang config sets `must_include_phrase: 也算`. | This makes `也算` a hard gate and allows low-quality but phrase-compliant drafts through. | Make `must_include_phrase` optional, move `也算` to a recommendation, and add deterministic reflection/contract checks for mechanics that matter. |
| account memory | `finalize` records lessons under `("accounts", account_id, "lessons")`; `planner` and `executor` never read them. | The system cannot avoid repeated structures, endings, hotwords, or near-duplicate posts across runs. | Retrieve recent lessons before drafting and pass compact anti-repetition guidance into runtime context/prompts. |
| builtin skills | Style skills are short and generic. | They do not encode learned high-interaction formats. | Add concrete format recipes and anti-patterns to `fengkuang_style`, `psychology_style`, hashtagging, and safety skills. |
| drafting backend | DeepSeek hard requirements only enforce JSON, runtime hook, hashtags, and a few phrases. Deterministic fengkuang fallback still emits weak titles like `打工人地铁生存实录`. | Prompt compliance can drift; offline tests preserve generic output. | Add hard requirements for comment/save mechanics; upgrade deterministic drafts so tests can assert the new quality bar. |
| eval contracts | Playbook eval checks fields, tags, title length, required/forbidden body terms. | No deterministic check catches generic titles, missing comment prompt, missing save trigger, or mental-health jokes in 发疯文学. | Extend `playbook.node_contract` constraints with title/image/body quality predicates and add warning-only content quality judge later. |
| e2e tests | Existing e2e tests check status, tags, and safety basics. | Tests do not fail when output is boring but valid. | Add dry-run assertions for concrete object, comment trigger, save/tool trigger, and anti-generic titles. |
| experiment loop | Metrics are manually observed. | No plan links post variants to 2h/24h/72h outcomes. | Add an experiment runbook and log schema; use metrics to update prompts/evals. |

## Concrete Implementation Order

Do not start with prompt edits alone. The correct order is:

1. **Fix evidence ingestion** so future scans preserve raw samples and teardown fails fast.
2. **Remove structural locks** so `也算` is no longer required and reflection can reject boring but formally compliant drafts.
3. **Read account memory before drafting** so the next post can avoid yesterday's title shape, hotwords, and ending.
4. **Encode borrowed mechanics into skills and prompts** so generation knows what to do with the evidence.
5. **Add deterministic quality checks** for obvious misses, keeping nuanced style as warning-only judge/manual review.
6. **Run dry-run tests and real publish experiments** to calibrate whether the mechanics actually improve account-level medians.

## Review Feedback Verification

The latest review feedback is mostly supported by code evidence:

- `src/ptsm/agent_runtime/nodes/reflector.py` currently evaluates only two conditions: required hashtag and required phrase.
- `src/ptsm/playbooks/definitions/fengkuang_daily_post/playbook.yaml` hard-codes `must_include_phrase: 也算`, while `reflection.md` describes it as preferred wording. The implementation turns that preference into a mandatory publishing shape.
- `src/ptsm/skills/builtin/fengkuang_style/SKILL.md` is too thin to carry the learned patterns from high-interaction samples.
- `src/ptsm/agent_runtime/runtime.py::build_finalize_node()` records execution lessons, but `planner.py` and `executor.py` do not search memory or expose `memory_hits` to drafting.

One adjustment: do not make LLM quality scoring the first hard gate. The plan keeps LLM judging as warning-only until the deterministic mechanics checks and real publish metrics are calibrated.

## External Signals

- Xiaohongshu/Kotler reporting frames the platform around people and life scenes; active user behaviors include search, deep reading, saving, sharing, screenshots, and comments. It also reports strong UGC influence and high daily search volume. Source: <https://www.kotler.com.cn/pdf/2023kmg-xhs.pdf>
- A 2025 Xiaohongshu marketing trend summary reports that emotional expression is now a key seed-planting factor, not just functional selling points. Source: <https://www.fxbaogao.com/detail/5060150>
- QuestMobile's 2025 media ecosystem report says Xiaohongshu continues to expand beyond vertical communities, while users assign different life needs to different platforms. Source: <https://www.questmobile.cn/research/report/2000767092954075138/>
- DT/Jiemian's "发疯工牌" case shows the useful pattern: emotional resonance plus a participation mechanism. One source note says the original note reached 8.4w likes and 2.3w collects, and follow-on UGC helped self-propagation. Source: <https://www.jiemian.com/article/11422876.html>
- QianGua's 2025 anxiety-emotion report summary says anxiety-related commercial notes on Xiaohongshu grew sharply and estimated interactions exceeded 100 million. It splits anxiety into health, appearance, relationship, and survival anxiety. Source: <https://www.growthhk.cn/cgo/product/147096.html>
- BrandStar's 2026 reading of Xiaohongshu emotion methodology argues that emotion needs to be placed in a coordinate system: who, why, and in what situation. Generic empathy is not enough. Source: <https://www.brandstar.com.cn/in-depth/7997>

## What High-Interaction Posts Should Look Like

### 发疯文学

High-performing 发疯文学 is not just "I am tired" plus a hot tag. It usually has all five elements:

1. **Specific social object:** 工牌、群聊、工位、通勤闸机、周报、绩效表、外卖小票, or another object users can copy, photograph, remix, or comment with.
2. **One exact collapse moment:** "领导 18:57 发来一句在吗", "地铁门关上那一秒我想原地退休", not broad summaries like "打工人很累".
3. **Absurd but harmless release:**谐音梗、身份梗、反差句、无攻击性的夸张, avoiding mental-health stigma and direct attacks on real people.
4. **Participation hook:** "把你的工牌疯话交出来", "用你的姓造一句打工人发疯文学", "评论区接一句最想发给老板但不敢发的话".
5. **Soft landing:** 不鸡汤, but gives a tiny self-protection turn: "今天先不把自己交给绩效表", "先把工牌摘了，灵魂下班".

Recommended structures:

- `身份物件 + 反差疯话 + 评论接龙`
- `具体崩溃瞬间 + 一句可复制金句 + 轻量自救`
- `职场规训话术反写 + 用户二创模板`

Avoid:

- 泛化标题: "打工人日常", "职场崩溃实录", "今日已疯"
- 堆热词: "牛马/社畜/发疯/崩溃" without a new scene
- 用心理疾病、咨询、医院当笑点

### 现代心理困境观察

High-performing psychology content should give users two reasons to engage: "这就是我" and "这个我想存下来今晚试." It should stay far away from diagnosis bait.

Required elements:

1. **First-person micro-scene:** 先给一个可以脑补画面的瞬间，例如 "下班路上还在复盘会议里那句话".
2. **Mechanism after scene:** 机制名放在场景之后，例如反刍思维、低控制感、情绪回避、边界压力。
3. **Relief through reframing:** "不是你太敏感" is useful only when followed by a precise reason.
4. **One small tool:** A two-line script, 3-column note, 5-minute timer, message draft, or boundary sentence.
5. **Collectible shape:** Numbered mini-protocol, screenshot-worthy table, or "今晚就能试" checklist.
6. **Boundary without killing the post:** Professional-help reminder at the end, not as the emotional climax.
7. **Comment prompt:** Ask for an example, not an opinion: "你最常反复复盘哪类话？" beats "你怎么看？"

Recommended structures:

- `场景共鸣 -> 机制命名 -> 不是你的错 -> 今晚试一个动作 -> 评论区收集同类场景`
- `一句误解 -> 机制解释 -> 反例/边界 -> 可保存练习`
- `热点情绪词 -> 心理机制 -> 不诊断的安全行动`

Avoid:

- "几条判断你是不是..." style diagnosis bait
- "治好焦虑/治愈抑郁/一招解决" claims
- Pure textbook definitions
- A safe but cold ending that leaves no interaction question

## Content Quality Rubric

Each generated post should be judged on these dimensions before publish:

| Dimension | Pass Condition | Failure Pattern |
| --- | --- | --- |
| Hook specificity | Title/cover name a concrete scene, object, or conflict | Generic trend label |
| First-screen tension | User can understand why to click in one glance | Abstract explanation |
| Platform-native format | Includes a copyable phrase, checklist, comparison, or comment game | Plain essay only |
| Save/share trigger | Gives reusable language, steps, or a screenshot-worthy frame | Only emotional venting |
| Comment trigger | Asks for user examples or completion, not broad opinions | No prompt or "你怎么看" |
| Search fit | Title/body includes 1-2 natural search terms | Hashtags only |
| Persona fit | Feels like a real user, not a brand account or AI explainer | Over-polished, slogan-like |
| Safety | No stigma, diagnosis bait, medical claims, or harassment | Uses mental illness as joke |

## Improvement Strategy

Use three layers instead of trying to "write better" generally:

1. **Research layer:** rebuild the high-engagement sample path after XHS login, and make topic-radar capture not only topics but post mechanics.
2. **Generation layer:** update playbook and skill prompts so every draft must declare its hook mechanism, save trigger, comment trigger, and safety guard.
3. **Evaluation layer:** add deterministic checks for obvious misses and warning-only quality judges for nuanced style/engagement issues.

## Scope

In scope:

- `fengkuang_daily_post`
- `modern_psychology_post`
- `xhs_trend_scan`
- `topic_research`
- playbook-local `evaluation.yaml`
- topic-radar teardown/reporting docs
- warning-only content quality evals
- an operator experiment loop for 2h/24h/72h publish metrics

Out of scope:

- Real publish automation changes before manual evidence is collected
- New Xiaohongshu accounts
- Paid ads or commercial amplification
- Broad platform algorithm reverse engineering
- Medical or clinical psychology products
- Making LLM quality judges required gates before human calibration

---

### Task 1: Fix XHS Evidence Pipeline

**Files:**
- Modify: `src/topic_radar/cli.py`
- Modify: `src/topic_radar/output/artifacts.py`
- Modify: `src/topic_radar/platforms/xiaohongshu.py`
- Modify: `src/topic_radar/analysis/note_teardown.py`
- Test: `tests/unit/topic_radar/test_xiaohongshu_platform.py`
- Test: `tests/unit/topic_radar/test_cli.py` or nearest existing topic-radar CLI tests
- Test: `tests/unit/topic_radar/test_artifacts.py`
- Modify: `docs/operations/topic-radar-runbook.md`
- Create: `docs/research/2026-05-15-xhs-content-quality-sample-set.md`

**Step 1: Write failing tests for raw XHS preservation**

Add a test that builds a LLM-mode `TopicScanResult` from XHS `TrendingItem` inputs and asserts:

```python
assert result.raw_trending
assert result.raw_trending[0]["platform"] == "xiaohongshu"
assert "title" in result.raw_trending[0]
assert "hot_score" in result.raw_trending[0]
```

Expected before implementation: FAIL because `_convert_llm_output()` currently returns no `raw_trending`.

**Step 2: Preserve raw_trending in LLM conversion**

Update `src/topic_radar/cli.py::_convert_llm_output()` to call `_flatten_trending()` or equivalent logic and pass `raw_trending` into `TopicScanResult`.

Expected after implementation: the failing test passes.

**Step 3: Write failing parser test for `data.note` detail payload**

Add a test with payload shaped like:

```python
payload = {
    "feed_id": "note-1",
    "data": {
        "note": {
            "noteId": "note-1",
            "title": "情绪自由才是更高级的情绪管理",
            "desc": "正文",
            "interactInfo": {"likedCount": "13", "collectedCount": "16"},
        },
        "comments": {"list": []},
    },
}
```

Expected before implementation: parser returns `None` or misses fields.

**Step 4: Parse `data.note` and nested comments**

Update `XiaohongshuPlatform.get_feed_detail()` so it accepts:

- top-level `note`
- top-level detail object
- nested `data.note`
- nested `data.comments.list`

Expected after implementation: the parser test passes.

**Step 5: Add bounded teardown failure behavior**

Update the teardown CLI or platform call path so one inaccessible note fails within a configured timeout and reports a compact error, without blocking a whole batch.

Example expected error text:

```text
Failed to fetch detail for feed <id>: note inaccessible or timed out
```

**Step 6: Login preflight**

Run:

```bash
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap xhs-login-qrcode
```

Expected:

- `doctor` reports `xhs_preflight.status == ok`.
- If login is required, operator scans the QR code before continuing.

**Step 7: Collect high-engagement candidates**

Run:

```bash
uv run topic-radar scan \
  --platforms xiaohongshu \
  --keywords "发疯文学,打工人发疯,职场发疯,心理学,情绪管理,职场焦虑,反刍思维" \
  --output-dir outputs/artifacts
```

Expected:

- `outputs/artifacts/topic-scan-YYYY-MM-DD.json` has `raw_trending` with at least 30 candidates.
- At least 10 candidates have non-zero comment or collect counts.

**Step 8: Teardown a balanced sample**

Run `topic-radar teardown` for:

- 5 发疯文学 / 职场情绪 posts
- 5 心理学 / 情绪管理 posts
- 3 negative controls with low interaction

Expected research fields:

- title
- cover text or first image text
- engagement score
- hook type
- opening scene
- save/share trigger
- comment trigger
- top comment themes
- reusable pattern
- safety risks

**verify:**

```bash
uv run pytest -q tests/unit/topic_radar
rg -n "发疯文学|心理学|hook|comment_trigger|save_trigger|engagement_score" \
  docs/research/2026-05-15-xhs-content-quality-sample-set.md
```

**done_when:**

- Research doc contains at least 13 teardown rows.
- Each row explains why the post likely did or did not get interaction.
- The doc separates "topic popularity" from "content mechanic."
- `topic-scan-YYYY-MM-DD.json` preserves raw XHS rows in both LLM and rules paths.
- Detail parser handles `data.note` payloads.

---

### Task 2: Generalize Reflection Policy And Remove Mandatory `也算`

**Files:**
- Modify: `src/ptsm/agent_runtime/nodes/reflector.py`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml`
- Modify: `docs/operations/local-runbook.md`
- Test: `tests/unit/agent_runtime/test_reflector_node.py`
- Test: `tests/integration/test_fengkuang_workflow.py`

**Step 1: Write failing reflector tests**

Create or extend reflector unit tests with three cases:

```python
def test_reflector_accepts_required_hashtag_without_optional_phrase() -> None:
    node = build_reflector_node(max_attempts=2)
    result = node(
        {
            "reflection_rules": {"required_hashtag": "#发疯文学"},
            "draft_content": {
                "body": "领导18:57发在吗，我的工牌先替我下班。评论区接一句工牌背面的疯话。",
                "hashtags": ["#发疯文学"],
            },
        }
    )
    assert result["reflection_decision"] == "finalize"
```

Expected before implementation: FAIL because the node indexes `rules["must_include_phrase"]`.

Add companion tests proving:

- a missing required hashtag still retries/fails;
- a playbook that explicitly sets `must_include_phrase` still enforces it for compatibility.

**Step 2: Make phrase requirements optional**

Update `build_reflector_node()` so:

- `required_hashtag` remains required when configured;
- `must_include_phrase` is enforced only when the value is a non-empty string;
- failure feedback names the missing condition compactly.

**Step 3: Move `也算` from gate to recommendation**

Update fengkuang playbook files:

```yaml
reflection:
  required_hashtag: "#发疯文学"
  recommended_phrases:
    - 也算
    - 至少
    - 还能
```

Change `reflection.md` from "must include" behavior to:

- prefer light positive closure;
- avoid repeating the same closing template across posts;
- reject generic drafts that only satisfy tag/phrase checks.

**Step 4: Update integration expectations**

Replace integration assertions that require `"也算"` with assertions for:

- `#发疯文学` exists;
- body includes a concrete scene/object from the input;
- body includes a comment or completion prompt;
- no forbidden mental-health joke appears.

**verify:**

```bash
uv run pytest -q tests/unit/agent_runtime/test_reflector_node.py tests/integration/test_fengkuang_workflow.py
rg -n "must_include_phrase: 也算|hard-checks.*也算|assert \"也算\"" \
  src/ptsm tests docs/operations/local-runbook.md
```

Expected `rg` result: no mandatory fengkuang `也算` gate remains. References inside positive-reframe recommendations may remain.

**done_when:**

- A fengkuang draft can pass without `也算` when it has the required hashtag and quality mechanics.
- Playbooks that still configure a non-empty `must_include_phrase` keep backward-compatible enforcement.
- Docs no longer claim the reflector hard-checks `也算`.

---

### Task 3: Read Account Memory Before Drafting

**Files:**
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/agent_runtime/graph/builder.py`
- Modify: `src/ptsm/agent_runtime/nodes/planner.py` or create `src/ptsm/agent_runtime/nodes/memory.py`
- Modify: `src/ptsm/agent_runtime/nodes/executor.py`
- Modify: `src/ptsm/agent_runtime/state.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Test: `tests/integration/test_fengkuang_workflow.py`
- Test: `tests/unit/agent_runtime/test_memory_node.py`
- Modify: `docs/operations/local-runbook.md`

**Step 1: Write failing memory retrieval test**

Seed memory before invoking the workflow:

```python
memory.record(
    namespace=("accounts", "acct-fk-001", "lessons"),
    item={
        "playbook_id": "fengkuang_daily_post",
        "scene": "昨天领导18:57发在吗",
        "title": "领导18:57发在吗，我的工牌先疯了",
        "final_body": "评论区接一句工牌背面的疯话。至少先让工牌替我发言。",
    },
)
```

Expected final state after implementation:

```python
assert result["memory_hits"]
assert "Avoid repeating recent account posts" in "\n".join(result["runtime_skill_contents"])
```

Expected before implementation: FAIL because no node searches memory.

**Step 2: Add a bounded memory lookup**

Implement a small node or planner hook that searches:

```python
namespace=("accounts", state["account_id"], "lessons")
```

Keep only the last 3 same-playbook lessons. For each lesson, expose compact fields:

- `scene`
- `title` if present
- first 80-120 chars of `final_body`

Do not change the memory store schema unless required.

**Step 3: Inject anti-repetition context**

Append a runtime context block:

```text
# Recent Account Memory
Avoid repeating recent account posts:
- title shape: ...
- ending: ...
- repeated hotwords: ...
Use a different concrete object, opening sentence, and closing turn.
```

Pass it through `runtime_skill_contents` so both deterministic and LLM drafting backends can consume it.

**Step 4: Persist richer lessons**

Update `finalize` to record `title`, `image_text`, `hashtags`, and a short `final_body` preview in addition to current fields.

**Step 5: Make deterministic drafting visibly use memory**

Update deterministic drafting tests so repeated scenes avoid the exact same title shape or ending when recent memory is present. Keep this simple: the test only needs to prove the memory context is read, not that novelty is perfect.

**verify:**

```bash
uv run pytest -q tests/unit/agent_runtime/test_memory_node.py tests/integration/test_fengkuang_workflow.py tests/unit/infrastructure/llm/test_factory.py
```

**done_when:**

- Workflow state includes `memory_hits` for accounts with prior lessons.
- The drafting prompt/context contains anti-repetition guidance.
- New lessons include enough fields to compare future title, cover, hashtag, and ending repetition.

---

### Task 4: Add Content Mechanics To Runtime Skill Context

**Files:**
- Modify: `src/ptsm/skills/runtime_context.py`
- Test: `tests/unit/skills/test_runtime_context.py`
- Modify: `docs/skills.md`

**Implementation notes:**

- Extend `TrendHit` or nearby rendering logic to infer simple mechanics from title + metrics:
  - `copyable_line`: title includes `文案`, `个签`, `话术`, `请假条`, `清单`, `方法`
  - `comment_chain`: high comments or title/body cue includes `哈哈`, `笑`, `评论`, `补充`
  - `save_tool`: high collects or title cue includes `Tips`, `法则`, `判断`, `反复观看`, `方法`
  - `identity_conflict`: title contains audience/conflict cues such as `打工人`, `工资`, `优秀员工`, `躺平`, `优等生`
- Render a new section in `# XHS Trend Scan Live Context`:

```text
可借鉴内容机制：
- comment_chain: 用一句可接龙的话触发评论补充
- save_tool: 给一个可收藏清单/三栏/话术模板
- copyable_line: 生成一句用户想截图或转发的封面句
```

- Do not put raw sample titles into prompts as copy targets; keep the existing "只借情绪结构，不复写原题" rule.

**verify:**

```bash
uv run pytest -q tests/unit/skills/test_runtime_context.py
```

**done_when:**

- Runtime context includes a mechanics section when search results contain high-signal titles.
- Tests prove `copyable_line`, `comment_chain`, and `save_tool` can be inferred from fake MCP results.
- Docs explain that runtime trend context now carries content mechanics, not just hot titles.

---

### Task 5: Upgrade 发疯文学 Prompts, Skills, And Deterministic Drafts

**Files:**
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml`
- Modify: `src/ptsm/skills/builtin/fengkuang_style/SKILL.md`
- Modify: `src/ptsm/skills/builtin/positive_reframe/SKILL.md`
- Modify: `src/ptsm/skills/builtin/xhs_hashtagging/SKILL.md`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Test: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`

**Prompt changes:**

- Require one concrete social object or repeatable format.
- Require one participation mechanism: comment completion, template fill-in, or remix prompt.
- Require one save/share trigger: reusable line, template, or "发疯金句".
- Forbid mental-health stigma jokes in 发疯文学 output.
- Title and cover must work as a pair:
  - title = conflict or identity
  - cover = exact line users want to screenshot

**Deterministic backend changes:**

- Replace generic fallback titles such as `打工人地铁生存实录`, `会议连环暴击实录`, and `社畜崩溃边缘实录` with scene-specific titles.
- Body must include at least one comment prompt cue, for example `评论区`.
- Body or image text must include one copyable line or reusable format.
- Add DeepSeek hard requirements when `#发疯文学` appears:

```text
必须包含一个具体职场物件或社交对象；必须包含评论区接龙/补充提示；不得用心理疾病、治疗、医院、用药作为笑点。
```

**Example direction:**

Weak:

```text
标题：打工人地铁生存实录
封面：今日已疯
```

Stronger:

```text
标题：领导18:57发「在吗」的那一秒
封面：我的工牌先替我发疯
互动：评论区接一句你最想写在工牌背面的疯话
```

**verify:**

```bash
uv run pytest -q tests/e2e/test_fengkuang_publish_dry_run.py tests/unit/infrastructure/llm/test_factory.py
uv run python -m ptsm.bootstrap run-playbook \
  --scene "领导18:57突然发来一句在吗，明天早会还要我补材料" \
  --account-id acct-fk-local \
  --playbook-id fengkuang_daily_post \
  --eval
```

**done_when:**

- Dry-run output includes a concrete object, a specific collapse moment, a participation prompt, and `#发疯文学`.
- Output does not use mental illness, hospitals, therapy, or medication as joke material.
- Reflection rejects generic titles like "打工人日常" unless they include a concrete twist.
- Deterministic dry-run output now fails if the comment/copyable mechanics are removed.

---

### Task 6: Upgrade Psychology Prompts, Skills, And Deterministic Drafts

**Files:**
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `src/ptsm/skills/builtin/psychology_safety/SKILL.md`
- Modify: `src/ptsm/skills/builtin/xhs_psychology_hashtagging/SKILL.md`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Test: `tests/e2e/test_modern_psychology_publish_dry_run.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`

**Prompt changes:**

- Opening must contain a first-person micro-scene before any concept name.
- Body must include a named mechanism and one non-diagnostic reframe.
- Body must include one "save-worthy" mini-tool:
  - 3-column note
  - 5-minute timer
  - boundary sentence template
  - message draft
  - before/after thought rewrite
- Ending must include one comment prompt asking for a user example.
- Professional boundary remains required but should be concise and placed after the practical tool.

**Deterministic backend changes:**

- Replace `title: 下班后还在复盘那句话` with a sharper scene/reframe title such as `下班后还在复盘一句话，不是你太敏感`.
- Replace `image_text: 脑子还没下班` with a more screenshot-worthy line such as `脑子在替尴尬加班`.
- Body must include a named mini-tool, e.g. `事实 / 猜测 / 下一步` 三栏.
- Body must include an example-based comment prompt.

**Example direction:**

Weak:

```text
标题：下班后还在复盘那句话
封面：脑子还没下班
```

Stronger:

```text
标题：下班后还在复盘一句话，不是你太敏感
封面：脑子在替尴尬加班
工具：事实/猜测/下一步三栏
互动：你最容易反复复盘哪类瞬间？
```

**verify:**

```bash
uv run pytest -q tests/e2e/test_modern_psychology_publish_dry_run.py tests/unit/infrastructure/llm/test_factory.py
uv run python -m ptsm.bootstrap run-playbook \
  --scene "下班路上还在反复复盘会议里一句话，越想越尴尬" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --eval
```

**done_when:**

- Dry-run output includes scene, mechanism, reframe, mini-tool, professional boundary, and example-based comment prompt.
- Output avoids diagnosis bait and treatment claims.
- Hashtags include `#心理学` or `#情绪管理` plus scene-specific tags.
- Deterministic dry-run output preserves the mini-tool and comment prompt.

---

### Task 7: Add Deterministic Content-Quality Contract Checks

**Files:**
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`

**New contract constraints:**

Add support for narrowly deterministic constraints:

```yaml
constraints:
  title_must_not_equal_any:
    - "打工人日常"
    - "打工人地铁生存实录"
    - "社畜崩溃边缘实录"
  image_text_must_not_equal_any:
    - "今日已疯"
    - "脑子还没下班"
  body_must_include_comment_prompt_any:
    - "评论区"
    - "你最"
    - "你们"
  body_must_include_save_trigger_any:
    - "三栏"
    - "清单"
    - "话术"
    - "模板"
    - "步骤"
  body_must_not_include_any:
    - "精神病"
    - "心理医生"
    - "治好焦虑"
```

Rules:

- These checks can be required because they catch obvious misses, not subjective quality.
- Keep them scoped to `executor` final content.
- Do not gate on "will go viral" or "sounds good"; gate only on explicit mechanics and safety.

**verify:**

```bash
uv run pytest -q tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py
uv run python -m ptsm.bootstrap harness-check
```

**done_when:**

- Contract tests fail when generic title, missing comment prompt, missing save trigger, or forbidden mental-health joke appears.
- `eval-artifact` reports `required_failed > 0` for a deliberately weak fixture.
- Existing valid playbook dry-runs pass the new checks after Tasks 5 and 6.

---

### Task 8: Add Warning-Only Content Quality Judge

**Files:**
- Modify: `src/ptsm/evaluations/llm_judge.py`
- Modify: `src/ptsm/application/use_cases/eval_artifact.py`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml`
- Create: `tests/unit/evaluations/test_content_quality_judge.py`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`

**Judge rubric:**

Return structured JSON with:

```json
{
  "score": 0,
  "labels": {
    "hook_specificity": "pass|warn|fail",
    "save_trigger": "pass|warn|fail",
    "comment_trigger": "pass|warn|fail",
    "platform_native_format": "pass|warn|fail",
    "persona_fit": "pass|warn|fail",
    "safety": "pass|warn|fail"
  },
  "reason": "short explanation",
  "rewrite_hint": "one concrete improvement"
}
```

Rules:

- Gate level must be `warning`.
- Default harness must remain deterministic-only unless the judge is explicitly enabled.
- Use fake backend tests; no network required in default test suite.

**verify:**

```bash
uv run pytest -q tests/unit/evaluations/test_content_quality_judge.py tests/unit/application/use_cases/test_eval_artifact.py
uv run python -m ptsm.bootstrap harness-check
```

**done_when:**

- Judge results are stored in `.ptsm/evals` when enabled.
- Harness report shows warning counts but does not block merge on content-quality judge output.
- Docs explain that judge scores require human calibration before becoming gates.

---

### Task 9: Add A Publish Experiment Runbook

**Files:**
- Create: `docs/operations/content-experiment-runbook.md`
- Modify: `docs/operations.md`
- Create: `docs/research/2026-05-15-xhs-content-experiment-log.md`

**Runbook design:**

For each topic, generate three variants:

1. `comment_chain`: optimized for comments and UGC completion
2. `save_tool`: optimized for收藏 and screenshot/save behavior
3. `identity_conflict`: optimized for identity recognition and share

Track:

- publish timestamp
- title
- cover text
- topic source
- variant type
- 2h views/likes/collects/comments/shares
- 24h views/likes/collects/comments/shares
- 72h views/likes/collects/comments/shares
- comment quality notes
- next rewrite decision

Suggested success thresholds for first calibration:

- 24h view count beats recent account median by 50%.
- 24h `(likes + collects + comments*4 + shares*6) / views` improves over recent median.
- Comments contain user examples, not only short praise.
- Collects outpace likes for psychology `save_tool` variants.

**verify:**

```bash
rg -n "comment_chain|save_tool|identity_conflict|2h|24h|72h" \
  docs/operations/content-experiment-runbook.md \
  docs/research/2026-05-15-xhs-content-experiment-log.md
```

**done_when:**

- Operator can run an experiment without changing code.
- The log format makes losing variants useful because they reveal which mechanic failed.
- The runbook separates content metric learning from real publish mechanics.

---

### Task 10: Run A Two-Week Calibration Batch

**Files:**
- Modify: `docs/research/2026-05-15-xhs-content-experiment-log.md`
- Create as needed: `docs/research/YYYY-MM-DD-xhs-content-weekly-review.md`
- Modify after results: `docs/xhs-topics/verticals.md`

**Batch shape:**

- 6 发疯文学 posts:
  - 2 comment_chain
  - 2 identity_conflict
  - 2 save_tool / reusable template
- 6 psychology posts:
  - 3 save_tool
  - 2 identity_conflict
  - 1 comment_chain

**2026-05-16 pre-publish status:** The 12 dry-run candidates for this batch shape are recorded in `docs/research/2026-05-15-xhs-content-experiment-log.md` with `not_published` status and artifact paths. No real publish or metric collection has happened yet; Task 10 remains open until the rows have 24h and 72h metrics and a weekly review converts winners into prompt/eval updates.

**2026-05-16 completion audit:** Current evidence confirms the engineering prep is ready but the publish experiment is not complete. The experiment log has 12 active candidate rows, all 12 referenced local artifacts exist, and the current artifacts passed pre-publish `eval-artifact` with `required_failed = 0` and `warning_failed = 0`. The same audit counted `published_rows = 0`, `rows_with_24h = 0`, and `rows_with_72h = 0`, so the done conditions below are unmet. The local `:18060` xiaohongshu-mcp process is listening as PID `3875`, but its environment has no `COOKIES_PATH`; `curl --max-time 5 http://localhost:18060/api/v1/login/status` timed out with exit code `28`. A cookie file exists at `/Users/wudalu/llm-app/ptsm/cookies.json`, but the active MCP process is not using it.

**Review questions:**

- Did high views come from topic heat or from click-through title/cover?
- Did comments contain user examples?
- Did saves happen because the post had a tool or because the topic was generally useful?
- Did "发疯" posts generate UGC-style completion?
- Did psychology posts avoid diagnosis bait while still being emotionally sharp?

**verify:**

```bash
rg -n "views|likes|collects|comments|shares|decision|rewrite" \
  docs/research/2026-05-15-xhs-content-experiment-log.md
```

**done_when:**

- At least 12 posts have 24h and 72h metrics.
- Weekly review identifies top 3 mechanics and bottom 3 failure patterns.
- Winning mechanics are converted into prompt/eval updates, not just noted manually.

---

### Task 11: Final Harness And Source-Of-Truth Sync

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/topic-radar.md`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`

**verify:**

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --strict
```

**done_when:**

- Source-of-truth docs describe the new content-quality layer.
- All deterministic tests pass.
- Harness strict check passes or reports only documented non-blocking warnings.
- The final handoff includes sample artifacts, eval summaries, and experiment metrics.

## Recommended First Manual Rewrite Tests

Use these as immediate sanity checks before implementing code changes.

### 发疯文学 Test Scene

Scene:

```text
领导18:57突然发来一句在吗，明天早会还要我补材料
```

Expected post mechanic:

- object: 工牌 or 群聊截图
- hook: 下班前新需求
- save/share: 可复制疯话
- comment: "评论区接一句你最想写在工牌背面的疯话"

### Psychology Test Scene

Scene:

```text
下班路上还在反复复盘会议里一句话，越想越尴尬
```

Expected post mechanic:

- scene: 下班路上/会议复盘
- mechanism: 反刍思维
- tool: 事实/猜测/下一步三栏
- comment: "你最容易反复复盘哪类瞬间？"
- safety: concise professional-help boundary

## Decision Rule

Do not judge the next iteration by one viral hit. Judge it by whether the system consistently produces posts with:

- one clear first-screen click reason
- one platform-native participation or save mechanism
- one concrete scene users recognize
- one safe, account-consistent voice
- measurable 24h and 72h deltas against the account's own median
