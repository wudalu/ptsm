# XHS MCP Spike Notes

Date: 2026-03-15

## Goal

Validate whether `xiaohongshu-mcp` can serve as the XiaoHongShu publishing backend for PTSM, and whether `langchain-mcp-adapters` can call it from Python.

## Local Environment

- Workspace: `/Users/wudalu/llm-app/ptsm`
- OS: `macOS 15.7.4`
- Arch: `x86_64`
- `go`: not installed
- `docker`: not installed
- local Chrome binary: not found

Conclusion:

- Source build path is unavailable on this machine.
- Docker path is unavailable on this machine.
- Prebuilt binary path is the shortest workable route.

## Upstream Version Used

- Repo: `https://github.com/xpzouying/xiaohongshu-mcp`
- Latest release observed during spike: `v2026.03.09.0605-0e16f4b`
- Binary used: `xiaohongshu-mcp-darwin-amd64.tar.gz`

## What Was Verified

### 1. Server startup works locally

Binary was downloaded and started successfully.

Observed startup log:

- `Registered 13 MCP tools`
- `MCP Server initialized with official SDK`
- `启动 HTTP 服务器: :18060`

### 2. HTTP MCP endpoint is reachable

Initialization against `http://localhost:18060/mcp` returned a valid MCP initialize response.

Observed server info:

- `name: xiaohongshu-mcp`
- `version: 2.0.0`
- `protocolVersion: 2025-03-26`

### 3. LangChain MCP adapter can connect

Added `langchain-mcp-adapters` and created a small probe module:

- `src/ptsm/spikes/xhs_mcp_probe.py`

Confirmed `MultiServerMCPClient` can connect over HTTP transport and list tools.

Observed tool list:

- `check_login_status`
- `delete_cookies`
- `favorite_feed`
- `get_feed_detail`
- `get_login_qrcode`
- `like_feed`
- `list_feeds`
- `post_comment_to_feed`
- `publish_content`
- `publish_with_video`
- `reply_comment_in_feed`
- `search_feeds`
- `user_profile`

### 4. `check_login_status` works through `langchain-mcp-adapters`

The probe successfully invoked `check_login_status`.

Observed result:

- `❌ 未登录`
- `请使用 get_login_qrcode 工具获取二维码进行登录`

This proves the Python -> LangChain MCP adapter -> xiaohongshu-mcp tool chain is valid.

## Intermediate Root Cause

The first QR login attempt did not establish a session, and this was traced to two concrete issues:

- the QR code that was scanned had already expired
- `xiaohongshu-mcp` prefers `/tmp/cookies.json` when that file exists, so stale cookies can keep getting reused unless the login flow overwrites them

Observed evidence:

- QR code timeout returned by upstream: `4m0s`
- expired QR file generation time we observed locally: `2026-03-15 09:52:43`
- fresh QR file generation time that later worked: `2026-03-15 10:11:04`
- service working directory: `/Users/wudalu/llm-app/ptsm`
- cookie precedence from upstream implementation: `/tmp/cookies.json` first, then `COOKIES_PATH`, then local `cookies.json`

Interpretation:

- the earlier failure was not an MCP integration problem
- it was a login bootstrap/session artifact problem

## What Was Verified But Initially Blocked

### 5. `search_feeds` reaches the MCP tool, but fails without login

The service logs confirm the tool was invoked:

- `MCP: 搜索Feeds`
- `MCP: 搜索Feeds - 关键词: 打工人`

Observed server outcome:

- HTTP `500` on `/mcp`
- adapter surfaced an `ExceptionGroup`

Interpretation:

- transport is working
- tool routing is working
- current blocker is login/session state

### 6. `publish_content` reaches the MCP tool, but fails without login

The service logs confirm the tool was invoked with our payload:

- title: `PTSM Spike Test`
- images: `1`
- tags: `2`

Observed server outcome:

- HTTP `500` on `/mcp`
- server-side warning: `Execution context was destroyed`
- adapter surfaced an `ExceptionGroup`

Interpretation:

- publish request shape is accepted
- transport is working
- current blocker is authenticated browser/session state

## End-to-End Validation After Login

After scanning a fresh QR code and confirming login inside the XiaoHongShu app, the same server and probe path succeeded end-to-end.

### 7. Authenticated `check_login_status` succeeds

Observed result:

- `✅ 已登录`
- `用户名: xiaohongshu-mcp`

### 8. Authenticated `search_feeds` succeeds

Executed through:

- `uv run python -m ptsm.spikes.xhs_mcp_probe --server-url http://localhost:18060/mcp --keyword 打工人`

Observed result:

- `search_feeds` returned `count: 22`
- results included normal notes such as:
  - `又来坐牢了`
  - `当代打工人发疯实录`
  - `文案｜“独属牛马打工人💻的日常发疯文案”`

Interpretation:

- authenticated MCP search works through `langchain-mcp-adapters`

### 9. Authenticated `publish_content` succeeds

Executed through:

- `uv run python -m ptsm.spikes.xhs_mcp_probe --server-url http://localhost:18060/mcp --publish-json ...`

Publish payload characteristics:

- title: `PTSM发布验证`
- visibility: `仅自己可见`
- images: `1`
- tags: `PTSM`, `自动化验证`

Observed server-side publish flow:

- image upload submitted
- image upload completed
- title/content filled
- tag suggestions clicked successfully
- visibility set to `仅自己可见`

Observed final adapter result:

- `内容发布成功`
- `Status: 发布完成`

Interpretation:

- Python -> LangChain MCP adapter -> xiaohongshu-mcp -> real XiaoHongShu publish flow is now validated
- a minimal real publish can be executed safely by forcing `仅自己可见`

## Cookie Reuse Attempt

Tried reusing an existing cookie file from:

- `/Users/wudalu/llm-app/pub-to-social-media/data/cookies/xiaohongshu_cookies.json`

Result:

- the file format is compatible
- after placing it where `xiaohongshu-mcp` can read it, login status still reported `未登录`

Interpretation:

- old cookies are likely expired

## Login QR Code

Generated a fresh login QR code image from:

- `GET /api/v1/login/qrcode`

Saved local file:

- `/tmp/xhs-login-qrcode.png`

Observed metadata:

- `is_logged_in: false`
- `timeout: 4m0s`

## Engineering Conclusion

`xiaohongshu-mcp` is viable as the backend for PTSM.

What is already proven:

- local service startup
- HTTP MCP connectivity
- `langchain-mcp-adapters` compatibility
- tool discovery
- successful tool invocation for login status
- request routing into `search_feeds` and `publish_content`

What is now proven end-to-end:

- authenticated `check_login_status`
- authenticated `search_feeds`
- authenticated `publish_content`

Current remaining gap is not feasibility. It is productization:

- login bootstrap UX
- session lifecycle management
- structured publisher adapter integration inside PTSM
- failure normalization and operational safeguards

## Recommended Integration Path

1. Keep `xiaohongshu-mcp` as an external backend, not embedded code.
2. Use HTTP transport, not stdio, because upstream already exposes stable HTTP MCP.
3. In PTSM, add a thin MCP publisher adapter that:
   - preflights `check_login_status`
   - optionally requests `get_login_qrcode`
   - maps `final_content -> publish_content`
   - normalizes MCP HTTP failures into structured application errors
4. Use `仅自己可见` as the default verification mode for any real publish smoke test.
5. Do not enable public real publish in the main workflow until login/session bootstrap is handled.

## Next Action

The spike is complete enough to move into product integration.

Recommended next implementation step in PTSM:

1. Add an MCP-backed XiaoHongShu publisher adapter.
2. Add login/session preflight around `check_login_status` and `get_login_qrcode`.
3. Keep the first integrated real publish path restricted to `仅自己可见`.
4. Persist publish inputs and MCP outputs into local artifacts for traceability.
