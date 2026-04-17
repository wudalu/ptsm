# PTSM Agent Platform Rebaseline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于当前已经存在的 `fengkuang` 纵切 MVP，重写一份和现有仓库状态一致的实施计划，把 `PTSM` 收敛成真正可扩展的多 playbook agent platform。

**Architecture:** 不再把仓库当成 greenfield scaffold。当前代码已经具备 `accounts + playbooks + skills + dry-run publish + local observability` 的第一条纵切；新的工作重点是把这条纵切抽象成通用 `plan -> execute -> reflect` 运行时、请求级 skill surface、本地可恢复 memory/checkpoint，以及一个第二垂直领域来证明泛化能力。

**Tech Stack:** Python 3.12, `uv`, LangGraph, LangChain, Pydantic v2, YAML/Markdown asset loading, local JSON/JSONL persistence, pytest

## 1. Current Baseline

- 当前仓库已经不是“空仓库”，M0 脚手架验收条件已经满足：
  - `uv sync`
  - `uv run pytest -q`
  - `uv run python -m ptsm.bootstrap --help`
- 当前已有可工作的发疯文学纵切：
  - account registry: `src/ptsm/accounts/registry.py`
  - playbook registry/loader: `src/ptsm/playbooks/registry.py`, `src/ptsm/playbooks/loader.py`
  - skill registry/loader: `src/ptsm/skills/registry.py`, `src/ptsm/skills/loader.py`
  - fengkuang workflow: `src/ptsm/agent_runtime/runtime.py`
  - dry-run publish flow: `src/ptsm/application/use_cases/run_playbook.py`
  - CLI + run artifacts: `src/ptsm/interfaces/cli/main.py`, `src/ptsm/infrastructure/observability/run_store.py`
- 当前主要缺口不是“把文件建出来”，而是“把现有单纵切实现抽象成真正的平台能力”：
  - `agent_runtime` 仍然是 `fengkuang` 专用 runtime，不是通用 graph kernel
  - 没有 request-scoped skill surface / selector
  - 没有通用 playbook request / routing contract
  - memory 仍是纯内存，不支持 thread resume / cross-thread lookup
  - 没有第二个真实垂直领域验证泛化
  - `ptsm run-plan` 仍然没有传 `--skip-git-repo-check`
- 当前目录不在 git repo 内。下面的 “commit” 步骤只在实际 git checkout 中执行；如果当前目录仍不是 git repo，则跳过 commit，但保留任务边界和验证顺序。

## 2. Rebaseline Scope

### In Scope

- 修正本地 `run-plan` 执行入口，避免再次踩 trusted-directory 问题
- 抽出通用 runtime state / graph / nodes
- 引入 request-scoped skill surface 和 selector
- 规范化 playbook/account/request routing contract
- 增加本地持久化 checkpointer 和 memory store
- 用第二个垂直领域验证平台化抽象

### Out Of Scope

- 真实 PostgreSQL / PostgresSaver 上线
- 微信公众号集成
- 监控 Dashboard
- 批量调度器和审批流
- 图片生成链路

## 3. Execution Order

按下面顺序实现：

1. 先修 `run-plan` 和文档基线，保证计划执行入口可信
2. 再抽 runtime kernel
3. 再做 skill surface 和 playbook routing
4. 再补本地持久化 memory/checkpoint
5. 最后增加第二个垂直领域并统一 CLI

---

### Task 1: Harden Local Plan Execution And Baseline Docs

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `README.md`
- Create: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write the failing test**

Add a focused CLI test file that verifies `run_plan_cli()` builds a Codex command with:

- `-C <cwd>`
- `--skip-git-repo-check`
- `--full-auto`
- `--sandbox workspace-write`

Also verify the default state path still lands under `.ptsm/plan_runs/`.

Use assertions along these lines:

```python
def test_run_plan_cli_allows_non_git_directories(monkeypatch, tmp_path: Path) -> None:
    ...
    assert captured["command"] == [
        "codex",
        "exec",
        "-C",
        str(Path.cwd()),
        "--skip-git-repo-check",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "implement task",
    ]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py -q`

Expected: FAIL because `run_plan_cli()` currently omits `--skip-git-repo-check`.

**Step 3: Write minimal implementation**

- Update `run_plan_cli()` in `src/ptsm/interfaces/cli/main.py` to include `--skip-git-repo-check`
- Expand `README.md` from the current stub into a real baseline doc that states:
  - the repo already contains a fengkuang MVP
  - `docs/plans/2026-03-14-ptsm-agent-platform.md` is historical greenfield context
  - this rebaseline plan supersedes it for current execution
  - current stable commands include:
    - `uv run python -m ptsm.bootstrap --help`
    - `uv run pytest -q`
    - `ptsm run-fengkuang ...`
    - `ptsm run-plan ...`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py -q`

Expected: PASS

**Step 5: Run the small regression set**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/plan_runner/test_runner.py tests/unit/test_bootstrap.py -q`

Expected: PASS

**Step 6: Snapshot if inside a git checkout**

```bash
git add README.md src/ptsm/interfaces/cli/main.py tests/unit/interfaces/cli/test_main.py
git commit -m "fix: harden local plan execution entrypoint"
```

---

### Task 2: Extract A Generic Runtime Kernel From The Fengkuang Workflow

**Files:**
- Create: `src/ptsm/agent_runtime/state.py`
- Create: `src/ptsm/agent_runtime/graph/builder.py`
- Create: `src/ptsm/agent_runtime/nodes/ingest.py`
- Create: `src/ptsm/agent_runtime/nodes/planner.py`
- Create: `src/ptsm/agent_runtime/nodes/executor.py`
- Create: `src/ptsm/agent_runtime/nodes/reflector.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Create: `tests/unit/agent_runtime/test_graph_flow.py`
- Create: `tests/integration/test_plan_execute_reflect_loop.py`
- Modify: `tests/integration/test_fengkuang_workflow.py`

**Step 1: Write the failing tests**

Add one unit test for the generic graph and one integration test for the reusable runtime contract.

Required behaviors:

```python
def test_graph_routes_retry_then_finalize() -> None:
    # fake executor fails first draft, reflector returns "retry", second pass "finalize"
    ...
    assert result["status"] == "completed"
    assert result["attempt_count"] == 2

def test_graph_supports_replan_branch() -> None:
    # reflector can force a planner re-entry before finalizing
    ...
    assert result["planner_iterations"] == 2
```

Update the existing fengkuang integration test so it asserts that fengkuang is now a specialization of the generic runtime instead of a one-off graph implementation.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agent_runtime/test_graph_flow.py tests/integration/test_plan_execute_reflect_loop.py tests/integration/test_fengkuang_workflow.py -q`

Expected: FAIL because the generic files and reusable state contract do not exist yet.

**Step 3: Write minimal implementation**

Implement these pieces:

- `state.py`
  - define `ExecutionState` and the reflection decision type
  - include request fields, selected playbook, candidate skills, activated skills, draft/final content, attempt counters, memory hits, run status, and artifact path
- `graph/builder.py`
  - create a reusable `StateGraph` builder that wires:
    - `ingest`
    - `planner`
    - `executor`
    - `reflector`
    - `finalize`
- node modules
  - each node should be a small pure function or adapter wrapper
- `runtime.py`
  - keep a `build_fengkuang_workflow()` compatibility function
  - internally route it through the new generic builder

The final graph must allow reflection to return at least:

- `continue`
- `retry`
- `replan`
- `finalize`
- `fail`

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agent_runtime/test_graph_flow.py tests/integration/test_plan_execute_reflect_loop.py tests/integration/test_fengkuang_workflow.py -q`

Expected: PASS

**Step 5: Run the broader runtime regression set**

Run: `uv run pytest tests/unit/agent_runtime tests/integration/test_fengkuang_workflow.py -q`

Expected: PASS

**Step 6: Snapshot if inside a git checkout**

```bash
git add src/ptsm/agent_runtime tests/unit/agent_runtime/test_graph_flow.py tests/integration/test_plan_execute_reflect_loop.py tests/integration/test_fengkuang_workflow.py
git commit -m "refactor: extract generic runtime kernel"
```

---

### Task 3: Add Request-Scoped Skill Surface And Runtime Activation

**Files:**
- Modify: `src/ptsm/skills/contracts.py`
- Modify: `src/ptsm/skills/registry.py`
- Modify: `src/ptsm/skills/loader.py`
- Create: `src/ptsm/skills/selector.py`
- Create: `src/ptsm/skills/surface.py`
- Modify: `src/ptsm/skills/builtin/fengkuang_style/SKILL.md`
- Modify: `src/ptsm/skills/builtin/positive_reframe/SKILL.md`
- Modify: `src/ptsm/skills/builtin/xhs_hashtagging/SKILL.md`
- Create: `tests/unit/skills/test_selector.py`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_skill_loader.py`

**Step 1: Write the failing tests**

Add tests that require:

```python
def test_skill_registry_parses_scope_tags_from_front_matter() -> None:
    spec = registry.list_skills()[0]
    assert spec.platform_tags == ["xiaohongshu"]
    assert "fengkuang_daily_post" in spec.playbook_tags

def test_selector_returns_request_scoped_surface() -> None:
    surface = selector.select(
        domain="发疯文学",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    assert [item.skill_name for item in surface.list_summaries()] == [...]
    assert "放大具体日常崩溃场景" not in surface.list_summaries()[0].short_description

def test_surface_activates_full_skill_content_on_demand() -> None:
    loaded = surface.activate("fengkuang_style")
    assert "放大具体日常崩溃场景" in loaded.content
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_skill_loader.py tests/unit/skills/test_selector.py -q`

Expected: FAIL because the current skill contract only exposes a flat list of full registry entries.

**Step 3: Write minimal implementation**

- Extend `SkillSpec` so it carries:
  - `domain_tags`
  - `platform_tags`
  - `playbook_tags`
  - `token_budget_hint`
  - `assets_present`
- update the builtin skill front matter to declare those tags
- add `SkillSelector` that narrows the full registry into request-scoped candidates
- add `RequestSkillSurface` that:
  - exposes summaries only
  - loads full markdown only through explicit activation

Use the design decisions in `docs/plans/2026-03-20-ptsm-skill-surface-design.md` as the source of truth.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_skill_loader.py tests/unit/skills/test_selector.py -q`

Expected: PASS

**Step 5: Run the full skill regression set**

Run: `uv run pytest tests/unit/skills -q`

Expected: PASS

**Step 6: Snapshot if inside a git checkout**

```bash
git add src/ptsm/skills tests/unit/skills
git commit -m "feat: add request scoped skill surface"
```

---

### Task 4: Normalize Playbook Routing Around Accounts And Generic Requests

**Files:**
- Modify: `src/ptsm/playbooks/registry.py`
- Modify: `src/ptsm/playbooks/loader.py`
- Modify: `src/ptsm/accounts/registry.py`
- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_loader.py`
- Modify: `tests/unit/accounts/test_account_registry.py`
- Create: `tests/integration/test_playbook_selection.py`

**Step 1: Write the failing tests**

Add tests that require:

```python
def test_playbook_registry_selects_by_account_domain_and_platform() -> None:
    account = accounts.get("acct-fk-local")
    playbook = registry.select_for_account(account=account)
    assert playbook.playbook_id == "fengkuang_daily_post"

def test_generic_playbook_request_defaults_platform_from_account() -> None:
    request = PlaybookRequest(account_id="acct-fk-local", scene="...")
    assert request.platform is None

def test_run_playbook_routes_through_generic_request_contract() -> None:
    result = run_playbook(PlaybookRequest(account_id="acct-fk-local", scene="..."))
    assert result["playbook_id"] == "fengkuang_daily_post"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/accounts/test_account_registry.py tests/integration/test_playbook_selection.py -q`

Expected: FAIL because routing is still bound to `FengkuangRequest` and hard-coded fengkuang selection.

**Step 3: Write minimal implementation**

- Introduce a generic `PlaybookRequest` model in `src/ptsm/application/models.py`
- let account metadata drive default domain/platform selection
- extend playbook definitions so selection can be performed through account + platform + optional explicit playbook override
- refactor `run_playbook.py` so:
  - `run_playbook()` is the generic entrypoint
  - `run_fengkuang_playbook()` becomes a thin compatibility wrapper

Preserve current CLI behavior for `run-fengkuang` while making the internal contract generic.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/accounts/test_account_registry.py tests/integration/test_playbook_selection.py -q`

Expected: PASS

**Step 5: Run the broader routing regression set**

Run: `uv run pytest tests/unit/playbooks tests/unit/accounts tests/integration/test_playbook_selection.py -q`

Expected: PASS

**Step 6: Snapshot if inside a git checkout**

```bash
git add src/ptsm/playbooks src/ptsm/accounts src/ptsm/application/models.py src/ptsm/application/use_cases/run_playbook.py tests/unit/playbooks tests/unit/accounts tests/integration/test_playbook_selection.py
git commit -m "refactor: normalize playbook routing contracts"
```

---

### Task 5: Add Local Persistent Checkpoint And Memory Services

**Files:**
- Create: `src/ptsm/infrastructure/persistence/checkpointer.py`
- Modify: `src/ptsm/infrastructure/memory/store.py`
- Create: `src/ptsm/application/services/memory_service.py`
- Create: `src/ptsm/application/services/memory_write_policy.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Create: `tests/integration/test_thread_memory_resume.py`
- Create: `tests/integration/test_cross_thread_memory_lookup.py`

**Step 1: Write the failing tests**

Add tests that require:

```python
def test_thread_memory_resume_reads_previous_state(tmp_path: Path) -> None:
    result1 = run_playbook(..., thread_id="thread-1")
    result2 = run_playbook(..., thread_id="thread-1")
    assert result2["memory_hits"]

def test_cross_thread_memory_lookup_uses_account_namespace(tmp_path: Path) -> None:
    result = run_playbook(..., account_id="acct-fk-local", thread_id="thread-b")
    assert result["memory_hits"][0]["playbook_id"] == "fengkuang_daily_post"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_thread_memory_resume.py tests/integration/test_cross_thread_memory_lookup.py -q`

Expected: FAIL because the current memory implementation is purely in-memory and process-local.

**Step 3: Write minimal implementation**

- create a local file-backed checkpointer under `.ptsm/checkpoints/`
- upgrade the execution memory store so it can persist account-scoped lessons under `.ptsm/memory/`
- add `MemoryService` and `MemoryWritePolicy` to keep write/read rules out of runtime nodes
- thread IDs must become meaningful across independent CLI invocations

Keep the implementation local-file based for now; the goal is stable interfaces and real resumability, not Postgres yet.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_thread_memory_resume.py tests/integration/test_cross_thread_memory_lookup.py -q`

Expected: PASS

**Step 5: Run the memory + workflow regression set**

Run: `uv run pytest tests/integration/test_thread_memory_resume.py tests/integration/test_cross_thread_memory_lookup.py tests/integration/test_fengkuang_workflow.py -q`

Expected: PASS

**Step 6: Snapshot if inside a git checkout**

```bash
git add src/ptsm/infrastructure/persistence src/ptsm/infrastructure/memory/store.py src/ptsm/application/services src/ptsm/agent_runtime/runtime.py src/ptsm/application/use_cases/run_playbook.py tests/integration/test_thread_memory_resume.py tests/integration/test_cross_thread_memory_lookup.py
git commit -m "feat: add local persistent checkpoint and memory"
```

---

### Task 6: Prove Platform Generality With A Second Vertical Slice And Generic CLI

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/reflection.md`
- Create: `src/ptsm/skills/builtin/english_vocab_teaching/SKILL.md`
- Create: `src/ptsm/skills/builtin/bilingual_examples/SKILL.md`
- Create: `src/ptsm/accounts/definitions/acct-en-local.yaml`
- Modify: `tests/unit/test_bootstrap.py`
- Modify: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Create: `tests/e2e/test_daily_english_publish_dry_run.py`

**Step 1: Write the failing tests**

Add tests that require:

```python
def test_build_parser_supports_run_playbook_command() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "run-playbook",
        "--account-id",
        "acct-en-local",
        "--scene",
        "今天学一个表达感谢的短语",
    ])
    assert args.account_id == "acct-en-local"

def test_run_playbook_cli_outputs_daily_english_dry_run_receipt(capsys) -> None:
    exit_code = main([
        "run-playbook",
        "--account-id",
        "acct-en-local",
        "--scene",
        "今天学一个表达感谢的短语",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert payload["playbook_id"] == "daily_english_post"
    assert payload["publish_result"]["status"] == "dry_run"
```

Keep the existing `run-fengkuang` CLI test and make sure it still passes as a compatibility alias.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bootstrap.py tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py -q`

Expected: FAIL because no generic `run-playbook` command or second built-in playbook exists yet.

**Step 3: Write minimal implementation**

- add a generic `run-playbook` CLI command
- keep `run-fengkuang` as a convenience wrapper for existing automation
- add a deterministic `daily_english_post` playbook with:
  - vocabulary teaching prompt
  - bilingual example output
  - reflection rules for “word + phonetic + example + translation”
- add one local English account profile
- extend the drafting backend factory so the second playbook can run in deterministic dry-run mode without introducing external dependencies

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bootstrap.py tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py -q`

Expected: PASS

**Step 5: Run the full project regression suite**

Run: `uv run pytest -q`

Expected: PASS

**Step 6: Snapshot if inside a git checkout**

```bash
git add src/ptsm/interfaces/cli/main.py src/ptsm/application/models.py src/ptsm/application/use_cases/run_playbook.py src/ptsm/infrastructure/llm/factory.py src/ptsm/playbooks/definitions/daily_english_post src/ptsm/skills/builtin/english_vocab_teaching src/ptsm/skills/builtin/bilingual_examples src/ptsm/accounts/definitions/acct-en-local.yaml tests/unit/test_bootstrap.py tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py
git commit -m "feat: add generic playbook cli and daily english slice"
```

## 4. Done Criteria For This Rebaseline

This rebaseline is complete when all of the following are true:

- `ptsm run-plan` can execute in non-git directories without trusted-directory failures
- runtime logic is organized as generic state + nodes + builder, not only a fengkuang one-off workflow
- skill access is request-scoped and activation-based
- playbook routing works through generic request/account contracts
- thread resume and cross-thread memory lookup work across independent invocations
- at least two vertical slices route through the same platform architecture
- `uv run pytest -q` passes

## 5. Handoff Notes

- The old file `docs/plans/2026-03-14-ptsm-agent-platform.md` should be treated as historical greenfield planning context, not the executable source of truth for the current repo.
- The new source of truth for implementation is this file.
- When executing this plan, do not restart from “empty scaffold” work; start directly at Task 1 above.
