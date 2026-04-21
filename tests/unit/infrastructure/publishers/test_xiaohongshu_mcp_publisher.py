from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from langchain_core.messages import ToolMessage

from ptsm.accounts.registry import AccountProfile
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import (
    PublisherPreflightError,
    XiaohongshuMcpPublisher,
)


class FakeMcpRunner:
    def __init__(self, responses: dict[str, object]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tool_names(self) -> list[str]:
        return list(self.responses)

    async def invoke_tool(self, tool_name: str, payload: dict[str, object]) -> object:
        self.calls.append((tool_name, payload))
        return self.responses[tool_name]


class ExplodingMcpRunner:
    async def list_tool_names(self) -> list[str]:
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [httpx.ConnectError("All connection attempts failed")],
        )

    async def invoke_tool(self, tool_name: str, payload: dict[str, object]) -> object:
        raise AssertionError("invoke_tool should not be reached")


def build_account() -> AccountProfile:
    return AccountProfile(
        account_id="acct-fk-local",
        nickname="发疯文学实验号",
        platform="xiaohongshu",
        domain="发疯文学",
        publish_mode="dry-run",
    )


def test_xiaohongshu_mcp_publisher_publishes_after_login_preflight(tmp_path: Path) -> None:
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"fake-image")
    runner = FakeMcpRunner(
        {
            "check_login_status": [{"type": "text", "text": "✅ 已登录"}],
            "publish_content": [{"type": "text", "text": "内容发布成功: 发布完成"}],
        }
    )
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=runner,
    )

    receipt = publisher.publish(
        account=build_account(),
        content={
            "title": "打工人发疯验证",
            "body": "今天开会开到灵魂出窍。",
            "hashtags": ["#发疯文学", "#打工人日常"],
        },
        artifact_path="outputs/artifacts/demo.json",
        image_paths=[str(image_path)],
        visibility="仅自己可见",
    )

    assert receipt["status"] == "published"
    assert receipt["platform"] == "xiaohongshu"
    assert receipt["provider"] == "xiaohongshu_mcp"
    assert receipt["platform_payload"]["images"] == [str(image_path)]
    assert receipt["platform_payload"]["visibility"] == "仅自己可见"
    assert runner.calls[0] == ("check_login_status", {})
    assert runner.calls[1][0] == "publish_content"
    assert runner.calls[1][1]["tags"] == ["发疯文学", "打工人日常"]
    assert runner.calls[1][1]["visibility"] == "仅自己可见"


def test_xiaohongshu_mcp_publisher_requires_login(tmp_path: Path) -> None:
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"fake-image")
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=FakeMcpRunner(
            {
                "check_login_status": [{"type": "text", "text": "❌ 未登录"}],
                "publish_content": [{"type": "text", "text": "不会执行"}],
            }
        ),
    )

    with pytest.raises(PublisherPreflightError, match="not logged in") as exc_info:
        publisher.publish(
            account=build_account(),
            content={
                "title": "打工人发疯验证",
                "body": "今天开会开到灵魂出窍。",
                "hashtags": ["#发疯文学"],
            },
            artifact_path="outputs/artifacts/demo.json",
            image_paths=[str(image_path)],
            visibility="仅自己可见",
        )

    assert exc_info.value.preflight["status"] == "login_required"
    assert exc_info.value.preflight["login_status"] == "❌ 未登录"


def test_xiaohongshu_mcp_publisher_preflight_returns_qrcode_metadata() -> None:
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=FakeMcpRunner(
            {
                "check_login_status": [{"type": "text", "text": "❌ 未登录"}],
                "get_login_qrcode": [
                    {
                        "type": "text",
                        "text": '{"timeout":"4m0s","is_logged_in":false,"img":"data:image/png;base64,abc"}',
                    }
                ],
            }
        ),
    )

    preflight = publisher.preflight()

    assert preflight["status"] == "login_required"
    assert preflight["login_status"] == "❌ 未登录"
    assert preflight["qrcode"]["timeout"] == "4m0s"
    assert preflight["qrcode"]["is_logged_in"] is False
    assert preflight["qrcode"]["img"] == "data:image/png;base64,abc"


def test_xiaohongshu_mcp_publisher_preflight_surfaces_connection_errors() -> None:
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=ExplodingMcpRunner(),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to connect to xiaohongshu-mcp server at http://localhost:18060/mcp",
    ):
        publisher.preflight()


def test_xiaohongshu_mcp_publisher_requires_at_least_one_existing_image(tmp_path: Path) -> None:
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=FakeMcpRunner(
            {
                "check_login_status": [{"type": "text", "text": "✅ 已登录"}],
                "publish_content": [{"type": "text", "text": "不会执行"}],
            }
        ),
    )

    with pytest.raises(ValueError, match="At least one image path"):
        publisher.publish(
            account=build_account(),
            content={
                "title": "打工人发疯验证",
                "body": "今天开会开到灵魂出窍。",
                "hashtags": ["#发疯文学"],
            },
            artifact_path="outputs/artifacts/demo.json",
            image_paths=[],
            visibility="仅自己可见",
        )


def test_xiaohongshu_mcp_publisher_extracts_publish_metadata_from_json_response(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"fake-image")
    runner = FakeMcpRunner(
        {
            "check_login_status": [{"type": "text", "text": "✅ 已登录"}],
            "publish_content": [
                {
                    "type": "text",
                    "text": '{"post_id":"note-123","post_url":"https://www.xiaohongshu.com/explore/note-123"}',
                }
            ],
        }
    )
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=runner,
    )

    receipt = publisher.publish(
        account=build_account(),
        content={
            "title": "打工人发疯验证",
            "body": "今天开会开到灵魂出窍。",
            "hashtags": ["#发疯文学"],
        },
        artifact_path="outputs/artifacts/demo.json",
        image_paths=[str(image_path)],
        visibility="仅自己可见",
    )

    assert receipt["post_id"] == "note-123"
    assert receipt["post_url"] == "https://www.xiaohongshu.com/explore/note-123"


def test_xiaohongshu_mcp_publisher_extracts_publish_metadata_from_tool_message_artifact(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"fake-image")
    runner = FakeMcpRunner(
        {
            "check_login_status": [{"type": "text", "text": "✅ 已登录"}],
            "publish_content": ToolMessage(
                content=[{"type": "text", "text": "内容发布成功: 发布完成"}],
                artifact={
                    "structured_content": {
                        "note_id": "note-456",
                        "note_url": "https://www.xiaohongshu.com/explore/note-456",
                    }
                },
                tool_call_id="tool-call-publish-content",
                name="publish_content",
            ),
        }
    )
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=runner,
    )

    receipt = publisher.publish(
        account=build_account(),
        content={
            "title": "打工人发疯验证",
            "body": "今天开会开到灵魂出窍。",
            "hashtags": ["#发疯文学"],
        },
        artifact_path="outputs/artifacts/demo.json",
        image_paths=[str(image_path)],
        visibility="仅自己可见",
    )

    assert receipt["post_id"] == "note-456"
    assert receipt["post_url"] == "https://www.xiaohongshu.com/explore/note-456"


def test_xiaohongshu_mcp_publisher_checks_publish_status_when_tool_available() -> None:
    runner = FakeMcpRunner(
        {
            "check_login_status": [{"type": "text", "text": "✅ 已登录"}],
            "check_publish_status": [
                {
                    "type": "text",
                    "text": '{"status":"published_visible","post_id":"note-123"}',
                }
            ],
        }
    )
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=runner,
    )

    result = publisher.check_publish_status(post_id="note-123")

    assert result["status"] == "published_visible"
    assert result["post_id"] == "note-123"
    assert result["source"] == "mcp"


def test_xiaohongshu_mcp_publisher_finds_exact_title_match_via_search() -> None:
    runner = FakeMcpRunner(
        {
            "search_feeds": [
                {
                    "type": "text",
                    "text": """
                    {
                      "feeds": [
                        {
                          "id": "note-123",
                          "xsecToken": "xsec-123",
                          "noteCard": {
                            "displayTitle": "周日晚上，我的灵魂已经提前在工位坐牢"
                          }
                        }
                      ]
                    }
                    """,
                }
            ],
        }
    )
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=runner,
    )

    result = publisher.find_published_note(
        title="周日晚上，我的灵魂已经提前在工位坐牢",
        body="至少今晚还能再瘫两小时，也算最后的狂欢。",
    )

    assert result == {
        "post_id": "note-123",
        "post_url": "https://www.xiaohongshu.com/explore/note-123",
        "source": "mcp_search",
        "xsec_token": "xsec-123",
    }


def test_xiaohongshu_mcp_publisher_rejects_fuzzy_search_matches() -> None:
    runner = FakeMcpRunner(
        {
            "search_feeds": [
                {
                    "type": "text",
                    "text": """
                    {
                      "feeds": [
                        {
                          "id": "note-123",
                          "xsecToken": "xsec-123",
                          "noteCard": {
                            "displayTitle": "本人一到周日晚上就自动崩溃，这样还有救吗"
                          }
                        }
                      ]
                    }
                    """,
                }
            ],
        }
    )
    publisher = XiaohongshuMcpPublisher(
        server_url="http://localhost:18060/mcp",
        tool_runner=runner,
    )

    result = publisher.find_published_note(
        title="周日晚上，我的灵魂已经提前在工位坐牢",
        body="至少今晚还能再瘫两小时，也算最后的狂欢。",
    )

    assert result is None
