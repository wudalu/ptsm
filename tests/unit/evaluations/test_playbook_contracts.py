from __future__ import annotations

from pathlib import Path
import pytest
import tempfile
import yaml
from ptsm.evaluations.playbook_contracts import PlaybookEvalContract, load_playbook_eval_contract


class TestPlaybookEvalContract:
    def test_loads_fengkuang_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "fengkuang_daily_post")
        assert contract is not None
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
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "fengkuang_daily_post")
        assert contract is not None
        nc = contract.node_contracts.get("executor", {})
        assert "title" in nc.get("required_fields", [])
        assert "hashtags" in nc.get("required_fields", [])

    def test_to_dict(self):
        contract = PlaybookEvalContract(
            suite_id="test.default",
            version=2,
            uses={"artifact": "artifact.v1"},
            node_contracts={"finalize": {"required_fields": ["playbook_id"]}},
        )
        d = contract.to_dict()
        assert d["suite_id"] == "test.default"
        assert d["version"] == 2

    def test_loads_modern_psychology_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "modern_psychology_post")
        assert contract is not None
        assert contract.suite_id == "modern_psychology_post.default"
        executor_constraints = contract.node_contracts["executor"]["constraints"]
        assert "#心理学" in executor_constraints["hashtags_must_include_any"]
        assert "诊断" in executor_constraints["body_must_not_include_any"]
        assert "专业帮助" in executor_constraints["body_must_include_all"]
        assert "评论区" in executor_constraints["body_must_include_all"]
