# 开放热点发现与赛道路由 — 实施计划

## Goal

把默认热点流程改为“先无预设地发现各平台热点，再将每个有证据的热点路由到现有 playbook、多个候选 playbook，或明确标为未映射”，让运营者在选择后才进入现有的小红书选题/发帖流程。

`xhs-domain-opportunity` 继续承担“给定候选赛道或关键词的 XHS 证据比较”，不再充当泛热点入口；本次不新增 playbook、账号或内容领域。

## Current Docs Summary

- `docs/topic-radar.md` 和 `docs/architecture.md` 将 Topic Radar 定义为独立的八平台采集、证据规范化、聚类与新颖度层；PTSM 只能通过公共 `topic_radar.cli.run_scan()` 使用它，不能反向依赖 PTSM。
- `docs/runtime.md` 规定运行时只可接收已选择的安全选题摘要，不能把来源 URL、作者、token 或原始外部数据带入发帖节点。
- `docs/playbooks.md`、`docs/skills.md` 和 `docs/xhs-topics/*` 将 playbook/skill 定义为已有领域的内容生产与选题引导能力；`xhs-domain-opportunity` 的边界是关键词优先的 XHS 赛道比较。
- `docs/operations.md`、`docs/operations/topic-radar-runbook.md`、`docs/observability.md` 和 `docs/harness-engineering.md` 要求 `completed`、`partial`、`insufficient_evidence` 状态、来源健康度与 artifacts 对操作者可见，且不能把 partial 伪装为全平台结果。

## Diagnosis

1. `run_playbook()` 先解析账号/playbook，再运行 fresh scan，因此 `--fresh-topic-research` 是“既定赛道内补充素材”，不是“先发现后选择”。
2. `xhs-domain-opportunity` 先接收关键词并通过静态 `DOMAIN_MAPPINGS` 做候选比较；这适合验证已有赛道，不适合泛热点发现。
3. Topic Radar 默认会请求八个平台，但 XHS 在无关键词时回退为 `打工人,治愈` 搜索，给开放发现引入了领域偏置。
4. Topic Radar 的规则回退含固定 vertical centers。泛热点到 playbook 的新路由不能把这些预分类当作事实；必须从 `topic_clusters` 和其证据出发，未知/低置信内容必须保持未映射。

## Architecture and Guardrails

```text
8-platform public feeds/searches
          │
          ▼
Topic Radar scan (no domain/playbook/keywords)
          │  TopicCluster + evidence + scan status
          ▼
PTSM hotspot-discovery use case
          │
          ├── existing_playbook_fit  → operator chooses a playbook/account
          ├── ambiguous              → operator chooses among explicit fits
          └── unmapped               → monitor / new-domain-review, never force-fit
          │
          ▼
existing guide-post / run-playbook drafting flow
```

- 泛发现入口不接受 account、playbook、domain 或默认关键词；有定向检索需求时继续使用 Topic Radar 显式关键词扫描或 `xhs-domain-opportunity --keywords`。
- 每个路由项必须保留 cluster id、平台集合、证据数量/强度和 scan quality；`partial` 与 `insufficient_evidence` 原样透传。
- 发现报告默认只展示按 Topic Radar score 排序的前 12 个已验证 cluster；它必须同时写入符合条件总数、实际返回数与展示上限。这个阅读上限不改变扫描范围，也不能成为隐式赛道筛选。
- 若 Top-N 外仍有已映射的既有 playbook 候选，报告可在同一次 scan 的不重复补充区展示它们；每行至少引入一个未展示 playbook，`ambiguous` 保留完整候选。补充区必须与全平台排名分开、带明确 count/limit，且不能影响发现或自动选赛道。
- 路由逻辑是 PTSM domain 纯函数，接收中性值对象，不导入 Topic Radar；只有 application use case 可调用 `run_scan()`。
- 高置信现有赛道才映射；模糊则提供候选，新闻、偶发事件和未知话题不被硬塞进任一内容赛道。一个热点不能仅因“运动”等泛词被错误映射。
- 生成交接只产生 playbook profile 的安全 `generation_seed`；不得把原始标题、URL、作者、feed id、token 或抓取正文注入 `guide-post` / `run-playbook`。
- XHS 无关键词采集改用 MCP 的公开 feed listing 样本。它是“开放样本”，不是全站完整热榜；无登录或工具不可用时必须继续按 `partial` 诚实报告。

## Non-goals

- 不修改任何现有 playbook 的发帖策略、账号、发布权限或自动发布流程。
- 不把 `xhs-domain-opportunity` 改成无关键词的泛发现命令。
- 不以单次热点自动创建新领域；未映射项只进入显式的复盘/新领域评估入口。
- 不改变 Topic Radar 的 artifact schema 或让 Topic Radar import PTSM。

---

### Task 1: Make no-keyword XHS collection genuinely open

**Files:**

- Modify: `src/topic_radar/cli.py`
- Test: `tests/unit/topic_radar/test_cli.py`
- Modify: `docs/topic-radar.md`
- Modify: `docs/operations/topic-radar-runbook.md`

**Steps:**

1. Write a failing test proving `_scan_xiaohongshu()` calls `list_feeds()` when `keywords is None` and does not fall back to `打工人`/`治愈` or `search_feeds()`.
2. Write/retain a test proving explicit `--keywords` still calls `search_feeds()` and keeps the existing keyword splitting and failure reporting behavior.
3. Change the no-keyword branch to collect a bounded XHS feed listing. Preserve the collection mode/diagnostics in the scan output where the existing result model permits it.
4. Document the difference between an open listing sample and a query-filtered XHS search, plus the behavior when XHS is unavailable.

**verify:**

```bash
uv run pytest tests/unit/topic_radar/test_cli.py -q
uv run topic-radar scan --mcp-check
```

**done_when:**

- Default scan has no hidden XHS topical keyword filter.
- Keyword scans remain backward compatible.
- Operator docs do not claim the XHS listing is an exhaustive whole-site ranking.

---

### Task 2: Add evidence-first, pure hotspot-to-playbook routing

**Files:**

- Create: `src/ptsm/domain/hotspot_routing.py`
- Modify: `src/ptsm/playbooks/registry.py`
- Modify: `src/ptsm/playbooks/definitions/*/playbook.yaml`
- Test: `tests/unit/domain/test_hotspot_routing.py`
- Test: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `docs/playbooks.md`

**Steps:**

1. Write failing domain tests for a clear AI/topic profile fit, a clear existing non-AI fit, a genuinely unknown/news event, and an incidental-word false-positive such as `运动鞋`.
2. Add independent optional `hotspot_routing` coverage metadata (`include_any`, optional multi-term `require_all`, and `exclude_any`) to the existing playbook definitions and parse it into a read-only registry field. Do not reuse `trend_keywords`: those are still allowed to steer an already selected playbook's fresh research.
3. Define small immutable routing records and a deterministic pure router that maps a normalized hotspot summary only to existing playbook IDs.
4. Make outputs explicit: `existing_playbook_fit`, `ambiguous`, or `unmapped`; include confidence/reason and a safe profile-derived generation seed only for mapped results.
5. Do not reuse Topic Radar's fixed rule-fallback vertical labels as the source of truth. Unknown or insufficiently specific evidence remains unmapped.
6. Clarify in playbook docs that discovery can recommend an existing playbook but does not create or mutate a playbook.

**verify:**

```bash
uv run pytest tests/unit/domain/test_hotspot_routing.py -q
```

**done_when:**

- Routing has no Topic Radar import and is deterministic under unit tests.
- Unknown and incidental-match hotspots are never force-fit.
- Every mapped ID resolves to an existing playbook definition.

---

### Task 3: Add the independent discovery use case and CLI

**Files:**

- Create: `src/ptsm/application/use_cases/hotspot_discovery.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/application/use_cases/test_hotspot_discovery.py`
- Test: `tests/unit/interfaces/cli/test_main.py`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`

**Steps:**

1. Write a failing use-case test that patches the public `topic_radar.cli.run_scan()` and asserts the generic path calls it without a platform, keyword, account, domain, or playbook selection.
2. Use a completed fixture with real `TopicCluster`/evidence-shaped data to prove outputs are ranked from evidence-backed clusters, then route each cluster after discovery. Validate that every cluster id/fingerprint/evidence relationship is internally consistent before it is eligible.
3. Add fixtures for `partial`, `insufficient_evidence`, and malformed cluster evidence; preserve diagnostics, produce no synthetic recommendations when evidence is insufficient, discard malformed clusters, and never present partial results as exhaustive.
4. Create a JSON and Markdown operator artifact that contains safe routing summaries, source scan artifact references, cluster/platform/evidence context, status, next actions, and a transparent ranked display cap (default 12). It may label a representative title as `operator_headline`, but must never copy evidence/raw-trending rows, URL, author, feed id, token, or raw title into generation handoff fields.
5. Add read-only `ptsm hotspot-discovery` CLI dispatch, `--max-hotspots` display-limit control, and a machine-readable stdout response. It is the only new generic discovery entrypoint.
6. Document the package boundary, safe handoff to selection/drafting, artifact fields, and observability status.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_hotspot_discovery.py tests/unit/interfaces/cli/test_main.py -q
uv run python -m ptsm.bootstrap hotspot-discovery --help
```

**done_when:**

- The default new command is discovery-first and invokes all configured platforms through Topic Radar.
- It preserves score order for the all-platform Top-N while exposing each route status and any separate routed supplement with honest quality status.
- Existing `run-playbook --fresh-topic-research` behavior remains playbook-scoped and compatible.

---

### Task 4: Correct the skill entrypoints and deploy the local skill copies

**Files:**

- Create: `integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md`
- Create: `tests/unit/docs/test_openclaw_topic_radar_discovery_skill.py`
- Modify: `tests/unit/docs/test_openclaw_domain_opportunity_skill.py`
- Modify: `tests/unit/docs/test_hotspot_novelty_docs.py`
- Modify after repository validation: `/Users/wudalu/.codex/skills/ptsm-xhs-domain-opportunity/SKILL.md`
- Create after repository validation: `/Users/wudalu/.codex/skills/ptsm-topic-radar-discovery/SKILL.md`

**Steps:**

1. Before editing wrappers, add failing contract tests for the new discovery wrapper: generic requests run `ptsm hotspot-discovery`, explain `completed`/`partial`/`insufficient_evidence`, prohibit generation/publishing and raw identifiers, and ask the operator to choose a routed result.
2. Add failing tests that the domain-opportunity wrapper requires explicit candidate domains/keywords, retains `--keywords`, and directs generic “find the hot topics” requests to the discovery wrapper instead of inventing a keyword list.
3. Implement the thin versioned wrappers. The new discovery wrapper only discovers/routes; it delegates a chosen existing playbook to the appropriate existing topic-guide/psychology skill.
4. Once repo tests pass, mirror the exact wrapper content into the installed Codex skill locations and use `diff -u` to verify parity. This deployment is intentional because the installed skill is not auto-synced from `integrations/openclaw/`.

**verify:**

```bash
uv run pytest tests/unit/docs/test_openclaw_topic_radar_discovery_skill.py tests/unit/docs/test_openclaw_domain_opportunity_skill.py tests/unit/docs/test_hotspot_novelty_docs.py -q
diff -u integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-domain-opportunity/SKILL.md
diff -u integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md /Users/wudalu/.codex/skills/ptsm-topic-radar-discovery/SKILL.md
```

**done_when:**

- Generic hotspot language resolves to discovery-first, not keyword-first comparison.
- Named domain/keyword comparison remains available and unambiguous.
- Versioned and installed skill files are byte-for-byte aligned.

---

### Task 5: Update the complete documentation surface

**Files:**

- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/topic-radar.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations/topic-radar-runbook.md`
- Modify: `docs/operations/local-runbook.md`
- Modify as needed: `docs/xhs-topics/index.md`, `docs/xhs-topics/skills-landscape.md`, `docs/xhs-topics/harness-integration.md`
- Test: `tests/unit/docs/test_docs_map.py`

**Steps:**

1. Update source-of-truth descriptions and frontmatter `related_paths` for the new use case/domain/CLI/skill paths.
2. Distinguish open multi-platform discovery, targeted Topic Radar search, and XHS candidate-domain comparison in every operator-facing flow.
3. State that unmapped is a successful, expected routing outcome and that a new domain needs deliberate evidence/review rather than automatic creation.
4. Keep the existing fresh research and publish safeguards documented as separate downstream flows.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_hotspot_novelty_docs.py -q
uv run python -m ptsm.bootstrap harness-check --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/skills.md --changed-path docs/operations.md --changed-path docs/topic-radar.md --changed-path docs/harness-engineering.md --changed-path docs/operations/topic-radar-runbook.md --changed-path docs/operations/local-runbook.md
```

**done_when:**

- All required source-of-truth surfaces explain the same discovery-first model.
- No documentation calls keyword-first XHS comparison a generic all-platform hotspot scan.
- Any intentionally unchanged XHS topic document is explicitly recorded in the implementation handoff.

---

### Task 6: Full verification, review, and integration

**Steps:**

1. Run focused tests after each task; then run the complete non-E2E suite.
2. Run the CLI smoke test. Treat live MCP failures as environmental output, not as a substitute for deterministic tests; confirm its reported scan status is honest.
3. Run strict `harness-check` in the isolated worktree.
4. Inspect the final diff, request code review, resolve findings, then merge the feature branch into `main` using the project workflow.

**verify:**

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap hotspot-discovery
uv run python -m ptsm.bootstrap harness-check --base-ref main --strict
git diff --check
git status --short
```

**done_when:**

- Tests, strict harness, and whitespace checks pass in the feature worktree.
- The implementation is merged into local `main`; unrelated root-worktree files remain untouched.
- The handoff states the live scan status observed, the local skill deployment, and whether the requested no-direction discovery flow was verified end-to-end.

## Documentation Review Notes

- `docs/xhs-topics/verticals.md` was reviewed and intentionally left unchanged: it records long-horizon domain investment priorities, while this work only changes the discovery and routing flow.
- `docs/xhs-topics/image-forms-by-domain.md` was reviewed and intentionally left unchanged: no playbook image strategy or image-generation contract changes in this work.
