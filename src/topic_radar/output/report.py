from __future__ import annotations

from pathlib import Path

from topic_radar.output.artifacts import TopicScanResult


def generate_report(result: TopicScanResult, output_dir: str = "outputs/artifacts") -> Path:
    lines: list[str] = []

    lines.append(f"# Topic Radar Scan Report — {result.scan_date}")
    lines.append("")
    lines.append(f"**Platforms scanned:** {', '.join(result.platforms)}")
    if result.platform_errors:
        for platform, error in result.platform_errors.items():
            lines.append(f"- {platform}: ⚠️ {error}")
    lines.append("")

    # Cross-platform signals
    if result.cross_platform_signals:
        lines.append("## 跨平台话题信号")
        lines.append("")
        for signal in result.cross_platform_signals:
            lines.append(f"- **{signal.topic}** — 出现在 {', '.join(signal.platforms)} | 速度: {signal.velocity}")
        lines.append("")

    # Discovered verticals
    if result.discovered_verticals:
        lines.append("## 发现的候选垂类")
        lines.append("")
        for v in result.discovered_verticals:
            flag = "🔇 [噪音]" if v.is_noise else ""
            lines.append(f"### {v.name} {flag}")
            lines.append(f"- **置信度:** {v.confidence} | **讨论密度:** {v.discussion_density}")
            lines.append(f"- **关键词:** {', '.join(v.keywords[:6])}")
            lines.append(f"- **热度信号:** {_format_heat(v.heat_signals)}")
            if v.sample_topics:
                lines.append(f"- **样本话题:** {', '.join(v.sample_topics[:3])}")
            if v.suggested_angles:
                lines.append(f"- **建议角度:**")
                for angle in v.suggested_angles[:2]:
                    lines.append(f"  - {angle}")
            if v.comment_themes:
                lines.append(f"- **评论主题预测:** {', '.join(v.comment_themes)}")
            lines.append("")

    # Recommended angles
    if result.recommended_angles:
        lines.append("## 推荐选题角度")
        lines.append("")
        for i, rec in enumerate(result.recommended_angles[:5], 1):
            lines.append(f"{i}. **[{rec['vertical']}]** {rec['angle']}")
            lines.append(f"   - 讨论诱因: {rec['why_discussion_likely']}")
            lines.append(f"   - 置信度: {rec['confidence']}")
            lines.append("")

    # Engagement patterns
    if result.high_engagement_patterns:
        lines.append("## 高互动模式摘要")
        lines.append("")
        patterns = result.high_engagement_patterns[0]
        lines.append(f"- **热门钩子类型:** {', '.join(patterns.get('top_hook_types', []))}")
        lines.append(f"- **热门互动触发:** {', '.join(patterns.get('top_engagement_triggers', []))}")
        lines.append(f"- **拆解样本数:** {patterns.get('teardown_count', 0)}")
        lines.append(f"- **平均钩子置信度:** {patterns.get('avg_hook_confidence', 0)}")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告由 topic-radar v0.1.0 自动生成*")

    content = "\n".join(lines)
    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    filepath = dir_path / f"topic-brief-{result.scan_date}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _format_heat(heat: dict[str, float]) -> str:
    if not heat:
        return "暂无数据"
    return " | ".join(f"{p}: {h}" for p, h in sorted(heat.items()))
