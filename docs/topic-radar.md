---
title: Topic Radar
status: active
owner: ptsm
last_verified: 2026-05-10
source_of_truth: true
related_paths:
  - src/topic_radar
  - docs/index.md
  - docs/xhs-topics/index.md
  - docs/operations/topic-radar-runbook.md
  - docs/plans/2026-05-03-topic-radar-research-agent.md
---

# Topic Radar

独立的多平台选题研究引擎，发现各平台容易引发讨论的话题，产出结构化的选题建议。

与 PTSM 解耦，不依赖 PTSM 内部模块。PTSM 可通过 skill 或 planner 消费其产出的 artifact。

## 使用方式

```bash
# 多平台扫描
topic-radar scan                          # 三平台扫描
topic-radar scan --platforms xhs,weibo    # 限定平台
topic-radar scan --mcp-check              # 仅检查 MCP 健康

# 单帖拆解
topic-radar teardown <feed_id> --xsec-token <token>
```

## 架构

```
src/topic_radar/
├── cli.py                 # CLI: scan, teardown
├── config.py              # pydantic-settings 配置
├── mcp_client.py          # MCP client (HTTP + stdio)
├── platforms/
│   ├── xiaohongshu.py     # search_feeds, get_feed_detail
│   └── weibo.py           # Weibo/Douyin via mcp-trends-hub
├── analysis/
│   ├── schemas.py         # Pydantic schemas for LLM output
│   ├── llm_analyzer.py    # LLM-driven analysis (primary)
│   ├── methodology.py     # 4D methodology framework for prompt injection
│   ├── note_teardown.py   # 帖子拆解 (fallback)
│   ├── cross_platform.py  # 跨平台话题/垂类聚类 (fallback)
│   └── comment_signals.py # (included in note_teardown)
└── output/
    ├── artifacts.py       # TopicScanResult → JSON
    └── report.py          # Markdown 报告
```

### 分析路径

**默认路径：LLM → fallback rules**
1. 数据归一化（去重、排序、格式统一）
2. LLM 分析：将所有原始 trending 数据发送给 DeepSeek，system prompt 嵌入了 content-production-mcp 四维方法论框架（认知劫持机制 + 荣格原型 + 平台讨论模式 + 情绪-传播联动），LLM 据此自主发现垂类、评估讨论价值、生成选题角度
3. 如果 LLM 不可用（无 API key、网络错误、响应无效），自动回退到规则引擎

artifact 中 `analysis_method` 字段标记实际使用的路径（`"llm"` 或 `"rules"`）。

## 数据来源

- **小红书**: 本地 xiaohongshu-mcp (HTTP MCP on localhost:18060)
- **微博/抖音/知乎/B站/今日头条/豆瓣/少数派**: mcp-trends-hub (stdio MCP via npx)，共覆盖 7 个中文内容平台

## 分析能力

1. **帖子拆解**: 标题钩子分类（悬念/反常识/情绪共鸣/利益驱动/身份认同）、正文结构、互动诱因检测
2. **跨平台话题发现**: 对比多平台热榜，发现扩散中的讨论点
3. **垂类聚类**: 自动将话题分配到 12 个候选垂类，附带置信度和讨论密度
4. **评论区信号**: 提问密度、情感极性、真讨论 vs 打卡

## 产物

- `outputs/artifacts/topic-scan-{date}.json` — 结构化 JSON
- `outputs/artifacts/topic-brief-{date}.md` — 可读 Markdown 报告

## Programmatic API

`topic_radar.run_scan()` 提供异步 programmatic 接口，返回 `TopicScanResult`：

```python
from topic_radar import run_scan

result = await run_scan(platforms="xiaohongshu", keywords="打工人,治愈")
# result.discovered_verticals  — 发现的垂类
# result.recommended_angles    — 推荐角度
# result.scan_summary          — 扫描摘要
```

## 与 PTSM 协作

PTSM 通过 `--fresh-topic-research` 将 topic-radar 集成到发帖流程：

```bash
# 选题驱动发帖（topic-radar 扫描 → 交互选题 → 自动生成内容）
ptsm run-fengkuang --fresh-topic-research --account-id acct-fk-local
ptsm run-playbook --fresh-topic-research --account-id acct-psychology-local --playbook-id modern_psychology_post

# 结合图片生成和发布
ptsm run-fengkuang --fresh-topic-research --account-id acct-fk-local --auto-generate-image --publish-mode mcp-real --publish-visibility "仅自己可见"
```

流程：
1. topic-radar 扫描当前平台热点
2. 终端交互：展示发现的垂类和推荐角度，用户选择
3. 基于用户选择的垂类+角度构建 enriched scene
4. 继续正常的 playbook 发帖流程

topic_radar 不依赖 PTSM。PTSM 还可以：
- 通过 CLI 命令独立运行，人工参考结果
- 通过 programmatic API 在其他场景中消费分析结果
