from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


class BailianImageBackend:
    """DashScope/Bailian-backed text-to-image backend."""

    provider_name = "bailian"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        size: str,
        negative_prompt: str,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._size = size
        self._negative_prompt = negative_prompt

    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        output_dir.mkdir(parents=True, exist_ok=True)
        image_url = self._submit_qwen_request(prompt=prompt)
        output_path = output_dir / f"{output_stem}.png"
        self._download_image(image_url=image_url, output_path=output_path)
        image_paths = [str(output_path)]
        return {
            "status": "generated",
            "provider": self.provider_name,
            "model": self._model,
            "prompt": prompt,
            "image_paths": image_paths,
            "generated_image_paths": image_paths,
            "source_url": image_url,
        }

    def _submit_qwen_request(self, *, prompt: str) -> str:
        payload = {
            "model": self._model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
            "parameters": {
                "size": self._size,
                "negative_prompt": self._negative_prompt,
                "watermark": False,
                "prompt_extend": True,
            },
        }
        request = Request(
            f"{self._base_url}/services/aigc/multimodal-generation/generation",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
        return self._extract_image_url(raw)

    def _download_image(self, *, image_url: str, output_path: Path) -> None:
        with urlopen(image_url, timeout=60) as response:
            output_path.write_bytes(response.read())

    @staticmethod
    def _extract_image_url(payload: dict[str, object]) -> str:
        output = payload.get("output")
        if not isinstance(output, dict):
            raise ValueError("Bailian image response missing output")
        choices = output.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Bailian image response missing output.choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("Bailian image response contains invalid choice payload")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("Bailian image response missing output.choices[0].message")
        content = message.get("content")
        if not isinstance(content, list):
            raise ValueError("Bailian image response missing message.content")
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("image"), str):
                return item["image"]
        raise ValueError("Bailian image response missing generated image URL")

