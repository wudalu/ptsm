from __future__ import annotations

from ptsm.spikes.xhs_mcp_probe import build_publish_content_args, build_server_config


def test_build_server_config_uses_http_transport() -> None:
    config = build_server_config("http://localhost:18060/mcp")

    assert config == {
        "xiaohongshu": {
            "transport": "http",
            "url": "http://localhost:18060/mcp",
        }
    }


def test_build_publish_content_args_maps_final_content_to_mcp_contract() -> None:
    args = build_publish_content_args(
        final_content={
            "title": "打工人地铁生存实录",
            "image_text": "今日已疯",
            "body": "今天的通勤把我挤成了表情包。",
            "hashtags": ["#发疯文学", "#打工人日常"],
        },
        image_paths=["/tmp/demo-1.jpg", "/tmp/demo-2.jpg"],
    )

    assert args == {
        "title": "打工人地铁生存实录",
        "content": "今天的通勤把我挤成了表情包。",
        "images": ["/tmp/demo-1.jpg", "/tmp/demo-2.jpg"],
        "tags": ["发疯文学", "打工人日常"],
    }
