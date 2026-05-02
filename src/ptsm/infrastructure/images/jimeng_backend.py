from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class JimengImageBackend:
    """Volcengine Jimeng text-to-image backend."""

    provider_name = "jimeng"
    _service = "cv"
    _region = "cn-north-1"
    _version = "2022-08-31"

    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        base_url: str,
        model: str,
        width: int,
        height: int,
        poll_interval_seconds: float,
        max_poll_attempts: int,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._width = width
        self._height = height
        self._poll_interval_seconds = poll_interval_seconds
        self._max_poll_attempts = max_poll_attempts

    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        output_dir.mkdir(parents=True, exist_ok=True)
        task_id = self._submit_task(prompt=prompt)
        image = self._poll_result(task_id=task_id)
        source_url = image.get("source_url")
        image_bytes = image.get("bytes")
        if not isinstance(image_bytes, bytes):
            raise ValueError("Jimeng image response did not contain image bytes")
        suffix = _suffix_for_image_bytes(image_bytes) or _suffix_for_source(source_url)
        output_path = output_dir / f"{output_stem}{suffix}"
        output_path.write_bytes(image_bytes)
        image_paths = [str(output_path)]
        return {
            "status": "generated",
            "provider": self.provider_name,
            "model": self._model,
            "prompt": prompt,
            "task_id": task_id,
            "image_paths": image_paths,
            "generated_image_paths": image_paths,
            "source_url": source_url,
        }

    def _submit_task(self, *, prompt: str) -> str:
        payload = {
            "req_key": self._model,
            "prompt": prompt,
            "width": self._width,
            "height": self._height,
            "seed": -1,
            "force_single": True,
            "req_json": _request_options_json(),
        }
        response = self._request("CVSync2AsyncSubmitTask", payload)
        data = _response_data(response, context="submit")
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"Jimeng submit response missing task_id: {response}")
        return task_id

    def _poll_result(self, *, task_id: str) -> dict[str, object]:
        payload = {
            "req_key": self._model,
            "task_id": task_id,
            "req_json": _request_options_json(),
        }
        last_response: dict[str, object] | None = None
        for attempt in range(self._max_poll_attempts):
            if attempt > 0 and self._poll_interval_seconds > 0:
                time.sleep(self._poll_interval_seconds)
            response = self._request("CVSync2AsyncGetResult", payload)
            last_response = response
            data = _response_data(response, context="result")
            status = data.get("status")
            if status in {"failed", "canceled", "cancelled"}:
                raise ValueError(f"Jimeng task failed: {response}")
            image = self._image_from_result_data(data)
            if image is not None:
                return image
            if status in {"done", "success", "succeeded"}:
                raise ValueError(f"Jimeng result missing image data: {response}")
        raise TimeoutError(f"Jimeng polling timeout after {self._max_poll_attempts} attempts: {last_response}")

    def _request(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        query = {"Action": action, "Version": self._version}
        request = Request(
            _url_with_query(self._base_url, query),
            data=body.encode("utf-8"),
            headers=self._signed_headers(query=query, body=body),
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Jimeng response is not a JSON object: {raw}")
        return raw

    def _signed_headers(
        self,
        *,
        query: dict[str, str],
        body: str,
    ) -> dict[str, str]:
        parsed = urlparse(self._base_url)
        host = parsed.netloc
        now = datetime.now(timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = now.strftime("%Y%m%d")
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_query = urlencode(sorted(query.items()))
        canonical_headers = (
            "content-type:application/json\n"
            f"host:{host}\n"
            f"x-content-sha256:{body_hash}\n"
            f"x-date:{x_date}\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = "\n".join(
            [
                "POST",
                "/",
                canonical_query,
                canonical_headers,
                signed_headers,
                body_hash,
            ]
        )
        credential_scope = f"{short_date}/{self._region}/{self._service}/request"
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                x_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _signing_key(
                secret_key=self._secret_key,
                short_date=short_date,
                region=self._region,
                service=self._service,
            ),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            f"HMAC-SHA256 Credential={self._api_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": host,
            "X-Content-Sha256": body_hash,
            "X-Date": x_date,
        }

    @staticmethod
    def _image_from_result_data(data: dict[str, object]) -> dict[str, object] | None:
        b64_list = data.get("binary_data_base64")
        if isinstance(b64_list, list) and b64_list:
            first = b64_list[0]
            if isinstance(first, str) and first:
                return {
                    "bytes": base64.b64decode(first),
                    "source_url": None,
                }
        urls = data.get("image_urls")
        if isinstance(urls, list) and urls:
            first_url = urls[0]
            if isinstance(first_url, str) and first_url:
                with urlopen(first_url, timeout=60) as response:
                    return {
                        "bytes": response.read(),
                        "source_url": first_url,
                    }
        return None


def _response_data(response: dict[str, object], *, context: str) -> dict[str, object]:
    code = response.get("code")
    status = response.get("status")
    if code not in {None, 10000} and status not in {None, 10000}:
        message = response.get("message") or response.get("msg") or response
        raise ValueError(f"Jimeng {context} request failed: {message}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"Jimeng {context} response missing data: {response}")
    return data


def _request_options_json() -> str:
    return json.dumps(
        {
            "return_url": True,
            "logo_info": {"add_logo": False},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _signing_key(
    *,
    secret_key: str,
    short_date: str,
    region: str,
    service: str,
) -> bytes:
    k_date = hmac.new(secret_key.encode("utf-8"), short_date.encode("utf-8"), hashlib.sha256).digest()
    k_region = hmac.new(k_date, region.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_region, service.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(k_service, b"request", hashlib.sha256).digest()


def _url_with_query(base_url: str, query: dict[str, str]) -> str:
    return f"{base_url}?{urlencode(sorted(query.items()))}"


def _suffix_for_source(source_url: object) -> str:
    if not isinstance(source_url, str):
        return ".jpg"
    suffix = Path(urlparse(source_url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"


def _suffix_for_image_bytes(image_bytes: bytes) -> str | None:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    return None
