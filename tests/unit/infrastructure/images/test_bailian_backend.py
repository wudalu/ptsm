from __future__ import annotations

import io
import json
from pathlib import Path

from ptsm.config.settings import Settings
from ptsm.infrastructure.images.bailian_backend import BailianImageBackend
from ptsm.infrastructure.images.factory import build_image_backend


class DummyResponse:
    def __init__(self, payload: bytes):
        self._buffer = io.BytesIO(payload)

    def read(self) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> DummyResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_build_image_backend_returns_none_without_api_key() -> None:
    settings = Settings(_env_file=None, PIC_MODEL_API_KEY=None)

    assert build_image_backend(settings) is None


def test_build_image_backend_returns_bailian_backend_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        PIC_MODEL_API_KEY="sk-image-test",
        PIC_MODEL_MODEL="qwen-image-2.0-pro",
    )

    backend = build_image_backend(settings)

    assert isinstance(backend, BailianImageBackend)


def test_bailian_backend_posts_qwen_request_and_downloads_image(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[object] = []

    def fake_urlopen(request, timeout: int = 0):
        calls.append(request)
        full_url = request.full_url if hasattr(request, "full_url") else request
        if full_url.endswith("/generation"):
            payload = {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {
                                        "image": "https://example.com/generated.png",
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
            return DummyResponse(json.dumps(payload).encode("utf-8"))
        if full_url == "https://example.com/generated.png":
            return DummyResponse(b"fake-png-bytes")
        raise AssertionError(f"unexpected request URL: {full_url}")

    monkeypatch.setattr(
        "ptsm.infrastructure.images.bailian_backend.urlopen",
        fake_urlopen,
    )

    backend = BailianImageBackend(
        api_key="sk-image-test",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        model="qwen-image-2.0-pro",
        size="1104*1472",
        negative_prompt="不要模糊",
    )

    result = backend.generate(
        prompt="周六社畜躺平封面",
        output_dir=tmp_path,
        output_stem="weekend-flat",
    )

    request = calls[0]
    body = json.loads(request.data.decode("utf-8"))

    assert request.full_url == (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )
    assert request.headers["Authorization"] == "Bearer sk-image-test"
    assert body["model"] == "qwen-image-2.0-pro"
    assert body["input"]["messages"][0]["content"][0]["text"] == "周六社畜躺平封面"
    assert body["parameters"]["size"] == "1104*1472"
    assert result["provider"] == "bailian"
    assert result["model"] == "qwen-image-2.0-pro"
    assert result["source_url"] == "https://example.com/generated.png"
    assert Path(result["image_paths"][0]).exists()
