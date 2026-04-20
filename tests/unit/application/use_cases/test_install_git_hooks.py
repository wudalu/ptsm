from __future__ import annotations

from pathlib import Path

from ptsm.application.use_cases.install_git_hooks import install_git_hooks


def test_install_git_hooks_writes_pre_push_script(monkeypatch, tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)

    def fake_subprocess_run(command, **kwargs):
        class Result:
            stdout = ".git\n"

        return Result()

    monkeypatch.setattr(
        "ptsm.application.use_cases.install_git_hooks.subprocess.run",
        fake_subprocess_run,
    )

    result = install_git_hooks(
        project_root=tmp_path,
        base_ref="origin/main",
    )

    hook_path = git_dir / "hooks" / "pre-push"
    assert result["status"] == "installed"
    assert result["hook_path"] == str(hook_path)
    text = hook_path.read_text(encoding="utf-8")
    assert 'BASE_REF="origin/main"' in text
    assert "ptsm.bootstrap harness-check" in text


def test_install_git_hooks_skips_existing_hook_without_force(
    monkeypatch,
    tmp_path: Path,
) -> None:
    git_dir = tmp_path / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    existing_hook = hooks_dir / "pre-push"
    existing_hook.write_text("#!/bin/sh\n", encoding="utf-8")

    def fake_subprocess_run(command, **kwargs):
        class Result:
            stdout = ".git\n"

        return Result()

    monkeypatch.setattr(
        "ptsm.application.use_cases.install_git_hooks.subprocess.run",
        fake_subprocess_run,
    )

    result = install_git_hooks(project_root=tmp_path)

    assert result["status"] == "skipped"
    assert result["reason"] == "hook_exists"
    assert existing_hook.read_text(encoding="utf-8") == "#!/bin/sh\n"
