# Evaluation System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 evaluation system — contract catalog, rule evaluators, contract evaluators, eval store, CLI, and harness integration.

**Architecture:** EvalTarget extraction from artifacts → typed Evaluators (rule/contract) → structured EvalResults → local `.ptsm/evals` store → harness aggregation. LLM judge is warning-only and deferred to later phase.

**Tech Stack:** Python, pytest, local JSON/JSONL, Pydantic/dataclasses, existing RunStore/artifact infrastructure.

---

### Task 1: Write the Contract Catalog and Shared Schema Templates

**Files:**
- Create: `shared_contracts/evaluation/eval_target.schema.yaml`
- Create: `shared_contracts/evaluation/eval_result.schema.yaml`
- Create: `shared_contracts/evaluation/eval_suite.schema.yaml`
- Create: `shared_contracts/evaluation/artifact.schema.yaml`
- Create: `shared_contracts/evaluation/final_content.schema.yaml`
- Create: `shared_contracts/evaluation/skill_activation.schema.yaml`
- Create: `docs/research/2026-05-07-evaluation-contract-catalog.md`

- [ ] **Step 1: Create eval_target schema**

```yaml
# shared_contracts/evaluation/eval_target.schema.yaml
id: eval_target.v1
version: 1
owner: shared evaluation
description: Normalized view of one thing to score in PTSM evaluation.
type: contract
enforcement: required
gate_level: required

fields:
  target_id:
    type: string
    description: "Unique target identifier, e.g. run_id:phase:name"
    required: true
  run_id:
    type: string
    required: true
  artifact_path:
    type: string
    required: false
  playbook_id:
    type: string
    required: true
  account_id:
    type: string
    required: true
  platform:
    type: string
    required: false
  phase:
    type: string
    enum: [ingest, planner, executor, reflector, finalize, image, publish, post_publish, final]
    required: true
  target_type:
    type: string
    enum: [node_output, artifact_slice, event, run_summary]
    required: true
  input_ref:
    type: object
    required: false
  output_ref:
    type: object
    required: false
  metadata:
    type: object
    required: false
    fields:
      skill_names:
        type: list
        required: false
      runtime_context_sources:
        type: list
        required: false
      model_provider:
        type: string
        required: false
```

- [ ] **Step 2: Create eval_result schema**

```yaml
# shared_contracts/evaluation/eval_result.schema.yaml
id: eval_result.v1
version: 1
owner: shared evaluation
description: Structured evaluation result from one evaluator on one target.
type: contract
enforcement: required
gate_level: required

fields:
  eval_result_id:
    type: string
    required: true
  eval_run_id:
    type: string
    required: true
  target_id:
    type: string
    required: true
  evaluator_id:
    type: string
    required: true
  evaluator_version:
    type: string
    required: true
  status:
    type: string
    enum: [passed, failed, warning, skipped, error]
    required: true
  score:
    type: float
    range: [0.0, 1.0]
    required: false
  label:
    type: string
    required: false
  reason:
    type: string
    required: true
  evidence:
    type: list
    required: false
    item:
      type: object
      fields:
        path: string
        value_preview: string
        observation: string
  confidence:
    type: float
    range: [0.0, 1.0]
    required: false
  cost:
    type: object
    required: false
    fields:
      provider: string
      model: string
      input_tokens: integer
      output_tokens: integer
```

- [ ] **Step 3: Create eval_suite schema**

```yaml
# shared_contracts/evaluation/eval_suite.schema.yaml
id: eval_suite.v1
version: 1
owner: shared evaluation
description: Binds evaluators to a scope and thresholds.
type: contract
enforcement: required
gate_level: required

fields:
  suite_id:
    type: string
    required: true
  scope:
    type: object
    required: true
    fields:
      playbook_id: string
      platform: string
      phase: string
  evaluators:
    type: list
    required: true
    item:
      type: object
      fields:
        evaluator_id: string
        version: string
        type: string
        gate_level: string
```

- [ ] **Step 4: Create artifact contract schema**

```yaml
# shared_contracts/evaluation/artifact.schema.yaml
id: artifact.v1
version: 1
owner: shared observability
description: Persisted artifact completeness and run links.
type: contract
enforcement: required
gate_level: required

required_root_fields:
  - playbook_id
  - final_content
  - activated_skill_details
  - scene
  - publish_mode

final_content_required_fields:
  - title
  - body
  - hashtags

run_link_required: true
```

- [ ] **Step 5: Create final_content schema**

```yaml
# shared_contracts/evaluation/final_content.schema.yaml
id: final_content.v1
version: 1
owner: shared content
description: Common title/body/hashtags shape for final content evaluation.
type: contract
enforcement: required
gate_level: required

fields:
  title:
    type: string
    required: true
    max_length: 30
  body:
    type: string
    required: true
  image_text:
    type: string
    required: false
  hashtags:
    type: list
    required: true
    min_items: 1
    max_items: 8
```

- [ ] **Step 6: Create skill_activation contract schema**

```yaml
# shared_contracts/evaluation/skill_activation.schema.yaml
id: skill_activation.v1
version: 1
owner: shared skill/runtime
description: Activated skill and runtime context traceability.
type: contract
enforcement: required
gate_level: required

required_fields:
  - activated_skills
  - activated_skill_details

invariants:
  - all_activated_skills_have_details
  - runtime_skill_details_match_activated
```

- [ ] **Step 7: Create contract catalog document**

```markdown
# Evaluation Contract Catalog

Date: 2026-05-07

| Contract Family | Owner | Purpose | First Gate Level |
| --- | --- | --- | --- |
| eval_target.v1 | shared evaluation | Normalize what gets scored | required |
| eval_result.v1 | shared evaluation | Normalize scores, labels, evidence | required |
| eval_suite.v1 | shared evaluation | Bind evaluators to scope and thresholds | required |
| artifact.v1 | shared observability | Artifact completeness and run links | required |
| final_content.v1 | shared content | Common content shape | required |
| skill_activation.v1 | shared skill/runtime | Skill and context traceability | required |
```

- [ ] **Step 8: Verify and commit**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
git add shared_contracts/evaluation/ docs/research/2026-05-07-evaluation-contract-catalog.md
git commit -m "feat: add evaluation contract catalog and shared schema templates"
```

### Task 2: Define Evaluation Runtime Contracts

**Files:**
- Create: `src/ptsm/evaluations/__init__.py`
- Create: `src/ptsm/evaluations/contracts.py`
- Create: `tests/unit/evaluations/__init__.py`
- Create: `tests/unit/evaluations/test_contracts.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/evaluations/test_contracts.py
from __future__ import annotations

import json
import pytest
from ptsm.evaluations.contracts import EvalTarget, EvalResult, EvaluatorSpec, EvalSuite


class TestEvalTarget:
    def test_roundtrip_to_dict(self):
        target = EvalTarget(
            target_id="run-1:executor:final_content",
            run_id="run-1",
            artifact_path="outputs/artifacts/a.json",
            playbook_id="fengkuang_daily_post",
            account_id="acct-fk-local",
            platform="xiaohongshu",
            phase="executor",
            target_type="artifact_slice",
            metadata={"skill_names": ["fengkuang_style"]},
        )
        d = target.to_dict()
        assert d["target_id"] == "run-1:executor:final_content"
        assert d["phase"] == "executor"
        assert d["metadata"]["skill_names"] == ["fengkuang_style"]

    def test_minimal_target(self):
        target = EvalTarget(
            target_id="r:p:n",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="planner",
            target_type="node_output",
        )
        assert target.artifact_path is None
        assert target.platform is None


class TestEvalResult:
    def test_passed_result(self):
        result = EvalResult(
            eval_result_id="er-1",
            eval_run_id="evrun-1",
            target_id="t-1",
            evaluator_id="artifact_schema.required",
            evaluator_version="1",
            status="passed",
            reason="all required fields present",
        )
        assert result.status == "passed"
        assert result.score is None

    def test_failed_result_with_evidence(self):
        result = EvalResult(
            eval_result_id="er-2",
            eval_run_id="evrun-1",
            target_id="t-2",
            evaluator_id="final_content.hashtags_present",
            evaluator_version="1",
            status="failed",
            score=0.0,
            reason="hashtags list is empty",
            evidence=[
                {"path": "final_content.hashtags", "value_preview": "[]",
                 "observation": "hashtags must be non-empty"},
            ],
        )
        d = result.to_dict()
        assert d["status"] == "failed"
        assert len(d["evidence"]) == 1


class TestEvaluatorSpec:
    def test_rule_evaluator(self):
        spec = EvaluatorSpec(
            evaluator_id="artifact_schema.required",
            version="1",
            type="rule",
            owner="shared evaluation",
            applies_to={"phases": ["finalize"], "playbook_ids": [], "platforms": []},
            threshold=0.8,
            gate_level="required",
        )
        assert spec.type == "rule"
        assert spec.gate_level == "required"


class TestEvalSuite:
    def test_suite_binds_evaluators(self):
        suite = EvalSuite(
            suite_id="fengkuang_daily_post.default",
            scope={"playbook_id": "fengkuang_daily_post", "platform": "xiaohongshu"},
            evaluators=["artifact_schema.required", "final_content.hashtags_present"],
        )
        assert len(suite.evaluators) == 2
        assert suite.scope["playbook_id"] == "fengkuang_daily_post"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest -q tests/unit/evaluations/test_contracts.py -v
# Expected: ImportError / ModuleNotFoundError for ptsm.evaluations.contracts
```

- [ ] **Step 3: Write implementation**

```python
# src/ptsm/evaluations/__init__.py
```

```python
# src/ptsm/evaluations/contracts.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class EvalTarget:
    target_id: str
    run_id: str
    playbook_id: str
    account_id: str
    phase: str
    target_type: str
    artifact_path: str | None = None
    platform: str | None = None
    input_ref: dict[str, Any] | None = None
    output_ref: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class EvalResult:
    eval_result_id: str
    eval_run_id: str
    target_id: str
    evaluator_id: str
    evaluator_version: str
    status: str  # passed | failed | warning | skipped | error
    reason: str
    score: float | None = None
    label: str | None = None
    evidence: list[dict[str, Any]] | None = None
    confidence: float | None = None
    cost: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class EvaluatorSpec:
    evaluator_id: str
    version: str
    type: str  # rule | contract | llm_judge | human_review | aggregate
    owner: str
    applies_to: dict[str, Any] = field(default_factory=dict)
    threshold: float = 0.8
    gate_level: str = "required"  # required | warning | manual_review | experimental

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvalSuite:
    suite_id: str
    scope: dict[str, Any]
    evaluators: list[str]
    thresholds: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest -q tests/unit/evaluations/test_contracts.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ptsm/evaluations/ tests/unit/evaluations/
git commit -m "feat: define evaluation runtime contracts (EvalTarget, EvalResult, EvaluatorSpec, EvalSuite)"
```

---

### Task 3: Load Playbook Evaluation Contracts

**Files:**
- Create: `src/ptsm/evaluations/playbook_contracts.py`
- Create: `src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml`
- Create: `tests/unit/evaluations/test_playbook_contracts.py`

- [ ] **Step 1: Write playbook evaluation contract YAML**

```yaml
# src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml
version: 1
suite_id: fengkuang_daily_post.default
uses:
  final_content: final_content.v1
  artifact: artifact.v1
  skill_activation: skill_activation.v1

node_contracts:
  planner:
    output_contract: skill_activation.v1
    required_fields:
      - selected_playbook
      - activated_skills
      - activated_skill_details
      - planner_prompt
      - persona_prompt
    required_skills:
      from_playbook: true
    runtime_context:
      allowed_missing:
        - xhs_trend_scan
      required_traceability: true

  executor:
    output_schema: final_content.v1
    required_fields:
      - title
      - body
      - image_text
      - hashtags
    constraints:
      title_max_chars: 30
      hashtags_min_count: 1
      hashtags_max_count: 8
      body_must_include_scene_signal: true

  reflector:
    allowed_decisions:
      - retry
      - finalize
      - fail
    invariants:
      - retry_requires_feedback
      - finalize_requires_passing_required_rules

  finalize:
    artifact_schema: artifact.v1
    required_fields:
      - playbook_id
      - final_content
      - activated_skill_details
      - runtime_skill_details
```

- [ ] **Step 2: Write failing tests**

```python
# tests/unit/evaluations/test_playbook_contracts.py
from __future__ import annotations

from pathlib import Path
import pytest
import tempfile
import yaml
from ptsm.evaluations.playbook_contracts import PlaybookEvalContract, load_playbook_eval_contract


class TestPlaybookEvalContract:
    def test_loads_fengkuang_contract(self):
        root = Path(__file__).parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "fengkuang_daily_post")
        assert contract.suite_id == "fengkuang_daily_post.default"
        assert "planner" in contract.node_contracts
        assert "executor" in contract.node_contracts
        assert "finalize" in contract.node_contracts
        assert contract.node_contracts["executor"].get("constraints", {}).get("title_max_chars") == 30

    def test_missing_optional_contract_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            playbook_dir = Path(tmp) / "empty_playbook"
            playbook_dir.mkdir(parents=True)
            (playbook_dir / "playbook.yaml").write_text("playbook_id: empty_playbook")
            result = load_playbook_eval_contract(Path(tmp), "empty_playbook")
            assert result is None

    def test_invalid_node_contract_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            playbook_dir = Path(tmp) / "bad_playbook"
            playbook_dir.mkdir(parents=True)
            (playbook_dir / "playbook.yaml").write_text("playbook_id: bad_playbook")
            (playbook_dir / "evaluation.yaml").write_text("{}")
            with pytest.raises(ValueError, match="suite_id"):
                load_playbook_eval_contract(Path(tmp), "bad_playbook")

    def test_node_contracts_for_phase(self):
        root = Path(__file__).parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "fengkuang_daily_post")
        nc = contract.node_contracts.get("executor", {})
        assert "title" in nc.get("required_fields", [])
        assert "hashtags" in nc.get("required_fields", [])
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest -q tests/unit/evaluations/test_playbook_contracts.py -v
```

- [ ] **Step 4: Write implementation**

```python
# src/ptsm/evaluations/playbook_contracts.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class PlaybookEvalContract:
    suite_id: str
    version: int = 1
    uses: dict[str, str] = field(default_factory=dict)
    node_contracts: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "version": self.version,
            "uses": self.uses,
            "node_contracts": self.node_contracts,
        }


def load_playbook_eval_contract(
    definitions_root: Path, playbook_id: str
) -> PlaybookEvalContract | None:
    eval_path = definitions_root / playbook_id / "evaluation.yaml"
    if not eval_path.exists():
        return None

    raw = yaml.safe_load(eval_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"evaluation.yaml for {playbook_id} must be a mapping")

    suite_id = raw.get("suite_id")
    if not suite_id:
        raise ValueError(f"evaluation.yaml for {playbook_id} must have suite_id")

    return PlaybookEvalContract(
        suite_id=suite_id,
        version=raw.get("version", 1),
        uses=raw.get("uses", {}) or {},
        node_contracts=raw.get("node_contracts", {}) or {},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest -q tests/unit/evaluations/test_playbook_contracts.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/ptsm/evaluations/playbook_contracts.py \
        src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml \
        tests/unit/evaluations/test_playbook_contracts.py
git commit -m "feat: add playbook evaluation contract loader with fengkuang pilot"
```

---

### Task 4: Extract Eval Targets From Artifacts

**Files:**
- Create: `src/ptsm/evaluations/targets.py`
- Create: `tests/unit/evaluations/test_targets.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/evaluations/test_targets.py
from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from ptsm.evaluations.targets import extract_targets_from_artifact
from ptsm.evaluations.contracts import EvalTarget


SAMPLE_ARTIFACT = {
    "playbook_id": "fengkuang_daily_post",
    "scene": "周一早高峰",
    "account": {
        "account_id": "acct-fk-local",
        "platform": "xiaohongshu",
    },
    "publish_mode": "dry-run",
    "activated_skills": ["fengkuang_style", "xhs_hashtagging"],
    "activated_skill_details": [
        {"skill_name": "fengkuang_style", "display_name": "Fengkuang Style"},
        {"skill_name": "xhs_hashtagging", "display_name": "XHS Hashtagging"},
    ],
    "final_content": {
        "title": "测试标题",
        "body": "测试正文内容",
        "image_text": "图片描述",
        "hashtags": ["#发疯文学", "#测试"],
    },
    "runtime_skill_details": [],
    "drafting_provider": "deepseek",
}


class TestTargetExtraction:
    def test_extracts_final_content_target(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        final_targets = [t for t in targets if t.phase == "final"]
        assert len(final_targets) == 1
        assert final_targets[0].target_type == "artifact_slice"
        assert final_targets[0].playbook_id == "fengkuang_daily_post"

    def test_extracts_skill_activation_target(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        skill_targets = [t for t in targets if t.target_type == "node_output" and "skill" in t.target_id]
        assert len(skill_targets) >= 1

    def test_all_targets_have_required_fields(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        for target in targets:
            assert target.target_id
            assert target.run_id == "run-1"
            assert target.playbook_id
            assert target.account_id
            assert target.phase

    def test_target_metadata_includes_skills(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        final = [t for t in targets if t.phase == "final"][0]
        assert final.metadata is not None
        assert "skill_names" in final.metadata
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest -q tests/unit/evaluations/test_targets.py -v
```

- [ ] **Step 3: Write implementation**

```python
# src/ptsm/evaluations/targets.py
from __future__ import annotations

from typing import Any
from ptsm.evaluations.contracts import EvalTarget


def extract_targets_from_artifact(
    artifact: dict[str, Any], *, run_id: str
) -> list[EvalTarget]:
    playbook_id = str(artifact.get("playbook_id", ""))
    account_id = _account_id(artifact)
    platform = _platform(artifact)
    artifact_path = artifact.get("artifact_path")

    skill_names = [
        str(s.get("skill_name"))
        for s in artifact.get("activated_skill_details", [])
        if isinstance(s, dict) and s.get("skill_name")
    ]

    targets: list[EvalTarget] = []

    # Planner target: skill activation
    if artifact.get("activated_skill_details"):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:planner:skill_activation",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="planner",
                target_type="node_output",
                output_ref={
                    "activated_skills": artifact.get("activated_skills"),
                    "activated_skill_details_count": len(
                        artifact.get("activated_skill_details", [])
                    ),
                },
                metadata={
                    "skill_names": skill_names,
                    "runtime_context_sources": [],
                    "model_provider": artifact.get("drafting_provider"),
                },
            )
        )

    # Executor target: final content
    final_content = artifact.get("final_content")
    if isinstance(final_content, dict):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:executor:final_content",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="executor",
                target_type="artifact_slice",
                output_ref={"final_content": final_content},
                metadata={
                    "skill_names": skill_names,
                    "model_provider": artifact.get("drafting_provider"),
                },
            )
        )

    # Final target: artifact completeness
    targets.append(
        EvalTarget(
            target_id=f"{run_id}:final:artifact_completeness",
            run_id=run_id,
            artifact_path=str(artifact_path) if artifact_path else None,
            playbook_id=playbook_id,
            account_id=account_id,
            platform=platform,
            phase="final",
            target_type="artifact_slice",
            output_ref=artifact,
            metadata={
                "skill_names": skill_names,
                "model_provider": artifact.get("drafting_provider"),
            },
        )
    )

    return targets


def _account_id(artifact: dict[str, Any]) -> str:
    account = artifact.get("account")
    if isinstance(account, dict):
        return str(account.get("account_id", ""))
    return str(artifact.get("account_id", ""))


def _platform(artifact: dict[str, Any]) -> str | None:
    account = artifact.get("account")
    if isinstance(account, dict):
        return account.get("platform")
    return artifact.get("platform")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest -q tests/unit/evaluations/test_targets.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ptsm/evaluations/targets.py tests/unit/evaluations/test_targets.py
git commit -m "feat: add eval target extraction from PTSM artifacts"
```

---

### Task 5: Implement Rule Evaluators

**Files:**
- Create: `src/ptsm/evaluations/rules.py`
- Create: `tests/unit/evaluations/test_rules.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/evaluations/test_rules.py
from __future__ import annotations

import pytest
from ptsm.evaluations.contracts import EvalTarget, EvaluatorSpec
from ptsm.evaluations.rules import (
    rule_final_content_fields,
    rule_hashtags_non_empty,
    rule_hashtags_bounded,
    rule_publish_mode_valid,
    rule_no_real_publish_in_dry_run,
    ALL_RULE_EVALUATORS,
)


class TestFinalContentFields:
    def test_passes_when_fields_present(self):
        target = EvalTarget(
            target_id="t:executor:fc",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="executor",
            target_type="artifact_slice",
            output_ref={"final_content": {"title": "T", "body": "B", "hashtags": ["#h"]}},
        )
        result = rule_final_content_fields(target)
        assert result.status == "passed"

    def test_fails_when_title_missing(self):
        target = EvalTarget(
            target_id="t:executor:fc",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="executor",
            target_type="artifact_slice",
            output_ref={"final_content": {"body": "B", "hashtags": ["#h"]}},
        )
        result = rule_final_content_fields(target)
        assert result.status == "failed"
        assert "title" in result.reason.lower()


class TestHashtagsNonEmpty:
    def test_fails_on_empty_hashtags(self):
        target = EvalTarget(
            target_id="t:executor:fc",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="executor",
            target_type="artifact_slice",
            output_ref={"final_content": {"hashtags": []}},
        )
        result = rule_hashtags_non_empty(target)
        assert result.status == "failed"

    def test_passes_on_non_empty_hashtags(self):
        target = EvalTarget(
            target_id="t:executor:fc",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="executor",
            target_type="artifact_slice",
            output_ref={"final_content": {"hashtags": ["#a", "#b"]}},
        )
        result = rule_hashtags_non_empty(target)
        assert result.status == "passed"


class TestHashtagsBounded:
    def test_fails_when_too_many_hashtags(self):
        target = EvalTarget(
            target_id="t:executor:fc",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="executor",
            target_type="artifact_slice",
            output_ref={"final_content": {"hashtags": ["#"] * 10}},
        )
        result = rule_hashtags_bounded(target, max_hashtags=8)
        assert result.status == "failed"


class TestAllRuleEvaluators:
    def test_all_evaluators_registered(self):
        assert len(ALL_RULE_EVALUATORS) >= 5
        ids = [e.evaluator_id for e in ALL_RULE_EVALUATORS]
        assert "final_content.required_fields" in ids
        assert "hashtags.non_empty" in ids
        assert "hashtags.bounded" in ids
        assert "publish_mode.valid" in ids
        assert "publish.dry_run_safety" in ids
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest -q tests/unit/evaluations/test_rules.py -v
```

- [ ] **Step 3: Write implementation**

```python
# src/ptsm/evaluations/rules.py
from __future__ import annotations

from typing import Callable
from ptsm.evaluations.contracts import EvalResult, EvaluatorSpec, EvalTarget


def _make_eval_id(target_id: str, evaluator_id: str) -> str:
    return f"{target_id}:{evaluator_id}"


def _result(
    target_id: str,
    evaluator_id: str,
    status: str,
    reason: str,
    score: float | None = None,
    evidence: list[dict] | None = None,
) -> EvalResult:
    return EvalResult(
        eval_result_id=_make_eval_id(target_id, evaluator_id),
        eval_run_id="",
        target_id=target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status=status,
        reason=reason,
        score=score,
        evidence=evidence or [],
    )


def _get_final_content(target: EvalTarget) -> dict | None:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return None
    fc = ref.get("final_content")
    if isinstance(fc, dict):
        return fc
    return None


def rule_final_content_fields(target: EvalTarget) -> EvalResult:
    fc = _get_final_content(target)
    if fc is None:
        return _result(
            target.target_id, "final_content.required_fields", "failed",
            "final_content not found in target",
        )
    required = ["title", "body", "hashtags"]
    missing = [f for f in required if not fc.get(f)]
    if missing:
        return _result(
            target.target_id, "final_content.required_fields", "failed",
            f"missing required fields: {missing}",
            score=0.0,
            evidence=[{"path": f"final_content.{f}", "value_preview": str(fc.get(f)), "observation": "missing"} for f in missing],
        )
    return _result(
        target.target_id, "final_content.required_fields", "passed",
        "all required fields present",
        score=1.0,
    )


def rule_hashtags_non_empty(target: EvalTarget) -> EvalResult:
    fc = _get_final_content(target)
    if fc is None:
        return _result(target.target_id, "hashtags.non_empty", "skipped", "no final_content")
    hashtags = fc.get("hashtags")
    if not isinstance(hashtags, list) or not hashtags:
        return _result(
            target.target_id, "hashtags.non_empty", "failed",
            "hashtags list is empty or missing",
            score=0.0,
            evidence=[{"path": "final_content.hashtags", "value_preview": str(hashtags), "observation": "empty"}],
        )
    return _result(
        target.target_id, "hashtags.non_empty", "passed",
        f"found {len(hashtags)} hashtags",
        score=1.0,
    )


def rule_hashtags_bounded(target: EvalTarget, max_hashtags: int = 8) -> EvalResult:
    fc = _get_final_content(target)
    if fc is None:
        return _result(target.target_id, "hashtags.bounded", "skipped", "no final_content")
    hashtags = fc.get("hashtags", [])
    if not isinstance(hashtags, list):
        return _result(target.target_id, "hashtags.bounded", "skipped", "hashtags not a list")
    if len(hashtags) > max_hashtags:
        return _result(
            target.target_id, "hashtags.bounded", "failed",
            f"hashtags count {len(hashtags)} exceeds max {max_hashtags}",
            score=0.0,
        )
    return _result(
        target.target_id, "hashtags.bounded", "passed",
        f"hashtags count {len(hashtags)} within limit {max_hashtags}",
        score=1.0,
    )


def rule_publish_mode_valid(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return _result(target.target_id, "publish_mode.valid", "skipped", "no output ref")
    mode = ref.get("publish_mode")
    valid = {"dry-run", "private", "public"}
    if mode not in valid:
        return _result(
            target.target_id, "publish_mode.valid", "failed",
            f"invalid publish_mode: {mode}",
            score=0.0,
        )
    return _result(target.target_id, "publish_mode.valid", "passed", f"valid publish_mode: {mode}", score=1.0)


def rule_no_real_publish_in_dry_run(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return _result(target.target_id, "publish.dry_run_safety", "skipped", "no output ref")
    publish_mode = ref.get("publish_mode", "dry-run")
    publish_result = ref.get("publish_result")
    if publish_mode == "dry-run":
        if isinstance(publish_result, dict) and publish_result.get("status") not in ("dry_run", None):
            return _result(
                target.target_id, "publish.dry_run_safety", "failed",
                "real publish detected in dry-run mode",
                score=0.0,
            )
    return _result(target.target_id, "publish.dry_run_safety", "passed", "dry-run safety ok", score=1.0)


ALL_RULE_EVALUATORS: list[EvaluatorSpec] = [
    EvaluatorSpec("final_content.required_fields", "1", "rule", "shared evaluation",
                   {"phases": ["executor"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
    EvaluatorSpec("hashtags.non_empty", "1", "rule", "shared evaluation",
                   {"phases": ["executor"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
    EvaluatorSpec("hashtags.bounded", "1", "rule", "shared evaluation",
                   {"phases": ["executor"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
    EvaluatorSpec("publish_mode.valid", "1", "rule", "shared evaluation",
                   {"phases": ["final"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
    EvaluatorSpec("publish.dry_run_safety", "1", "rule", "shared evaluation",
                   {"phases": ["final"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest -q tests/unit/evaluations/test_rules.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ptsm/evaluations/rules.py tests/unit/evaluations/test_rules.py
git commit -m "feat: implement rule evaluators for final content, hashtags, publish safety"
```

---

### Task 6: Implement Contract Evaluators

**Files:**
- Create: `src/ptsm/evaluations/contracts_eval.py`
- Create: `tests/unit/evaluations/test_contract_evaluators.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/evaluations/test_contract_evaluators.py
from __future__ import annotations

import pytest
from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.contracts_eval import (
    contract_artifact_root_fields,
    contract_skill_details_match,
    ALL_CONTRACT_EVALUATORS,
)


class TestArtifactRootFields:
    def test_passes_with_all_required(self):
        target = EvalTarget(
            target_id="t:final:ac",
            run_id="r",
            playbook_id="fengkuang_daily_post",
            account_id="acct",
            phase="final",
            target_type="artifact_slice",
            output_ref={
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "T", "body": "B", "hashtags": ["#h"]},
                "activated_skill_details": [{"skill_name": "fs"}],
                "scene": "test",
                "publish_mode": "dry-run",
            },
        )
        result = contract_artifact_root_fields(target)
        assert result.status == "passed"

    def test_fails_with_missing_root_field(self):
        target = EvalTarget(
            target_id="t:final:ac",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="final",
            target_type="artifact_slice",
            output_ref={"playbook_id": "pb"},
        )
        result = contract_artifact_root_fields(target)
        assert result.status == "failed"


class TestSkillDetailsMatch:
    def test_passes_when_skills_match(self):
        target = EvalTarget(
            target_id="t:planner:sa",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="planner",
            target_type="node_output",
            output_ref={
                "activated_skills": ["s1", "s2"],
                "activated_skill_details": [
                    {"skill_name": "s1"},
                    {"skill_name": "s2"},
                ],
            },
        )
        result = contract_skill_details_match(target)
        assert result.status == "passed"

    def test_fails_when_skill_missing_details(self):
        target = EvalTarget(
            target_id="t:planner:sa",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="planner",
            target_type="node_output",
            output_ref={
                "activated_skills": ["s1", "s2", "s3"],
                "activated_skill_details": [
                    {"skill_name": "s1"},
                ],
            },
        )
        result = contract_skill_details_match(target)
        assert result.status == "failed"
        assert "s2" in result.reason.lower() or "s3" in result.reason.lower()


class TestAllContractEvaluators:
    def test_all_registered(self):
        assert len(ALL_CONTRACT_EVALUATORS) >= 2
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest -q tests/unit/evaluations/test_contract_evaluators.py -v
```

- [ ] **Step 3: Write implementation**

```python
# src/ptsm/evaluations/contracts_eval.py
from __future__ import annotations

from ptsm.evaluations.contracts import EvalResult, EvaluatorSpec, EvalTarget
from ptsm.evaluations.rules import _result, _make_eval_id


def contract_artifact_root_fields(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return _result(target.target_id, "artifact.root_fields", "skipped", "no output ref")
    required = ["playbook_id", "final_content", "activated_skill_details", "scene", "publish_mode"]
    missing = [f for f in required if f not in ref]
    if missing:
        return _result(
            target.target_id, "artifact.root_fields", "failed",
            f"missing required root fields: {missing}",
            score=0.0,
        )
    return _result(target.target_id, "artifact.root_fields", "passed", "all required root fields present", score=1.0)


def contract_skill_details_match(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return _result(target.target_id, "skill_activation.details_match", "skipped", "no output ref")
    activated = ref.get("activated_skills")
    details = ref.get("activated_skill_details", [])
    if not isinstance(activated, list) or not isinstance(details, list):
        return _result(
            target.target_id, "skill_activation.details_match", "skipped",
            "activated_skills or activated_skill_details not lists",
        )
    detail_names = {d.get("skill_name") for d in details if isinstance(d, dict) and d.get("skill_name")}
    missing = [s for s in activated if s not in detail_names]
    if missing:
        return _result(
            target.target_id, "skill_activation.details_match", "failed",
            f"activated skills missing details: {missing}",
            score=0.0,
        )
    return _result(
        target.target_id, "skill_activation.details_match", "passed",
        f"all {len(activated)} skills have details",
        score=1.0,
    )


ALL_CONTRACT_EVALUATORS: list[EvaluatorSpec] = [
    EvaluatorSpec("artifact.root_fields", "1", "contract", "shared observability",
                   {"phases": ["final"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
    EvaluatorSpec("skill_activation.details_match", "1", "contract", "shared skill/runtime",
                   {"phases": ["planner"], "playbook_ids": [], "platforms": []}, 1.0, "required"),
]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest -q tests/unit/evaluations/test_contract_evaluators.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ptsm/evaluations/contracts_eval.py tests/unit/evaluations/test_contract_evaluators.py
git commit -m "feat: implement contract evaluators for artifact and skill activation"
```

---

### Task 7: Add Eval Result Store

**Files:**
- Create: `src/ptsm/infrastructure/evaluations/__init__.py`
- Create: `src/ptsm/infrastructure/evaluations/eval_store.py`
- Create: `tests/unit/infrastructure/evaluations/__init__.py`
- Create: `tests/unit/infrastructure/evaluations/test_eval_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/infrastructure/evaluations/test_eval_store.py
from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from ptsm.infrastructure.evaluations.eval_store import EvalStore
from ptsm.evaluations.contracts import EvalResult


class TestEvalStore:
    def test_start_persists_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(suite_id="test_suite", source_kind="artifact", source_path="a.json")
            summary_path = Path(tmp) / handle.eval_run_id / "summary.json"
            assert summary_path.exists()
            summary = json.loads(summary_path.read_text())
            assert summary["suite_id"] == "test_suite"
            assert summary["status"] == "running"

    def test_append_result_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(suite_id="test_suite", source_kind="artifact")
            result = EvalResult(
                eval_result_id="er-1",
                eval_run_id=handle.eval_run_id,
                target_id="t-1",
                evaluator_id="eval-1",
                evaluator_version="1",
                status="passed",
                reason="ok",
            )
            store.append_result(handle.eval_run_id, result)
            results_path = Path(tmp) / handle.eval_run_id / "results.jsonl"
            lines = results_path.read_text().strip().split("\n")
            assert len(lines) == 1
            assert json.loads(lines[0])["status"] == "passed"

    def test_finalize_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(suite_id="test_suite", source_kind="artifact")
            store.finalize(
                handle.eval_run_id,
                status="passed",
                counts={"targets": 3, "evaluators": 5, "passed": 5, "failed": 0, "warnings": 0, "errors": 0},
                gate={"required_failed": 0, "warning_failed": 0},
            )
            summary_path = Path(tmp) / handle.eval_run_id / "summary.json"
            summary = json.loads(summary_path.read_text())
            assert summary["status"] == "passed"
            assert summary["counts"]["passed"] == 5
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest -q tests/unit/infrastructure/evaluations/test_eval_store.py -v
```

- [ ] **Step 3: Write implementation**

```python
# src/ptsm/infrastructure/evaluations/__init__.py
```

```python
# src/ptsm/infrastructure/evaluations/eval_store.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from ptsm.evaluations.contracts import EvalResult


@dataclass(frozen=True)
class EvalRunHandle:
    eval_run_id: str
    run_dir: Path
    results_path: Path
    summary_path: Path


class EvalStore:
    def __init__(self, base_dir: Path | str = ".ptsm/evals") -> None:
        self.base_dir = Path(base_dir)

    def start(
        self,
        *,
        suite_id: str,
        source_kind: str,
        source_path: str | None = None,
    ) -> EvalRunHandle:
        eval_run_id = uuid4().hex[:12]
        run_dir = self.base_dir / eval_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        handle = EvalRunHandle(
            eval_run_id=eval_run_id,
            run_dir=run_dir,
            results_path=run_dir / "results.jsonl",
            summary_path=run_dir / "summary.json",
        )
        summary = {
            "eval_run_id": eval_run_id,
            "suite_id": suite_id,
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": {"kind": source_kind, "path": source_path},
            "counts": {"targets": 0, "evaluators": 0, "passed": 0, "failed": 0, "warnings": 0, "errors": 0},
            "gate": {"required_failed": 0, "warning_failed": 0},
        }
        handle.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return handle

    def append_result(self, eval_run_id: str, result: EvalResult) -> None:
        run_dir = self.base_dir / eval_run_id
        results_path = run_dir / "results.jsonl"
        data = result.to_dict()
        data["eval_run_id"] = eval_run_id
        with results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def finalize(
        self,
        eval_run_id: str,
        *,
        status: str,
        counts: dict[str, int],
        gate: dict[str, int],
    ) -> None:
        run_dir = self.base_dir / eval_run_id
        summary_path = run_dir / "summary.json"
        current = json.loads(summary_path.read_text(encoding="utf-8"))
        current["status"] = status
        current["counts"] = counts
        current["gate"] = gate
        summary_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_eval_runs(self, *, limit: int | None = 10) -> list[dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        dirs = sorted(
            [d for d in self.base_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if limit:
            dirs = dirs[:limit]
        results = []
        for d in dirs:
            summary_path = d / "summary.json"
            if summary_path.exists():
                results.append(json.loads(summary_path.read_text(encoding="utf-8")))
        return results

    def read_results(self, eval_run_id: str) -> list[dict[str, Any]]:
        results_path = self.base_dir / eval_run_id / "results.jsonl"
        if not results_path.exists():
            return []
        results = []
        for line in results_path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                results.append(json.loads(line))
        return results
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest -q tests/unit/infrastructure/evaluations/test_eval_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ptsm/infrastructure/evaluations/ tests/unit/infrastructure/evaluations/
git commit -m "feat: add eval result store for local .ptsm/evals persistence"
```

---

### Task 8: Add eval-artifact Use Case and CLI

**Files:**
- Create: `src/ptsm/application/use_cases/eval_artifact.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Create: `tests/unit/application/use_cases/test_eval_artifact.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/application/use_cases/test_eval_artifact.py
from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from ptsm.application.use_cases.eval_artifact import run_eval_artifact


SAMPLE_ARTIFACT = {
    "playbook_id": "fengkuang_daily_post",
    "scene": "测试",
    "account": {"account_id": "acct-fk-local", "platform": "xiaohongshu"},
    "publish_mode": "dry-run",
    "activated_skills": ["fengkuang_style"],
    "activated_skill_details": [{"skill_name": "fengkuang_style"}],
    "final_content": {
        "title": "测试标题",
        "body": "测试正文",
        "image_text": "图片",
        "hashtags": ["#发疯文学", "#测试"],
    },
    "publish_result": {"status": "dry_run"},
}


class TestRunEvalArtifact:
    def test_returns_summary_with_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8")
            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
            )
            assert result["status"] in {"passed", "failed", "warning"}
            assert "counts" in result
            assert result["counts"]["targets"] >= 2
            assert result["counts"]["evaluators"] >= 5

    def test_missing_artifact_file_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_eval_artifact(
                artifact_path=Path(tmp) / "nonexistent.json",
                evals_base_dir=Path(tmp) / "evals",
            )
            assert result["status"] == "error"

    def test_results_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8")
            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
            )
            eval_run_id = result.get("eval_run_id")
            assert eval_run_id is not None
            results_path = Path(tmp) / "evals" / str(eval_run_id) / "results.jsonl"
            assert results_path.exists()
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest -q tests/unit/application/use_cases/test_eval_artifact.py -v
```

- [ ] **Step 3: Write implementation**

```python
# src/ptsm/application/use_cases/eval_artifact.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ptsm.evaluations.contracts import EvalResult
from ptsm.evaluations.targets import extract_targets_from_artifact
from ptsm.evaluations.rules import ALL_RULE_EVALUATORS, _get_final_content as get_fc
from ptsm.evaluations.rules import (
    rule_final_content_fields,
    rule_hashtags_non_empty,
    rule_hashtags_bounded,
    rule_publish_mode_valid,
    rule_no_real_publish_in_dry_run,
)
from ptsm.evaluations.contracts_eval import (
    contract_artifact_root_fields,
    contract_skill_details_match,
)
from ptsm.infrastructure.evaluations.eval_store import EvalStore


RULE_EVALUATOR_FNS = [
    rule_final_content_fields,
    rule_hashtags_non_empty,
    rule_hashtags_bounded,
    rule_publish_mode_valid,
    rule_no_real_publish_in_dry_run,
]

CONTRACT_EVALUATOR_FNS = [
    contract_artifact_root_fields,
    contract_skill_details_match,
]


def run_eval_artifact(
    *,
    artifact_path: Path | str,
    evals_base_dir: Path | str = ".ptsm/evals",
    run_id: str | None = None,
) -> dict[str, Any]:
    artifact_path = Path(artifact_path)
    if not artifact_path.exists():
        return {"status": "error", "reason": f"artifact not found: {artifact_path}"}

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    effective_run_id = run_id or artifact_path.stem

    targets = extract_targets_from_artifact(artifact, run_id=effective_run_id)
    store = EvalStore(base_dir=evals_base_dir)

    suite_id = f"{artifact.get('playbook_id', 'unknown')}.default"
    handle = store.start(
        suite_id=suite_id,
        source_kind="artifact",
        source_path=str(artifact_path),
    )

    all_results: list[EvalResult] = []
    for target in targets:
        for fn in RULE_EVALUATOR_FNS:
            result = fn(target)
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

        for fn in CONTRACT_EVALUATOR_FNS:
            result = fn(target)
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

    counts = _aggregate_counts(all_results, len(targets))
    gate = _gate_counts(all_results)

    status = "passed"
    if gate["required_failed"] > 0:
        status = "failed"
    elif counts["errors"] > 0:
        status = "error"

    store.finalize(handle.eval_run_id, status=status, counts=counts, gate=gate)

    return {
        "eval_run_id": handle.eval_run_id,
        "status": status,
        "suite_id": suite_id,
        "counts": counts,
        "gate": gate,
        "source": {"kind": "artifact", "path": str(artifact_path)},
    }


def _aggregate_counts(results: list[EvalResult], num_targets: int) -> dict[str, int]:
    return {
        "targets": num_targets,
        "evaluators": len(results),
        "passed": sum(1 for r in results if r.status == "passed"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "warnings": sum(1 for r in results if r.status == "warning"),
        "errors": sum(1 for r in results if r.status == "error"),
    }


def _gate_counts(results: list[EvalResult]) -> dict[str, int]:
    required_failed = sum(
        1 for r in results
        if r.status in ("failed", "error")
    )
    return {
        "required_failed": required_failed,
        "warning_failed": 0,
    }
```

- [ ] **Step 4: Add CLI command**

In `src/ptsm/interfaces/cli/main.py`, add:

```python
# Add import:
from ptsm.application.use_cases.eval_artifact import run_eval_artifact

# In build_parser():
eval_artifact = subparsers.add_parser("eval-artifact")
eval_artifact.add_argument("--artifact", type=Path, required=True)

# In main():
if args.command == "eval-artifact":
    result = run_eval_artifact(artifact_path=args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest -q tests/unit/application/use_cases/test_eval_artifact.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/ptsm/application/use_cases/eval_artifact.py \
        src/ptsm/interfaces/cli/main.py \
        tests/unit/application/use_cases/test_eval_artifact.py
git commit -m "feat: add eval-artifact use case and CLI command"
```

---

### Task 9: Aggregate Eval Results Into Harness

**Files:**
- Modify: `src/ptsm/application/use_cases/harness_evals.py`
- Modify: `src/ptsm/application/use_cases/harness_report.py`
- Modify: `tests/unit/application/use_cases/test_harness_evals.py`
- Modify: `tests/unit/application/use_cases/test_harness_report.py`

- [ ] **Step 1: Add eval aggregation to harness_evals.py**

Add a `_aggregate_eval_results` helper and call it from `run_harness_evals`:

```python
def _aggregate_eval_results(
    evals_base_dir: Path | str = ".ptsm/evals",
) -> dict[str, object]:
    from ptsm.infrastructure.evaluations.eval_store import EvalStore
    store = EvalStore(base_dir=evals_base_dir)
    eval_runs = store.list_eval_runs(limit=None)
    
    statuses = Counter(str(r.get("status", "unknown")) for r in eval_runs)
    suite_ids = Counter(str(r.get("suite_id", "unknown")) for r in eval_runs)
    
    total_passed = 0
    total_failed = 0
    total_warnings = 0
    total_errors = 0
    for r in eval_runs:
        counts = r.get("counts", {})
        if isinstance(counts, dict):
            total_passed += int(counts.get("passed", 0))
            total_failed += int(counts.get("failed", 0))
            total_warnings += int(counts.get("warnings", 0))
            total_errors += int(counts.get("errors", 0))
    
    return {
        "eval_runs_total": len(eval_runs),
        "by_status": dict(statuses),
        "by_suite": dict(suite_ids),
        "results": {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_warnings": total_warnings,
            "total_errors": total_errors,
        },
    }
```

And add `"evals": _aggregate_eval_results()` to the return dict of `run_harness_evals()`.

- [ ] **Step 2: Add eval thresholds to harness_report.py**

Add threshold checks:

```python
def _evaluate_thresholds(...):
    # existing code...
    
    # Add eval thresholds
    max_eval_failures = kwargs.get("max_required_eval_failures")
    if max_eval_failures is not None:
        configured["max_required_eval_failures"] = max_eval_failures
        eval_failures = int(evals.get("evals", {}).get("results", {}).get("total_failed", 0))
        if eval_failures > max_eval_failures:
            violations.append({
                "name": "max_required_eval_failures",
                "actual": eval_failures,
                "expected": f"<= {max_eval_failures}",
            })
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest -q tests/unit/application/use_cases/test_harness_evals.py tests/unit/application/use_cases/test_harness_report.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/ptsm/application/use_cases/harness_evals.py \
        src/ptsm/application/use_cases/harness_report.py \
        tests/unit/application/use_cases/test_harness_evals.py \
        tests/unit/application/use_cases/test_harness_report.py
git commit -m "feat: aggregate eval results into harness-evals and harness-report"
```

---

### Task 10: Update Docs and Run Final Harness

**Files to update:**
- Modify: `docs/observability.md` — add eval artifacts section
- Modify: `docs/harness-engineering.md` — add eval system to "What PTSM Already Has"
- Modify: `docs/operations.md` — add eval-artifact CLI reference
- Possibly modify: `docs/index.md` — add new eval doc references

- [ ] **Step 1: Update docs**

(Details fleshed out during implementation)

- [ ] **Step 2: Run final verification**

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: add evaluation system documentation"
```
