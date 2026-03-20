from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.xhs_browser import open_xhs_browser


def test_open_xhs_browser_uses_local_qrcode_when_present(tmp_path: Path) -> None:
    qrcode_path = tmp_path / "xhs-login.png"
    qrcode_path.write_bytes(b"fake-png")
    opened: list[str] = []

    result = open_xhs_browser(
        target="login",
        qrcode_output_path=qrcode_path,
        browser_opener=lambda url: opened.append(url) or True,
    )

    assert result["status"] == "opened"
    assert result["destination"].startswith("file://")
    assert opened == [result["destination"]]


def test_open_xhs_browser_uses_artifact_post_url(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "publish_result": {
                    "status": "published",
                    "post_url": "https://www.xiaohongshu.com/explore/demo-post",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    opened: list[str] = []

    result = open_xhs_browser(
        target="artifact",
        artifact_path=artifact_path,
        browser_opener=lambda url: opened.append(url) or True,
    )

    assert result["status"] == "opened"
    assert result["destination"] == "https://www.xiaohongshu.com/explore/demo-post"
    assert opened == ["https://www.xiaohongshu.com/explore/demo-post"]
