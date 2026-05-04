"""LLM-driven topic analysis. Default path with rule-based fallback."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from topic_radar.analysis.methodology import META_PROMPT
from topic_radar.analysis.schemas import LLMScanOutput
from topic_radar.platforms.weibo import TrendingItem


_PROMPT_SYSTEM = """你是一个内容策略分析师。你的任务是基于全网热搜数据，发现有讨论价值的话题，并给出具体的发帖选题建议。

分析原则：
- 不要只复述热搜标题。你需要判断每个话题的"讨论价值"——是否容易引发评论区互动。
- 高讨论价值的话题通常：涉及身份认同/价值观冲突、有争议空间、低门槛可参与、能引发经验交换。
- 低讨论价值的话题（noise）：纯资讯通报、明星八卦（除非有深层社会议题）、一次性的突发新闻。
- 垂类命名要具体，不要用"其他话题"这种兜底名称。从数据里读出来，不要套固定模板。
- 选题角度要是可执行的帖子标题方向，不要用{占位符}。用真实的中文表达。

输出格式：纯 JSON，不要加 markdown 代码块标记。

""" + META_PROMPT


def _build_user_prompt(
    trending_items: dict[str, list[TrendingItem]],
    scan_date: str,
) -> str:
    lines = [
        f"扫描日期：{scan_date}",
        "",
    ]
    for platform, items in trending_items.items():
        lines.append(f"## {platform} 热搜 ({len(items)} 条)")
        lines.append("")
        for item in items[:30]:
            lines.append(f"- [{item.rank}] {item.title} (热度: {item.hot_score})")
        lines.append("")

    lines.append("---")
    lines.append("请分析以上数据，返回 JSON，包含以下字段：")
    lines.append("""
{
  "scan_summary": "一句话总结本次扫描的核心发现",
  "cross_platform_signals": [
    {
      "topic": "跨平台话题名",
      "platforms": ["weibo", "douyin"],
      "velocity": "accelerating | steady | fading",
      "discussion_value": "为什么容易引发讨论，1-2句中文",
      "mechanism": "触发的认知劫持机制（如：悬念型/反常识型/身份共鸣型）",
      "archetype": "激活的荣格原型（如：英雄/叛逆者/智者）"
    }
  ],
  "discovered_verticals": [
    {
      "name": "垂类名称（2-8字，从数据里读出来，具体不要兜底）",
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "confidence": 0.85,
      "discussion_density": "high | medium | low",
      "sample_topics": ["样本话题1", "样本话题2"],
      "suggested_angles": ["具体选题角度1（不要占位符）", "具体选题角度2"],
      "comment_themes": ["预测评论主题1", "预测评论主题2"]
    }
  ],
  "recommended_angles": [
    {
      "vertical": "所属垂类",
      "angle": "具体选题角度",
      "why": "为什么这个角度会引发讨论",
      "hook_mechanism": "该选题利用的认知机制（如：反常识型/身份共鸣型）"
    }
  ],
  "noise_topics": ["只热但没讨论价值的话题"]
}""")
    lines.append("")
    lines.append("重要：只返回 JSON，不要任何解释文字，不要 markdown 代码块。")
    return "\n".join(lines)


class LLMAnalyzer:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.getenv("TOPIC_RADAR_LLM_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or ""
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
        self._config_api_key = api_key  # track if explicitly provided
        self._client: OpenAI | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def analyze(
        self,
        trending_items: dict[str, list[TrendingItem]],
        scan_date: str,
    ) -> tuple[LLMScanOutput | None, str]:
        """Run LLM analysis. Returns (result, method) where method is 'llm' or 'rules'.

        If LLM is unavailable or fails, returns (None, 'rules').
        Caller should then use rule-based fallback.
        """
        if not self.available:
            return None, "rules"

        prompt = _build_user_prompt(trending_items, scan_date)
        try:
            raw = self._call(prompt)
            data = _extract_json(raw)
            result = LLMScanOutput(**data)
            return result, "llm"
        except Exception:
            return None, "rules"

    def _call(self, prompt: str) -> str:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _PROMPT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        return content or ""


def _extract_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        end = next((i for i in range(1, len(lines)) if lines[i].startswith("```")), len(lines))
        raw = "\n".join(lines[1:end])
    if raw.startswith("```json"):
        raw = raw[7:]
    data: Any = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data
