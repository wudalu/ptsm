from __future__ import annotations

import json

from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.llm_judge import run_llm_judge


class FakeJudgeBackend:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def judge(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _target() -> EvalTarget:
    return EvalTarget(
        target_id="run-1:executor:final_content",
        run_id="run-1",
        playbook_id="fengkuang_daily_post",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        phase="executor",
        target_type="artifact_slice",
        output_ref={
            "final_content": {
                "title": "标题",
                "body": "正文",
                "hashtags": ["#发疯文学"],
            }
        },
    )


def test_run_llm_judge_parses_structured_json_result() -> None:
    backend = FakeJudgeBackend(
        json.dumps(
            {
                "score": 0.4,
                "label": "off_persona",
                "reason": "tone is too flat",
                "evidence": [
                    {
                        "path": "final_content.body",
                        "value_preview": "正文",
                        "observation": "flat tone",
                    }
                ],
                "confidence": 0.8,
            }
        )
    )

    result = run_llm_judge(
        _target(),
        evaluator_id="llm.executor.semantic_quality",
        rubric="Check persona and platform fit.",
        backend=backend,
        threshold=0.7,
    )

    assert result.status == "failed"
    assert result.gate_level == "warning"
    assert result.score == 0.4
    assert result.label == "off_persona"
    assert result.reason == "tone is too flat"
    assert result.evidence == [
        {
            "path": "final_content.body",
            "value_preview": "正文",
            "observation": "flat tone",
        }
    ]
    assert "Check persona and platform fit." in backend.prompts[0]


def test_run_llm_judge_invalid_json_becomes_warning_level_error() -> None:
    result = run_llm_judge(
        _target(),
        evaluator_id="llm.executor.semantic_quality",
        rubric="Check persona and platform fit.",
        backend=FakeJudgeBackend("not json"),
        threshold=0.7,
    )

    assert result.status == "error"
    assert result.gate_level == "warning"
    assert "invalid JSON" in result.reason
