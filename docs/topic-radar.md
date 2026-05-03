---
title: Topic Radar
status: active
owner: ptsm
last_verified: 2026-05-03
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
│   ├── note_teardown.py   # 帖子拆解：钩子类型/正文结构/互动诱因
│   ├── cross_platform.py  # 跨平台话题发现/垂类聚类
│   └── comment_signals.py # (included in note_teardown)
└── output/
    ├── artifacts.py       # TopicScanResult → JSON
    └── report.py          # Markdown 报告
```

## 数据来源

- **小红书**: 本地 xiaohongshu-mcp (HTTP MCP on localhost:18060)
- **微博/抖音**: mcp-trends-hub (stdio MCP via npx)

## 分析能力

1. **帖子拆解**: 标题钩子分类（悬念/反常识/情绪共鸣/利益驱动/身份认同）、正文结构、互动诱因检测
2. **跨平台话题发现**: 对比多平台热榜，发现扩散中的讨论点
3. **垂类聚类**: 自动将话题分配到 12 个候选垂类，附带置信度和讨论密度
4. **评论区信号**: 提问密度、情感极性、真讨论 vs 打卡

## 产物

- `outputs/artifacts/topic-scan-{date}.json` — 结构化 JSON
- `outputs/artifacts/topic-brief-{date}.md` — 可读 Markdown 报告

## 与 PTSM 协作

topic_radar 不依赖 PTSM。PTSM 可以：
- 通过 future skill 读取 artifact JSON 注入 planner context
- 通过 CLI 命令独立运行，人工参考结果
