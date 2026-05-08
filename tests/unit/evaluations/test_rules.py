from __future__ import annotations

import pytest
from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.rules import (
    rule_final_content_fields,
    rule_hashtags_non_empty,
    rule_hashtags_bounded,
    rule_publish_mode_valid,
    rule_no_real_publish_in_dry_run,
    ALL_RULE_EVALUATORS,
)


def _target(phase="executor", **overrides):
    defaults = {
        "target_id": "t:executor:fc",
        "run_id": "r",
        "playbook_id": "pb",
        "account_id": "acct",
        "phase": phase,
        "target_type": "artifact_slice",
    }
    defaults.update(overrides)
    return EvalTarget(**defaults)


class TestFinalContentFields:
    def test_passes_when_fields_present(self):
        target = _target(
            output_ref={
                "final_content": {"title": "T", "body": "B", "hashtags": ["#h"]}
            }
        )
        result = rule_final_content_fields(target)
        assert result.status == "passed"

    def test_fails_when_title_missing(self):
        target = _target(
            output_ref={
                "final_content": {"body": "B", "hashtags": ["#h"]}
            }
        )
        result = rule_final_content_fields(target)
        assert result.status == "failed"
        assert "title" in result.reason.lower()

    def test_fails_when_no_final_content(self):
        target = _target(output_ref={})
        result = rule_final_content_fields(target)
        assert result.status == "failed"


class TestHashtagsNonEmpty:
    def test_fails_on_empty_hashtags(self):
        target = _target(
            output_ref={"final_content": {"hashtags": []}}
        )
        result = rule_hashtags_non_empty(target)
        assert result.status == "failed"

    def test_passes_on_non_empty_hashtags(self):
        target = _target(
            output_ref={"final_content": {"hashtags": ["#a", "#b"]}}
        )
        result = rule_hashtags_non_empty(target)
        assert result.status == "passed"

    def test_skipped_without_final_content(self):
        target = _target(output_ref={})
        result = rule_hashtags_non_empty(target)
        assert result.status == "skipped"


class TestHashtagsBounded:
    def test_fails_when_too_many_hashtags(self):
        target = _target(
            output_ref={"final_content": {"hashtags": ["#"] * 10}}
        )
        result = rule_hashtags_bounded(target, max_hashtags=8)
        assert result.status == "failed"

    def test_passes_within_limit(self):
        target = _target(
            output_ref={"final_content": {"hashtags": ["#h1", "#h2"]}}
        )
        result = rule_hashtags_bounded(target)
        assert result.status == "passed"


class TestPublishModeValid:
    def test_fails_on_invalid_mode(self):
        target = _target(phase="final", output_ref={"publish_mode": "invalid"})
        result = rule_publish_mode_valid(target)
        assert result.status == "failed"

    def test_passes_dry_run(self):
        target = _target(phase="final", output_ref={"publish_mode": "dry-run"})
        result = rule_publish_mode_valid(target)
        assert result.status == "passed"


class TestDryRunSafety:
    def test_fails_on_real_publish_in_dry_run(self):
        target = _target(
            phase="final",
            output_ref={
                "publish_mode": "dry-run",
                "publish_result": {"status": "published"},
            },
        )
        result = rule_no_real_publish_in_dry_run(target)
        assert result.status == "failed"

    def test_passes_on_dry_run_status(self):
        target = _target(
            phase="final",
            output_ref={
                "publish_mode": "dry-run",
                "publish_result": {"status": "dry_run"},
            },
        )
        result = rule_no_real_publish_in_dry_run(target)
        assert result.status == "passed"


class TestAllRuleEvaluators:
    def test_all_evaluators_registered(self):
        assert len(ALL_RULE_EVALUATORS) >= 5
        ids = [e.evaluator_id for e in ALL_RULE_EVALUATORS]
        assert "final_content.required_fields" in ids
        assert "hashtags.non_empty" in ids
        assert "hashtags.bounded" in ids
        assert "publish_mode.valid" in ids
        assert "publish.dry_run_safety" in ids
