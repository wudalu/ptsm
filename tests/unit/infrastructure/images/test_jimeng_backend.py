from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from ptsm.config.settings import Settings
from ptsm.infrastructure.images.factory import build_image_backend
from ptsm.infrastructure.images.jimeng_backend import JimengImageBackend


class DummyResponse:
    def __init__(self, payload: bytes):
        self._buffer = io.BytesIO(payload)

    def read(self) -> bytes:
        return self._buffer.read()

    def __enter__(self) -> DummyResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_build_image_backend_returns_jimeng_backend_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        JIMENG_API_KEY="ak-test",
        JIMENG_SECRET_KEY="sk-test",
        PIC_MODEL_API_KEY="sk-bailian-test",
    )

    backend = build_image_backend(settings)

    assert isinstance(backend, JimengImageBackend)


def test_build_image_backend_requires_jimeng_secret_key() -> None:
    settings = Settings(_env_file=None, JIMENG_API_KEY="ak-test")

    with pytest.raises(ValueError, match="JIMENG_SECRET_KEY"):
        build_image_backend(settings)


def test_jimeng_backend_submits_signed_task_polls_result_and_downloads_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[object] = []

    def fake_urlopen(request, timeout: int = 0):
        calls.append(request)
        full_url = request.full_url if hasattr(request, "full_url") else request
        parsed = urlparse(full_url)
        action = parse_qs(parsed.query).get("Action", [""])[0]
        if action == "CVSync2AsyncSubmitTask":
            return DummyResponse(
                json.dumps(
                    {
                        "code": 10000,
                        "data": {"task_id": "task-123"},
                        "message": "Success",
                    }
                ).encode("utf-8")
            )
        if action == "CVSync2AsyncGetResult":
            return DummyResponse(
                json.dumps(
                    {
                        "code": 10000,
                        "data": {
                            "status": "done",
                            "image_urls": ["https://example.com/generated.jpg"],
                        },
                        "message": "Success",
                    }
                ).encode("utf-8")
            )
        if full_url == "https://example.com/generated.jpg":
            return DummyResponse(b"fake-jpeg-bytes")
        raise AssertionError(f"unexpected request URL: {full_url}")

    monkeypatch.setattr(
        "ptsm.infrastructure.images.jimeng_backend.urlopen",
        fake_urlopen,
    )

    backend = JimengImageBackend(
        api_key="ak-test",
        secret_key="sk-test",
        base_url="https://visual.volcengineapi.com",
        model="jimeng_t2i_v40",
        width=1536,
        height=2048,
        poll_interval_seconds=0,
        max_poll_attempts=1,
    )

    result = backend.generate(
        prompt="周六社畜躺平封面",
        output_dir=tmp_path,
        output_stem="weekend-flat",
    )

    submit_request = calls[0]
    submit_query = parse_qs(urlparse(submit_request.full_url).query)
    submit_body = json.loads(submit_request.data.decode("utf-8"))
    req_json = json.loads(submit_body["req_json"])

    assert submit_request.full_url.startswith("https://visual.volcengineapi.com?")
    assert submit_query["Action"] == ["CVSync2AsyncSubmitTask"]
    assert submit_query["Version"] == ["2022-08-31"]
    assert submit_request.headers["Authorization"].startswith(
        "HMAC-SHA256 Credential=ak-test/"
    )
    assert _header(submit_request, "X-Content-Sha256")
    assert _header(submit_request, "X-Date")
    assert submit_request.headers["Host"] == "visual.volcengineapi.com"
    assert submit_body["req_key"] == "jimeng_t2i_v40"
    assert submit_body["prompt"] == "周六社畜躺平封面"
    assert submit_body["width"] == 1536
    assert submit_body["height"] == 2048
    assert req_json["return_url"] is True
    assert req_json["logo_info"]["add_logo"] is False

    result_request = calls[1]
    result_query = parse_qs(urlparse(result_request.full_url).query)
    result_body = json.loads(result_request.data.decode("utf-8"))

    assert result_query["Action"] == ["CVSync2AsyncGetResult"]
    assert result_body["task_id"] == "task-123"
    assert result["provider"] == "jimeng"
    assert result["model"] == "jimeng_t2i_v40"
    assert result["source_url"] == "https://example.com/generated.jpg"
    assert Path(result["image_paths"][0]).exists()
    assert Path(result["image_paths"][0]).suffix == ".jpg"


def test_jimeng_backend_uses_png_suffix_for_png_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    png_bytes = b"\x89PNG\r\n\x1a\nfake-png-bytes"

    def fake_urlopen(request, timeout: int = 0):
        full_url = request.full_url if hasattr(request, "full_url") else request
        action = parse_qs(urlparse(full_url).query).get("Action", [""])[0]
        if action == "CVSync2AsyncSubmitTask":
            return DummyResponse(
                json.dumps({"code": 10000, "data": {"task_id": "task-png"}}).encode(
                    "utf-8"
                )
            )
        if action == "CVSync2AsyncGetResult":
            return DummyResponse(
                json.dumps(
                    {
                        "code": 10000,
                        "data": {
                            "status": "done",
                            "image_urls": ["https://example.com/generated.jpg"],
                        },
                    }
                ).encode("utf-8")
            )
        if full_url == "https://example.com/generated.jpg":
            return DummyResponse(png_bytes)
        raise AssertionError(f"unexpected request URL: {full_url}")

    monkeypatch.setattr(
        "ptsm.infrastructure.images.jimeng_backend.urlopen",
        fake_urlopen,
    )

    backend = JimengImageBackend(
        api_key="ak-test",
        secret_key="sk-test",
        base_url="https://visual.volcengineapi.com",
        model="jimeng_t2i_v40",
        width=1536,
        height=2048,
        poll_interval_seconds=0,
        max_poll_attempts=1,
    )

    result = backend.generate(
        prompt="周六社畜躺平封面",
        output_dir=tmp_path,
        output_stem="weekend-flat",
    )

    output_path = Path(result["image_paths"][0])
    assert output_path.suffix == ".png"
    assert output_path.read_bytes() == png_bytes


def test_jimeng_backend_persists_base64_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = 0
    image_bytes = b"fake-jpeg-from-base64"

    def fake_urlopen(request, timeout: int = 0):
        nonlocal calls
        calls += 1
        action = parse_qs(urlparse(request.full_url).query).get("Action", [""])[0]
        if action == "CVSync2AsyncSubmitTask":
            return DummyResponse(
                json.dumps(
                    {
                        "code": 10000,
                        "data": {"task_id": "task-456"},
                    }
                ).encode("utf-8")
            )
        if action == "CVSync2AsyncGetResult":
            return DummyResponse(
                json.dumps(
                    {
                        "code": 10000,
                        "data": {
                            "status": "done",
                            "binary_data_base64": [
                                base64.b64encode(image_bytes).decode("ascii")
                            ],
                        },
                    }
                ).encode("utf-8")
            )
        raise AssertionError(f"unexpected request URL: {request.full_url}")

    monkeypatch.setattr(
        "ptsm.infrastructure.images.jimeng_backend.urlopen",
        fake_urlopen,
    )

    backend = JimengImageBackend(
        api_key="ak-test",
        secret_key="sk-test",
        base_url="https://visual.volcengineapi.com",
        model="jimeng_t2i_v40",
        width=1536,
        height=2048,
        poll_interval_seconds=0,
        max_poll_attempts=1,
    )

    result = backend.generate(
        prompt="周六社畜躺平封面",
        output_dir=tmp_path,
        output_stem="weekend-flat",
    )

    output_path = Path(result["image_paths"][0])
    assert calls == 2
    assert output_path.read_bytes() == image_bytes
    assert result["source_url"] is None


def _header(request: object, name: str) -> str | None:
    headers = getattr(request, "headers")
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None
