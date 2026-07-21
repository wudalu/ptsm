"""LLM-driven topic analysis. Default path with rule-based fallback."""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence

from openai import OpenAI

from topic_radar.analysis.methodology import META_PROMPT
from topic_radar.analysis.evidence import (
    EvidenceRecord,
    TopicCluster,
    contains_unexpanded_template,
    contains_raw_source_provenance,
    find_clusters_for_titles,
    normalize_text,
    normalized_source_keys,
    source_provenance_keys,
)
from topic_radar.analysis.schemas import LLMAngle, LLMScanOutput, LLMTopicSignal, LLMVertical
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

_MAX_PROMPT_ITEMS_PER_PLATFORM = 12
_MAX_PROMPT_EVIDENCE_ROWS = 48
_MAX_PROMPT_CLUSTERS = 24


def _build_user_prompt(
    trending_items: dict[str, list[TrendingItem]],
    scan_date: str,
    *,
    evidence: Sequence[EvidenceRecord] | None = None,
    topic_clusters: Sequence[TopicCluster] | None = None,
) -> str:
    lines = [
        f"扫描日期：{scan_date}",
        "",
    ]
    for platform, items in trending_items.items():
        lines.append(f"## {platform} 热搜 ({len(items)} 条)")
        lines.append("")
        for item in items[:_MAX_PROMPT_ITEMS_PER_PLATFORM]:
            lines.append(f"- [{item.rank}] {item.title} (热度: {item.hot_score})")
        if len(items) > _MAX_PROMPT_ITEMS_PER_PLATFORM:
            lines.append(
                f"- … 其余 {len(items) - _MAX_PROMPT_ITEMS_PER_PLATFORM} 条已省略"
            )
        lines.append("")

    prompt_evidence = _select_prompt_evidence(evidence or [])
    if prompt_evidence:
        lines.append("## 可引用的证据（只能引用以下 evidence_id）")
        for record in prompt_evidence:
            lines.append(
                f"- {record.evidence_id} | {record.platform} | {record.title}"
            )
        if len(evidence or []) > len(prompt_evidence):
            lines.append(
                f"- … 其余 {len(evidence or []) - len(prompt_evidence)} 条证据未放入本次 LLM 上下文"
            )
        lines.append("")
    prompt_clusters = _select_prompt_clusters(topic_clusters or [], prompt_evidence)
    if prompt_clusters:
        lines.append("## 可引用的事件簇（只能引用以下 cluster_id）")
        for cluster, evidence_ids, platforms in prompt_clusters:
            platform_names = ", ".join(platforms)
            evidence_id_text = ", ".join(evidence_ids)
            lines.append(
                f"- {cluster.cluster_id} | {cluster.representative_title} | "
                f"平台: {platform_names} | 证据: {evidence_id_text}"
            )
        if len(topic_clusters or []) > len(prompt_clusters):
            lines.append(
                f"- … 其余 {len(topic_clusters or []) - len(prompt_clusters)} 个事件簇未放入本次 LLM 上下文"
            )
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
      "velocity": "unknown（单次扫描没有时序证据）",
      "discussion_value": "为什么容易引发讨论，1-2句中文",
      "mechanism": "触发的认知劫持机制（如：悬念型/反常识型/身份共鸣型）",
      "archetype": "激活的荣格原型（如：英雄/叛逆者/智者）",
      "cluster_id": "可选，必须是上方提供的 cluster_id",
      "evidence_ids": ["可选，必须是上方提供的 evidence_id"]
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
      "comment_themes": ["预测评论主题1", "预测评论主题2"],
      "cluster_ids": ["可选，必须是上方提供的 cluster_id"],
      "evidence_ids": ["可选，必须是上方提供的 evidence_id"]
    }
  ],
  "recommended_angles": [
    {
      "vertical": "所属垂类",
      "angle": "具体选题角度",
      "why": "为什么这个角度会引发讨论",
      "hook_mechanism": "该选题利用的认知机制（如：反常识型/身份共鸣型）",
      "cluster_id": "优先填写一个上方提供的 cluster_id",
      "evidence_ids": ["可选，必须是上方提供的 evidence_id"]
    }
  ],
  "noise_topics": ["只热但没讨论价值的话题"]
}""")
    lines.append("")
    lines.append(
        "重要：只返回 JSON，不要任何解释文字，不要 markdown 代码块。"
        "如果一个选题没有可验证证据，不要把它放进 recommended_angles；"
        "不得编造平台、cluster_id 或 evidence_id。"
        "不得把任何 source evidence 的标题、作者、URL、feed ID 或 token 原样或嵌入"
        "写进 vertical、angle 或 why；要写可执行的二次创作角度。"
    )
    return "\n".join(lines)


def _select_prompt_evidence(evidence: Sequence[EvidenceRecord]) -> list[EvidenceRecord]:
    """Round-robin bounded evidence so platform order cannot consume the prompt."""
    by_platform: dict[str, list[EvidenceRecord]] = {}
    for record in evidence:
        by_platform.setdefault(record.platform, []).append(record)
    for records in by_platform.values():
        records.sort(
            key=lambda record: (
                -record.normalized_heat,
                -record.hot_score,
            )
        )
    return _round_robin_prompt_rows(
        by_platform,
        max_rows=_MAX_PROMPT_EVIDENCE_ROWS,
    )


def _select_prompt_clusters(
    topic_clusters: Sequence[TopicCluster],
    prompt_evidence: Sequence[EvidenceRecord],
) -> list[tuple[TopicCluster, list[str], list[str]]]:
    """Keep clusters coherent with prompt evidence and cover each visible platform."""
    platform_by_evidence_id = {
        record.evidence_id: record.platform for record in prompt_evidence
    }
    entries: list[tuple[TopicCluster, list[str], list[str]]] = []
    for cluster in topic_clusters:
        evidence_ids = [
            evidence_id
            for evidence_id in cluster.evidence_ids
            if evidence_id in platform_by_evidence_id
        ]
        if not evidence_ids:
            continue
        platforms = sorted({platform_by_evidence_id[evidence_id] for evidence_id in evidence_ids})
        entries.append((cluster, evidence_ids, platforms))
    entries.sort(key=lambda entry: (-entry[0].score, entry[0].cluster_id))

    selected: list[tuple[TopicCluster, list[str], list[str]]] = []
    selected_cluster_ids: set[str] = set()
    covered_platforms: set[str] = set()
    for entry in entries:
        if len(selected) >= _MAX_PROMPT_CLUSTERS:
            break
        cluster, _evidence_ids, platforms = entry
        if set(platforms).issubset(covered_platforms):
            continue
        selected.append(entry)
        selected_cluster_ids.add(cluster.cluster_id)
        covered_platforms.update(platforms)

    for entry in entries:
        if len(selected) >= _MAX_PROMPT_CLUSTERS:
            break
        cluster = entry[0]
        if cluster.cluster_id in selected_cluster_ids:
            continue
        selected.append(entry)
        selected_cluster_ids.add(cluster.cluster_id)
    return selected


def _round_robin_prompt_rows(
    by_platform: Mapping[str, Sequence[EvidenceRecord]],
    *,
    max_rows: int,
) -> list[EvidenceRecord]:
    """Take the strongest remaining row from every platform in stable rounds."""
    selected: list[EvidenceRecord] = []
    indices = {platform: 0 for platform in by_platform}
    while len(selected) < max_rows:
        added = False
        for platform in sorted(by_platform):
            index = indices[platform]
            records = by_platform[platform]
            if index >= len(records):
                continue
            selected.append(records[index])
            indices[platform] = index + 1
            added = True
            if len(selected) >= max_rows:
                break
        if not added:
            break
    return selected


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
        self.last_error = ""

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def analyze(
        self,
        trending_items: dict[str, list[TrendingItem]],
        scan_date: str,
        *,
        evidence: Sequence[EvidenceRecord] | None = None,
        topic_clusters: Sequence[TopicCluster] | None = None,
    ) -> tuple[LLMScanOutput | None, str]:
        """Run LLM analysis. Returns (result, method) where method is 'llm' or 'rules'.

        If LLM is unavailable or fails, returns (None, 'rules').
        Caller should then use rule-based fallback.
        """
        if not self.available:
            return None, "rules"

        self.last_error = ""
        prompt = _build_user_prompt(
            trending_items,
            scan_date,
            evidence=evidence,
            topic_clusters=topic_clusters,
        )
        try:
            raw = self._call(prompt)
            data = _extract_json(raw)
            result = LLMScanOutput(**data)
            return result, "llm"
        except Exception as exc:
            self.last_error = (
                f"LLM analysis failed ({type(exc).__name__}); rules fallback used"
            )
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


def validate_llm_output_evidence(
    output: LLMScanOutput,
    evidence: Sequence[EvidenceRecord],
    topic_clusters: Sequence[TopicCluster],
    *,
    raw_provenance: Sequence[Mapping[str, object]] | None = None,
) -> LLMScanOutput | None:
    """Keep only LLM conclusions that can be traced to canonical evidence.

    The model may suggest a useful interpretation, but it cannot create a new
    source or claim a platform that the scan did not collect.  Older model
    payloads without ids remain compatible only when a vertical's sample title
    matches exactly one supplied event cluster.
    """
    clusters_by_id = {cluster.cluster_id: cluster for cluster in topic_clusters}
    evidence_by_id = {record.evidence_id: record for record in evidence}
    evidence_title_keys = normalized_source_keys(record.title for record in evidence)
    provenance_keys = source_provenance_keys(raw_provenance or [])
    validated_verticals = [
        validated
        for vertical in output.discovered_verticals
        if (
            validated := _validate_vertical_provenance(
                vertical,
                evidence=evidence,
                topic_clusters=topic_clusters,
                clusters_by_id=clusters_by_id,
                evidence_by_id=evidence_by_id,
            )
        ) is not None
    ]
    verticals_by_name = {vertical.name: vertical for vertical in validated_verticals}
    original_vertical_names = {vertical.name for vertical in output.discovered_verticals}

    validated_angles: list[LLMAngle] = []
    for angle in output.recommended_angles:
        # Reject before the method-choice branch. Leaving a template angle in
        # the LLM output would prevent rules fallback, then the selector would
        # discard it too late and expose an empty recommendation list.
        if any(
            contains_unexpanded_template(value)
            for value in (angle.vertical, angle.angle, angle.why)
        ):
            continue
        if contains_raw_source_provenance(
            (angle.vertical, angle.angle, angle.why),
            source_title_keys=evidence_title_keys,
            provenance_keys=provenance_keys,
        ):
            continue
        if angle.vertical in original_vertical_names and angle.vertical not in verticals_by_name:
            continue
        support = _resolve_support(
            cluster_id=angle.cluster_id,
            evidence_ids=angle.evidence_ids,
            fallback_titles=_vertical_sample_topics(angle.vertical, verticals_by_name),
            clusters_by_id=clusters_by_id,
            evidence_by_id=evidence_by_id,
            evidence=evidence,
            topic_clusters=topic_clusters,
        )
        if support is None:
            continue
        cluster, evidence_ids = support
        validated_angles.append(
            angle.model_copy(
                update={
                    "cluster_id": cluster.cluster_id,
                    "evidence_ids": evidence_ids,
                }
            )
        )

    if not validated_angles and not validated_verticals:
        return None

    validated_signals: list[LLMTopicSignal] = []
    for signal in output.cross_platform_signals:
        support = _resolve_support(
            cluster_id=signal.cluster_id,
            evidence_ids=signal.evidence_ids,
            fallback_titles=[signal.topic],
            clusters_by_id=clusters_by_id,
            evidence_by_id=evidence_by_id,
            evidence=evidence,
            topic_clusters=topic_clusters,
        )
        if support is None:
            continue
        cluster, evidence_ids = support
        if len(cluster.platforms) < 2:
            continue
        validated_signals.append(
            signal.model_copy(
                update={
                    "topic": cluster.representative_title,
                    "platforms": list(cluster.platforms),
                    "cluster_id": cluster.cluster_id,
                    "evidence_ids": evidence_ids,
                }
            )
        )
    return output.model_copy(
        update={
            "discovered_verticals": validated_verticals,
            "recommended_angles": validated_angles,
            "cross_platform_signals": validated_signals,
        }
    )


def _validate_vertical_provenance(
    vertical: LLMVertical,
    *,
    evidence: Sequence[EvidenceRecord],
    topic_clusters: Sequence[TopicCluster],
    clusters_by_id: dict[str, TopicCluster],
    evidence_by_id: dict[str, EvidenceRecord],
) -> LLMVertical | None:
    """Retain only vertical provenance that resolves to canonical evidence."""
    declared_clusters = {
        cluster_id for cluster_id in vertical.cluster_ids if cluster_id in clusters_by_id
    }
    declared_evidence = {
        evidence_id for evidence_id in vertical.evidence_ids if evidence_id in evidence_by_id
    }
    sample_evidence = _evidence_ids_for_titles(vertical.sample_topics, evidence)

    if declared_clusters:
        allowed_evidence = {
            evidence_id
            for cluster_id in declared_clusters
            for evidence_id in clusters_by_id[cluster_id].evidence_ids
        }
        supporting_evidence = (declared_evidence | sample_evidence) & allowed_evidence
        if not supporting_evidence:
            supporting_evidence = allowed_evidence
        cluster_ids = declared_clusters
    else:
        supporting_evidence = declared_evidence | sample_evidence
        cluster_ids = {
            cluster.cluster_id
            for cluster in topic_clusters
            if set(cluster.evidence_ids) & supporting_evidence
        }

    if not cluster_ids or not supporting_evidence:
        return None

    canonical_cluster_ids = [
        cluster.cluster_id
        for cluster in topic_clusters
        if cluster.cluster_id in cluster_ids
    ]
    canonical_evidence_ids = [
        record.evidence_id for record in evidence if record.evidence_id in supporting_evidence
    ]
    sample_topics = _canonical_sample_topics(
        vertical.sample_topics,
        canonical_evidence_ids,
        evidence_by_id,
    )
    return vertical.model_copy(
        update={
            "cluster_ids": canonical_cluster_ids,
            "evidence_ids": canonical_evidence_ids,
            "sample_topics": sample_topics,
        }
    )


def _evidence_ids_for_titles(
    titles: Sequence[str],
    evidence: Sequence[EvidenceRecord],
) -> set[str]:
    normalized_titles = {normalize_text(title) for title in titles if isinstance(title, str)}
    return {
        record.evidence_id
        for record in evidence
        if normalize_text(record.title) in normalized_titles
    }


def _canonical_sample_topics(
    requested_titles: Sequence[str],
    evidence_ids: Sequence[str],
    evidence_by_id: dict[str, EvidenceRecord],
) -> list[str]:
    allowed = set(evidence_ids)
    by_title = {
        normalize_text(record.title): record.title
        for evidence_id, record in evidence_by_id.items()
        if evidence_id in allowed
    }
    result: list[str] = []
    for title in requested_titles:
        canonical = by_title.get(normalize_text(title)) if isinstance(title, str) else None
        if canonical and canonical not in result:
            result.append(canonical)
    for evidence_id in evidence_ids:
        title = evidence_by_id[evidence_id].title
        if title not in result:
            result.append(title)
    return result


def _resolve_support(
    *,
    cluster_id: str,
    evidence_ids: Sequence[str],
    fallback_titles: Sequence[str],
    clusters_by_id: dict[str, TopicCluster],
    evidence_by_id: dict[str, EvidenceRecord],
    evidence: Sequence[EvidenceRecord],
    topic_clusters: Sequence[TopicCluster],
) -> tuple[TopicCluster, list[str]] | None:
    """Resolve one model reference set only when every supplied id is valid."""
    supplied_ids = list(evidence_ids)
    if cluster_id:
        cluster = clusters_by_id.get(cluster_id)
        if cluster is None:
            return None
        return _validated_cluster_evidence(cluster, supplied_ids, evidence_by_id)

    if supplied_ids:
        if any(evidence_id not in evidence_by_id for evidence_id in supplied_ids):
            return None
        matched_clusters = [
            cluster
            for cluster in topic_clusters
            if set(supplied_ids).issubset(cluster.evidence_ids)
        ]
        if len(matched_clusters) != 1:
            return None
        return _validated_cluster_evidence(matched_clusters[0], supplied_ids, evidence_by_id)

    matched_clusters = find_clusters_for_titles(fallback_titles, evidence, topic_clusters)
    if len(matched_clusters) != 1:
        return None
    return matched_clusters[0], list(matched_clusters[0].evidence_ids)


def _validated_cluster_evidence(
    cluster: TopicCluster,
    supplied_ids: Sequence[str],
    evidence_by_id: dict[str, EvidenceRecord],
) -> tuple[TopicCluster, list[str]] | None:
    if not supplied_ids:
        return cluster, list(cluster.evidence_ids)
    if any(evidence_id not in evidence_by_id for evidence_id in supplied_ids):
        return None
    if not set(supplied_ids).issubset(cluster.evidence_ids):
        return None
    return cluster, sorted(set(supplied_ids))


def _vertical_sample_topics(name: str, verticals_by_name: dict[str, Any]) -> list[str]:
    vertical = verticals_by_name.get(name)
    return list(vertical.sample_topics) if vertical is not None else []


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
