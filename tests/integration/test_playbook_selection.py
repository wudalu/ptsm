from __future__ import annotations

import importlib


def _load_playbook_contracts() -> tuple[type[object], object]:
    models_module = importlib.import_module("ptsm.application.models")
    use_case_module = importlib.import_module("ptsm.application.use_cases.run_playbook")
    return models_module.PlaybookRequest, use_case_module.run_playbook


def test_generic_playbook_request_defaults_platform_from_account() -> None:
    playbook_request_cls, _ = _load_playbook_contracts()

    request = playbook_request_cls(
        account_id="acct-fk-local",
        scene="周一早高峰地铁通勤",
    )

    assert request.platform is None


def test_run_playbook_routes_through_generic_request_contract() -> None:
    playbook_request_cls, run_playbook = _load_playbook_contracts()

    result = run_playbook(
        playbook_request_cls(
            account_id="acct-fk-local",
            scene="周一早高峰地铁通勤",
        )
    )

    assert result["playbook_id"] == "fengkuang_daily_post"
    assert result["account"]["account_id"] == "acct-fk-local"
