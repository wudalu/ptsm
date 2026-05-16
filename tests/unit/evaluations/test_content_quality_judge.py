from __future__ import annotations

import json

from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.llm_judge import run_content_quality_judge


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
                "title": "领导18:57发「在吗」那一秒",
                "image_text": "我的工牌先替我发疯",
                "body": "可复制疯话：收到，但灵魂已下班。评论区接一句工牌背面的疯话。",
                "hashtags": ["#发疯文学"],
            }
        },
    )


def test_content_quality_judge_parses_labels_and_rewrite_hint() -> None:
    backend = FakeJudgeBackend(
        json.dumps(
            {
                "score": 0.42,
                "labels": {
                    "hook_specificity": "pass",
                    "save_trigger": "fail",
                    "comment_trigger": "pass",
                    "platform_native_format": "warn",
                    "persona_fit": "pass",
                    "safety": "pass",
                },
                "reason": "save trigger is too thin",
                "rewrite_hint": "Add a reusable template line users can save.",
            }
        )
    )

    result = run_content_quality_judge(_target(), backend=backend)

    assert result.status == "failed"
    assert result.gate_level == "required"
    assert result.evaluator_id == "llm.executor.content_quality"
    assert result.score == 0.42
    assert result.reason == "save trigger is too thin"
    assert result.evidence == [
        {
            "labels": {
                "hook_specificity": "pass",
                "save_trigger": "fail",
                "comment_trigger": "pass",
                "platform_native_format": "warn",
                "persona_fit": "pass",
                "safety": "pass",
            },
            "rewrite_hint": "Add a reusable template line users can save.",
        }
    ]
    assert "hook_specificity" in backend.prompts[0]
    assert "rewrite_hint" in backend.prompts[0]


def test_content_quality_judge_rejects_missing_labels() -> None:
    result = run_content_quality_judge(
        _target(),
        backend=FakeJudgeBackend(
            json.dumps({"score": 0.9, "reason": "ok", "rewrite_hint": ""})
        ),
    )

    assert result.status == "error"
    assert result.gate_level == "required"
    assert "labels" in result.reason
