# Multi-Account Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 PTSM 支持多个小红书账号；每个账号绑定独立 `cookie.json` 登录态和默认内容领域，并在登录、预检、发布、排障全链路保持账号隔离。

**Architecture:** 保持现有 `account -> playbook -> runtime -> publisher` 分层，不把多账号逻辑塞进 runtime graph。核心改造点是把账号定义从纯内容元数据扩展为“账号 + cookie profile + 发布执行上下文”，并让发布器、登录命令、doctor、artifact 都按账号解析 cookie profile，而不是只读全局 `Settings.xhs_mcp_server_url` 或共享单一 cookie 状态。

**Tech Stack:** Python 3.12, `uv`, Pydantic v2, YAML account definitions, LangGraph runtime, local JSON artifact/run store, pytest

## Relevant Current Docs Summary

- `docs/playbooks.md` 已经说明 `account_id` 是 playbook 路由入口，但当前账号注册表只提供 `domain/platform/publish_mode` 基础映射。
- `docs/runtime.md` 说明 `run_playbook()` 已经把 `account_id` 带进 run store、artifact、memory namespace 和 publish receipt。
- `docs/architecture.md` 说明账号定义位于 `src/ptsm/accounts/`，发布器适配位于 `src/ptsm/infrastructure/`，应用编排应留在 `src/ptsm/application/`。
- `docs/development-workflow.md` 要求这类能力扩展先定义验证路径，再分任务实施，并在同一变更里同步更新 source-of-truth 文档。
- `docs/research/xhs-mcp-spike.md` 已记录上游 cookie 优先级：`/tmp/cookies.json` -> `COOKIES_PATH` -> 本地 `cookies.json`。这说明多个小红书账号的真正隔离单元是 cookie 文件，而不是昵称或领域。

## Problem Statement

当前仓库已经有多个 `account_id`，但这还不是平台意义上的多账号支持，原因有四个：

1. `src/ptsm/accounts/registry.py` 的 `AccountProfile` 只有内容路由元数据，没有 cookie profile / 会话绑定信息。
2. `src/ptsm/infrastructure/publishers/factory.py`、`src/ptsm/application/use_cases/xhs_login.py`、`src/ptsm/application/use_cases/doctor.py` 都默认走全局 `Settings.xhs_mcp_server_url`。
3. 当前上游登录态实质受 cookie 文件控制；如果平台层不显式建模 cookie profile，多个账号会天然串到同一登录态。
4. `xiaohongshu-mcp` 侧当前可见契约只有“当前服务是否已登录”，没有显式的 `account_id` / `session_id` 选择参数；因此如果继续共用一个全局 server + 全局 cookie，平台无法可靠区分多个运营账号。

## Recommendation

第一阶段采用“每个运营账号绑定一个独立 cookie profile”的方案。

- 每个账号定义自己的 `cookie_profile_id` 与 `cookie_path`，再可选绑定执行该 cookie 的 MCP server endpoint。
- `run-playbook`、`xhs-login-status`、`xhs-login-qrcode`、`doctor` 等入口都先解析 `account_id`，再拿到该账号的 cookie profile。
- artifact、run event、diagnostics 里写入 `cookie_profile_id` / `cookie_path` 摘要 / `server_url`，保证排障时能看出到底是哪个登录态。

不推荐第一阶段做“单 MCP 服务内切换账号”，因为当前上游契约里没有明确的账号选择能力；如果平台自己在客户端伪造切换，会让登录态、发布态和排障态都变得不可信。现实落地上，如果上游只能在进程级通过 `COOKIES_PATH` 读 cookie，那么执行层仍然应该是一号一进程或一号一端点，但平台内的账号主键仍然是 cookie profile。

## Scope

### In Scope

- 账号定义扩展为“内容路由 + cookie profile”
- 账号级 publisher / login / doctor 解析
- CLI 增加账号级运营入口
- 真实发布链路的账号级可观测性和安全护栏
- source-of-truth docs 同步更新

### Out Of Scope

- 多租户数据库或 Web 控制台
- 远端 secret manager
- 单个 MCP 服务内的账号切换协议设计
- 跨平台统一账号中心

## Success Criteria

- 同一仓库内可声明多个小红书账号，且每个账号可绑定独立 `cookie.json`。
- `ptsm run-playbook --account-id ... --publish-mode mcp-real` 会使用该账号绑定的 cookie profile，而不是共享全局 cookie 状态。
- `ptsm xhs-login-status --account-id ...`、`ptsm xhs-login-qrcode --account-id ...`、`ptsm doctor --account-id ...` 都能按账号返回结果。
- artifact / run / diagnose 输出能看出本次运行对应哪个 cookie profile。
- 文档与 harness 验证命令通过。

---

### Task 1: Define Account Cookie Profile Contract

**Files:**
- Modify: `src/ptsm/accounts/registry.py`
- Modify: `src/ptsm/accounts/definitions/acct-fk-local.yaml`
- Modify: `src/ptsm/accounts/definitions/acct-sushi-local.yaml`
- Modify: `src/ptsm/accounts/definitions/acct-wuxia-local.yaml`
- Test: `tests/unit/accounts/test_account_registry.py`
- Docs: `docs/playbooks.md`

**Design:**

- 给 `AccountProfile` 增加账号级 cookie / 执行上下文字段，至少覆盖：
  - `cookie_profile_id`
  - `cookie_path`
  - 可选 `publisher_server_url`
  - 可选 `publisher_visibility`
- `domain` 继续表示默认内容领域，不与 cookie profile 混用。
- `to_dict()` 输出中加入非敏感 cookie profile 摘要，供 artifact 和日志复用；不直接暴露 cookie 内容。
- 保持向后兼容：旧 YAML 不填时可以先落到默认 cookie profile 占位，但 real publish 校验必须阻止未绑定 cookie 的账号。

**verify:**

- `uv run pytest tests/unit/accounts/test_account_registry.py -q`

**done_when:**

- 账号 YAML 可以表达账号级 cookie profile。
- `AccountRegistry().get(...).to_dict()` 能返回 cookie profile 摘要。
- 现有 dry-run 账号定义不因新字段缺省而失效。

### Task 2: Resolve Execution Context Per Account Instead Of Shared Cookie State

**Files:**
- Create: `src/ptsm/application/services/account_publisher_context.py`
- Modify: `src/ptsm/infrastructure/publishers/factory.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/application/use_cases/xhs_login.py`
- Modify: `src/ptsm/application/use_cases/doctor.py`
- Test: `tests/unit/infrastructure/publishers/test_publisher_factory.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/application/use_cases/test_xhs_login.py`
- Test: `tests/unit/application/use_cases/test_doctor.py`
- Docs: `docs/runtime.md`

**Design:**

- 新增应用层 service，把 `account + settings + CLI override` 解析成统一的 execution context。
- 该 context 至少包含：`cookie_profile_id`、`cookie_path`、`server_url`、`visibility`、`resolution_source`。
- `build_publisher()` 不再只吃 `platform/publish_mode/settings`，而是能够接受账号级 cookie profile 与 server URL。
- `run_playbook()` 在 real publish 路径下始终优先使用账号绑定的 cookie profile。
- `xhs_login` / `doctor` 改为支持显式 `account_id`，只有在未指定账号时才允许全局 fallback。
- 如果当前发布器无法直接接收 `cookie_path`，就在这一层把账号解析为独立 MCP endpoint；不要把这种执行层限制泄漏到账号模型。

**verify:**

- `uv run pytest tests/unit/infrastructure/publishers/test_publisher_factory.py -q`
- `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/application/use_cases/test_xhs_login.py tests/unit/application/use_cases/test_doctor.py -q`

**done_when:**

- 账号级 real publish、login preflight、doctor 都使用同一套 execution context 解析。
- 现有 dry-run 路径和 `--server-url` override 仍然可用。
- 测试能证明账号绑定 cookie profile 优先于共享默认状态。

### Task 3: Add Account-Oriented Operator Entry Points

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Create: `src/ptsm/application/use_cases/list_accounts.py`
- Test: `tests/unit/interfaces/cli/test_main.py`
- Test: `tests/unit/test_bootstrap.py`
- Docs: `docs/operations.md`
- Docs: `docs/operations/local-runbook.md`

**Design:**

- 新增 `ptsm accounts`，列出 `account_id / nickname / platform / domain / publish_mode / cookie_profile_id`。
- 为 `xhs-login-status`、`xhs-login-qrcode`、`doctor` 增加 `--account-id`。
- 保留 `--server-url` 作为调试 override，但常规本地运营路径改为账号优先。
- CLI 返回体中明确输出解析后的账号和 cookie profile 摘要。

**verify:**

- `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py -q`

**done_when:**

- 操作员可以先 `ptsm accounts` 看可用账号，再对指定账号执行登录和预检。
- CLI 参数解析与调用链能把 `account_id` 传入相应用例。
- 文档里存在明确的多账号本地运营路径。

### Task 4: Add Cookie-Scoped Publish Safety And Observability

**Files:**
- Create: `src/ptsm/application/services/account_publish_lock.py`
- Modify: `src/ptsm/application/services/side_effect_ledger.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/application/use_cases/diagnose_publish.py`
- Modify: `src/ptsm/application/use_cases/xhs_publish_status.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/application/use_cases/test_diagnose_publish.py`
- Test: `tests/unit/infrastructure/observability/test_run_store.py`
- Docs: `docs/observability.md`

**Design:**

- 为 real publish 增加账号级或 cookie profile 级互斥，避免同一登录态被并发 run 同时写入。
- side-effect ledger key 中纳入 `cookie_profile_id`，避免不同账号因为内容相同被错误复用。
- artifact / run event / diagnose 输出增加 `cookie_profile_id`、`cookie_path` 摘要、`server_url`、preflight source。
- `xhs-check-publish` 与 `diagnose-publish` 优先读 artifact 中的执行上下文，减少人工传参。

**verify:**

- `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/application/use_cases/test_diagnose_publish.py tests/unit/infrastructure/observability/test_run_store.py -q`

**done_when:**

- 同一 cookie profile 下的 real publish 不会被无保护并发执行。
- 诊断输出能定位到具体 cookie profile。
- side-effect 去重不会跨账号串用结果。

### Task 5: End-to-End Multi-Account Dry-Run And Real-Publish Harness Coverage

**Files:**
- Create: `tests/integration/test_multi_account_publisher_resolution.py`
- Modify: `tests/integration/test_playbook_selection.py`
- Modify: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Modify: `tests/e2e/test_sushi_poetry_publish_dry_run.py`
- Docs: `docs/harness-engineering.md`

**Design:**

- 增加集成测试，证明不同 `account_id` 会解析到不同 execution context，但 playbook 选择仍由 `domain/platform` 负责。
- 扩充 E2E dry-run 断言，确保 artifact 中存在 cookie profile 摘要。
- 如果 harness 有固定输出 schema，补齐多账号字段的预期。

**verify:**

- `uv run pytest tests/integration/test_multi_account_publisher_resolution.py tests/integration/test_playbook_selection.py -q`
- `uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_sushi_poetry_publish_dry_run.py -q`

**done_when:**

- 集成和 E2E 测试都能证明“多账号 cookie 上下文”和“playbook 路由”各自职责清晰。
- harness 对新增 cookie profile 字段没有误报。

### Task 6: Final Verification And Docs Sync

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/runtime.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`

**verify:**

- `uv run pytest -q`
- `uv run python -m ptsm.bootstrap doctor --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/accounts/registry.py --changed-path src/ptsm/application/use_cases/run_playbook.py --changed-path src/ptsm/interfaces/cli/main.py`
- `uv run python -m ptsm.bootstrap harness-check --changed-path src/ptsm/accounts/registry.py --changed-path src/ptsm/application/use_cases/run_playbook.py --changed-path src/ptsm/interfaces/cli/main.py`

**done_when:**

- 全量测试通过。
- docs-sync 不再报告 source-of-truth 脱节。
- harness-check 对本次多账号能力变更返回通过状态。

## Rollout Notes

- 第一阶段只承诺“小红书平台多账号 + 每账号独立 cookie profile + 默认领域绑定”。
- 如果上游可以直接以参数形式接收 `cookie_path`，优先做单发布器多 cookie profile；如果上游只能通过 `COOKIES_PATH` 或工作目录解析 cookie，就保持“一账号一 MCP 进程/端点”的执行形态。
- 如果后续上游 `xiaohongshu-mcp` 明确支持单服务多账号切换，再在 execution context 下增加 `session_selector` 一类字段，不要在第一阶段预埋过度抽象。
- 建议先新增第二个 real-publish 测试账号定义，在本地完成 dry-run、cookie 解析、login preflight 验证，再开放真实发布。
