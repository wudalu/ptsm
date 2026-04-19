# Bailian Image Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Bailian-backed image generation so `run-fengkuang` can generate a publishable XiaoHongShu image when no local image is supplied.

**Architecture:** Add a small `infrastructure.images` layer with a Bailian/DashScope backend, thread it through `run_playbook()`, and persist generation evidence into the artifact. Default to Beijing-region DashScope and a synchronous `qwen-image-2.0-pro` request so the first implementation avoids async task orchestration. Only auto-generate for real publish runs by default; dry-runs require an explicit flag to avoid accidental spend.

**Tech Stack:** Python 3.12, stdlib `urllib`, Pydantic settings, existing artifact/run store flow, pytest

### Task 1: Add request and settings surface

**Files:**
- Modify: `src/ptsm/config/settings.py`
- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write the failing test**

Add a CLI test that calls:

```python
exit_code = main(
    [
        "run-fengkuang",
        "--scene",
        "周六社畜躺平",
        "--account-id",
        "acct-fk-local",
        "--auto-generate-image",
    ]
)
```

Patch `run_fengkuang_playbook()` and assert the request includes:

```python
assert captured_request.auto_generate_images is True
```

Also add a settings test that constructs `Settings.model_validate(...)` with:

```python
{
    "PIC_MODEL_API_KEY": "sk-test",
    "PIC_MODEL_MODEL": "qwen-image-2.0-pro",
}
```

and asserts the parsed settings expose `pic_model_api_key`, `pic_model_model`, and the default `pic_model_base_url`.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py -q`

Expected: FAIL because `--auto-generate-image` and `auto_generate_images` do not exist yet.

**Step 3: Write minimal implementation**

Add to `Settings`:

- `pic_model_api_key`
- `pic_model_base_url` defaulting to `https://dashscope.aliyuncs.com/api/v1`
- `pic_model_model` defaulting to `qwen-image-2.0-pro`
- `pic_model_size` defaulting to `1104*1472`
- `pic_model_negative_prompt`

Add to `PlaybookRequest`:

```python
auto_generate_images: bool | None = None
```

Add CLI flags:

```python
fengkuang.add_argument("--auto-generate-image", dest="auto_generate_image", action="store_true")
fengkuang.add_argument("--no-auto-generate-image", dest="auto_generate_image", action="store_false")
fengkuang.set_defaults(auto_generate_image=None)
```

and pass `auto_generate_images=args.auto_generate_image` into `FengkuangRequest(...)`.

**Step 4: Run test to verify it passes**

Run:

- `uv run pytest tests/unit/interfaces/cli/test_main.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/config/settings.py src/ptsm/application/models.py src/ptsm/interfaces/cli/main.py tests/unit/interfaces/cli/test_main.py
git commit -m "feat: add image generation request surface"
```

### Task 2: Add Bailian image backend

**Files:**
- Create: `src/ptsm/infrastructure/images/contracts.py`
- Create: `src/ptsm/infrastructure/images/factory.py`
- Create: `src/ptsm/infrastructure/images/bailian_backend.py`
- Test: `tests/unit/infrastructure/images/test_bailian_backend.py`

**Step 1: Write the failing test**

Create backend tests for:

```python
def test_bailian_backend_posts_qwen_request_and_downloads_image(...)
def test_build_image_backend_returns_none_without_api_key()
def test_build_image_backend_returns_bailian_backend_when_configured()
```

The main request test should monkeypatch `urlopen` and assert:

- POST URL is `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`
- header contains `Authorization: Bearer sk-test`
- body contains `model`, `input.messages[0].content[0].text`, and `parameters.size`
- the backend downloads the returned image URL into `outputs/generated_images/...png`

Expected result shape:

```python
assert result["provider"] == "bailian"
assert result["model"] == "qwen-image-2.0-pro"
assert Path(result["image_paths"][0]).exists()
assert result["source_url"].startswith("https://")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/infrastructure/images/test_bailian_backend.py -q`

Expected: FAIL because the images package does not exist yet.

**Step 3: Write minimal implementation**

Create a protocol:

```python
class ImageBackend(Protocol):
    provider_name: str
    def generate(...)-> dict[str, object]: ...
```

Implement a Bailian backend that:

- builds a Qwen text-to-image request
- sends it via stdlib `urllib.request`
- parses `output.choices[0].message.content[*].image`
- downloads the first image URL to a requested output path
- returns structured metadata

Implement a factory:

```python
def build_image_backend(settings: Settings) -> ImageBackend | None:
    if not settings.pic_model_api_key:
        return None
    return BailianImageBackend(...)
```

**Step 4: Run test to verify it passes**

Run:

- `uv run pytest tests/unit/infrastructure/images/test_bailian_backend.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/infrastructure/images tests/unit/infrastructure/images/test_bailian_backend.py
git commit -m "feat: add bailian image backend"
```

### Task 3: Integrate image generation into run_playbook

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write the failing test**

Add tests for:

```python
def test_run_fengkuang_playbook_generates_image_for_real_publish_when_missing(...)
def test_run_fengkuang_playbook_prefers_manual_image_paths(...)
def test_run_fengkuang_playbook_skips_generation_for_dry_run_without_flag(...)
```

The real-publish test should patch:

- workflow result with a finished artifact
- a fake image backend returning `generated_image_paths`
- a publisher capturing `image_paths`

Assert:

```python
assert publisher.received_image_paths == [str(tmp_path / "generated.png")]
assert result["image_generation"]["provider"] == "bailian"
assert artifact["image_generation"]["generated_image_paths"] == [str(tmp_path / "generated.png")]
```

The manual-path test should assert the backend is never called.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q`

Expected: FAIL because `run_playbook()` has no image generation branch.

**Step 3: Write minimal implementation**

In `run_playbook()`:

- resolve `effective_publish_mode`
- decide whether generation should happen:
  - manual images always win
  - if `auto_generate_images is True`, generate
  - else if `auto_generate_images is None` and `publish_mode == "mcp-real"`, generate
  - else skip
- call `build_image_backend(settings)` only when needed
- build a prompt from `final_content.title`, `final_content.image_text`, `final_content.body`, and the original `scene`
- save generated images under `outputs/generated_images/<artifact-stem>-cover.png`
- publish using the resolved image path list
- merge structured `image_generation` metadata into the artifact

Use a helper result shape like:

```python
{
    "status": "generated",
    "provider": "bailian",
    "model": "...",
    "prompt": "...",
    "generated_image_paths": [...],
    "source_url": "...",
}
```

**Step 4: Run test to verify it passes**

Run:

- `uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/application/use_cases/run_playbook.py tests/unit/application/use_cases/test_run_playbook.py
git commit -m "feat: generate images before publish when needed"
```

### Task 4: Update docs and artifact observability

**Files:**
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/observability.md`
- Modify: `docs/runtime.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing test**

Add or extend a docs test that requires the core docs to mention:

- `PIC_MODEL_API_KEY`
- `outputs/generated_images`
- `--auto-generate-image`

**Step 2: Run test to verify it fails**

Run:

- `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`

Expected: FAIL because docs do not reference the new image-generation path or command.

**Step 3: Write minimal implementation**

Document:

- required `.env` fields for Bailian image generation
- the default behavior for real publish vs dry-run
- where generated images and evidence are stored
- how generated-image metadata appears in artifacts and diagnostics

**Step 4: Run test to verify it passes**

Run:

- `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/operations/local-runbook.md docs/observability.md docs/runtime.md docs/harness-engineering.md tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py
git commit -m "docs: document bailian image generation"
```

### Task 5: Verify end-to-end behavior

**Files:**
- Test: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/infrastructure/images/test_bailian_backend.py`

**Step 1: Write the failing test**

Extend the dry-run or CLI coverage with one explicit request that sets `--auto-generate-image` and patches the backend so the returned JSON proves image generation is threaded through the command response.

**Step 2: Run test to verify it fails**

Run:

- `uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py -q`

Expected: FAIL because CLI output does not yet surface image generation metadata.

**Step 3: Write minimal implementation**

Make sure the final CLI JSON includes `image_generation` when generation runs, and `generated_image_paths` are visible through the normal receipt path.

**Step 4: Run test to verify it passes**

Run:

- `uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py -q`
- `uv run pytest -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/e2e/test_fengkuang_publish_dry_run.py
git commit -m "test: cover image generation publish flow"
```
