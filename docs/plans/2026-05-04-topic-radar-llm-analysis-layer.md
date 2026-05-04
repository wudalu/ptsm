# Topic Radar LLM Analysis Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace rule-based analysis in topic_radar with LLM-driven semantic analysis. Rules are demoted to pure data normalization. LLM handles all content understanding: vertical discovery, topic value assessment, cross-platform signal interpretation, and angle generation.

**Architecture:** New module `src/topic_radar/analysis/llm_analyzer.py`. Normalization layer stays in `platforms/` and `mcp_client.py`. Old rule-based `cross_platform.py` and `note_teardown.py` are kept as fallback.

**Tech Stack:** Python 3.12, DeepSeek API (reusing PTSM's `deepseek_chat` model), pydantic for output validation.

**Non-goals:**
- Does not modify PTSM internals
- Does not change CLI interface
- Does not remove existing rule-based modules (they serve as fallback)
- Does not introduce streaming or real-time analysis

---

### Design Decisions (pre-approved)

1. **LLM takes raw normalized data, not rule-filtered candidates.** Normalization only does format parsing + dedup + sorting. No clustering, no hook classification, no topic labeling — these are now LLM responsibilities.

2. **Single LLM call per scan.** 40 trending items × 3 platforms = ~120 items max. Prompt is ~3-5K tokens. Structured JSON output via pydantic validation.

3. **Same LLM provider as PTSM.** Reuses `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` from `.env`. Adds `TOPIC_RADAR_LLM_MODEL` (default: `deepseek-chat`) as override.

4. **LLM first, rules as fallback.** No CLI flag. Default path: normalize → LLM analyze → output. If LLM call fails (API error, timeout, invalid response, missing key), silently fall back to rule-based modules. Artifact records `analysis_method: "llm"` or `"rules"`.

---

### Task 1: LLM output schema and validation

**Files:**
- Create: `src/topic_radar/analysis/schemas.py`

**What:**
- Define pydantic models for LLM structured output:
  - `LLMTopicSignal`: `{topic: str, platforms: list[str], discussion_value: str, velocity: str, reason: str}`
  - `LLMVertical`: `{name: str, keywords: list[str], confidence: float, discussion_density: str, sample_topics: list[str], suggested_angles: list[str], comment_themes: list[str]}`
  - `LLMScanOutput`: `{scan_summary: str, cross_platform_signals: list[LLMTopicSignal], discovered_verticals: list[LLMVertical], recommended_angles: list[dict], noise_topics: list[str]}`
- Output from LLM is parsed into these models, validated, then converted to existing `TopicScanResult` format.

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_schemas.py -q
```

**done_when:**
- Valid LLM JSON parses into `LLMScanOutput` without errors
- Invalid JSON raises clear validation errors
- Schema is compatible with existing `TopicScanResult.to_json()` output

---

### Task 2: LLM analyzer module

**Files:**
- Create: `src/topic_radar/analysis/llm_analyzer.py`
- Create: `tests/unit/topic_radar/test_llm_analyzer.py`

**What:**
- `LLMAnalyzer` class:
  - `build_prompt(trending_items, teardowns=None)` → constructs a single prompt containing all normalized data
  - `analyze(trending_items, teardowns=None)` → calls LLM, parses response into `LLMScanOutput`
  - `_fallback_analyze(...)` → delegates to existing rule-based modules
- Prompt design:
  - System: role as content strategy analyst, output JSON only
  - Context: date, platforms scanned, item count
  - Data: normalized trending items with rank, title, hot_score, platform
  - Instructions: discover verticals, find cross-platform signals, assess discussion value, suggest angles, identify noise
  - Output format: JSON schema inline
- Config: reads LLM settings from `TopicRadarConfig` (uses same env vars as PTSM)

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_llm_analyzer.py -q
# Smoke test with real API:
uv run topic-radar scan --platforms weibo,douyin
```

**done_when:**
- Prompt is generated correctly from trending items
- LLM response is parsed into validated `LLMScanOutput`
- Fallback to rule-based path when LLM is unavailable (no API key, network error, invalid response)
- Artifact records `analysis_method`

---

### Task 3: CLI integration

**Files:**
- Modify: `src/topic_radar/cli.py`
- Modify: `src/topic_radar/config.py`

**What:**
- Add `TOPIC_RADAR_LLM_MODEL` env var (default: `deepseek-chat`) in config
- Wire `LLMAnalyzer` into `_scan()`. Default path: normalize → LLM analyze → output. If LLM fails (no API key, network error, invalid response), fallback to rule-based analysis.
- Report which analysis path was used in CLI output and artifact metadata
- No new CLI flags — the switch is automatic

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_cli.py -q
uv run topic-radar scan --platforms weibo
```

**done_when:**
- Scan with valid API key uses LLM path
- Scan without API key falls back to rules
- Artifact records `analysis_method: "llm"` or `"rules"`

---

### Task 4: Prompt validation via recorded test fixtures

**Files:**
- Create: `tests/fixtures/trending_weibo_sample.json`
- Create: `tests/fixtures/expected_llm_output_sample.json`
- Modify: `tests/unit/topic_radar/test_llm_analyzer.py`

**What:**
- Record a real trending_items payload from mcp-trends-hub
- Record the corresponding LLM output for deterministic replay
- Test that prompt construction is deterministic given fixed input
- Test that LLM output schema validation catches malformed responses

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_llm_analyzer.py -q
```

**done_when:**
- Fixture-based tests pass without live API call
- Schema validation edge cases covered (empty items, missing fields, extra fields)

---

### Task 5: Docs and runbook update

**Files:**
- Modify: `docs/topic-radar.md`
- Modify: `docs/operations/topic-radar-runbook.md`
- Modify: `docs/plans/2026-05-04-topic-radar-llm-analysis-layer.md`

**What:**
- Document LLM analysis path in architecture overview
- Document LLM-first with rule fallback behavior
- Note required env vars: `DEEPSEEK_API_KEY` (or `TOPIC_RADAR_LLM_MODEL`)

**verify:**
```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

**done_when:**
- docs/topic-radar.md reflects LLM + rules dual-path architecture
- runbook includes LLM scan examples
- related_paths updated

---

### Task 6: Final verification

**Files:**
- No new files

**What:**
- Run full test suite
- Run production scan with `默认路径` against live weibo+douyin data
- Verify artifact quality improvement over rule-based output
- Commit evidence

**verify:**
```bash
uv run pytest -q
uv run topic-radar scan --platforms weibo,douyin
```

**done_when:**
- All tests pass
- LLM scan produces richer verticals, concrete angles, and non-template output
- Artifact contains `analysis_method: "llm"`
