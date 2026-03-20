from __future__ import annotations

from ptsm.accounts.registry import AccountProfile
from ptsm.infrastructure.publishers.xiaohongshu_adapter import XiaohongshuAdapter


def test_xiaohongshu_adapter_builds_dry_run_receipt() -> None:
    adapter = XiaohongshuAdapter()
    account = AccountProfile(
        account_id="acct-fk-local",
        nickname="发疯文学实验号",
        platform="xiaohongshu",
        domain="发疯文学",
        publish_mode="dry-run",
    )

    receipt = adapter.publish(
        account=account,
        content={
            "title": "周一打工人的地铁崩溃",
            "image_text": "今日已疯",
            "body": "今天一上地铁就感觉灵魂被折叠。",
            "hashtags": ["#发疯文学", "#打工人日常"],
        },
        artifact_path="outputs/artifacts/demo.json",
        image_paths=[],
        visibility="仅自己可见",
    )

    assert receipt["status"] == "dry_run"
    assert receipt["platform"] == "xiaohongshu"
    assert receipt["account_id"] == "acct-fk-local"
    assert receipt["account_nickname"] == "发疯文学实验号"
    assert receipt["platform_payload"]["content"].endswith("#发疯文学 #打工人日常")
    assert receipt["platform_payload"]["cover_text"] == "今日已疯"
    assert receipt["artifact_path"] == "outputs/artifacts/demo.json"
    assert receipt["platform_payload"]["visibility"] == "仅自己可见"
