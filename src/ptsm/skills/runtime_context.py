from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
import json
import re
from typing import Any, Protocol, Sequence

from ptsm.agent_runtime.state import ExecutionState
from ptsm.config.settings import Settings
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import (
    LangChainMcpToolRunner,
    McpToolRunner,
)
from ptsm.playbooks.registry import PlaybookDefinition
from ptsm.skills.loader import LoadedSkill

_WEEKDAY_TOKENS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
_WORK_CUES = ("老板", "领导", "工位", "下班", "上班", "需求", "开会", "会议", "群里", "打工")
_OVERTIME_CUES = ("下班", "需求", "加班", "临时", "今晚", "初稿", "工位", "微信", "群里")
_POETRY_CUES = ("苏轼", "定风波", "赤壁赋", "水调歌头", "诗词")


class RuntimeContextBuilder(Protocol):
    """Build dynamic skill context for a planner pass."""

    def build(self, *, scene: str, domain: str, playbook_id: str) -> str | None:
        """Return dynamic context text or `None` when unavailable."""


@dataclass(frozen=True)
class TrendHit:
    keyword: str
    title: str
    author: str
    likes: int
    comments: int
    shares: int
    collects: int

    @property
    def score(self) -> int:
        return self.likes + (self.comments * 4) + (self.shares * 6) + (self.collects * 2)


class SkillContextResolver:
    """Resolve dynamic context blocks for activated skills."""

    def __init__(self, *, builders: dict[str, RuntimeContextBuilder] | None = None) -> None:
        self._builders = builders or {}

    def resolve(
        self,
        *,
        state: ExecutionState,
        playbook: PlaybookDefinition,
        loaded_skills: Sequence[LoadedSkill],
    ) -> dict[str, str]:
        contexts: dict[str, str] = {}
        for loaded_skill in loaded_skills:
            builder = self._builders.get(loaded_skill.skill.skill_name)
            if builder is None:
                continue
            context = builder.build(
                scene=state["scene"],
                domain=playbook.domain,
                playbook_id=playbook.playbook_id,
            )
            if context:
                contexts[loaded_skill.skill.skill_name] = context
        return contexts


class XhsTrendScanContextBuilder:
    """Live XiaoHongShu trend scan for the `xhs_trend_scan` builtin skill."""

    def __init__(
        self,
        *,
        server_url: str,
        tool_runner: McpToolRunner | None = None,
    ) -> None:
        self.server_url = server_url
        self.tool_runner = tool_runner or LangChainMcpToolRunner(server_url=server_url)

    def build(self, *, scene: str, domain: str, playbook_id: str) -> str | None:
        try:
            return asyncio.run(
                self._build_async(scene=scene, domain=domain, playbook_id=playbook_id)
            )
        except RuntimeError as exc:
            if "asyncio.run()" in str(exc):
                raise
            return None
        except Exception:
            return None

    async def _build_async(
        self,
        *,
        scene: str,
        domain: str,
        playbook_id: str,
    ) -> str | None:
        tool_names = await self.tool_runner.list_tool_names()
        if "check_login_status" not in tool_names or "search_feeds" not in tool_names:
            return None

        login_payload = await self.tool_runner.invoke_tool("check_login_status", {})
        login_text = _extract_text(login_payload).strip()
        if "已登录" not in login_text or "未登录" in login_text:
            return None

        keywords = _derive_keywords(scene=scene, domain=domain, playbook_id=playbook_id)
        if not keywords:
            return None

        hits: list[TrendHit] = []
        for keyword in keywords:
            payload = await self.tool_runner.invoke_tool("search_feeds", {"keyword": keyword})
            hits.extend(_parse_trend_hits(payload=payload, keyword=keyword))

        if not hits:
            return None

        return _render_trend_context(scene=scene, keywords=keywords, hits=hits)


def build_skill_context_resolver(
    *,
    settings: Settings,
    xhs_tool_runner: McpToolRunner | None = None,
) -> SkillContextResolver:
    return SkillContextResolver(
        builders={
            "xhs_trend_scan": XhsTrendScanContextBuilder(
                server_url=settings.xhs_mcp_server_url,
                tool_runner=xhs_tool_runner,
            )
        }
    )


def _derive_keywords(*, scene: str, domain: str, playbook_id: str) -> list[str]:
    keywords: list[str] = []
    day_token = next((token for token in _WEEKDAY_TOKENS if token in scene), None)
    is_work_scene = any(cue in scene for cue in _WORK_CUES) or domain == "发疯文学"
    is_poetry_scene = any(cue in scene for cue in _POETRY_CUES) or domain == "苏轼诗词赏析"

    if day_token:
        if day_token == "周四":
            keywords.append("怎么才周四")
        else:
            keywords.append(day_token)
        if is_work_scene and day_token not in {"周六", "周日"} and "怎么才周四" not in keywords:
            keywords.append(f"打工人 {day_token}")

    if playbook_id == "fengkuang_daily_post" or domain == "发疯文学":
        keywords.append("发疯文学 打工人")
        if any(cue in scene for cue in _OVERTIME_CUES):
            keywords.append("隐形加班")
            keywords.append("下班前 新需求")

    if is_poetry_scene:
        for cue in _POETRY_CUES:
            if cue in scene:
                keywords.append(cue)

    return _dedupe_preserve_order(keywords)[:4]


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _parse_trend_hits(*, payload: object, keyword: str) -> list[TrendHit]:
    data = _extract_json_payload(payload)
    if not isinstance(data, dict):
        return []

    feeds = data.get("feeds")
    if not isinstance(feeds, list):
        return []

    hits: list[TrendHit] = []
    for item in feeds:
        if not isinstance(item, dict):
            continue
        card = item.get("noteCard")
        if not isinstance(card, dict):
            continue
        title = str(card.get("displayTitle", "")).strip()
        if not title:
            continue
        user = card.get("user")
        interact = card.get("interactInfo")
        if not isinstance(user, dict) or not isinstance(interact, dict):
            continue
        hits.append(
            TrendHit(
                keyword=keyword,
                title=title,
                author=str(user.get("nickname", "")).strip(),
                likes=_to_int(interact.get("likedCount")),
                comments=_to_int(interact.get("commentCount")),
                shares=_to_int(interact.get("sharedCount")),
                collects=_to_int(interact.get("collectedCount")),
            )
        )
    return hits


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0


def _render_trend_context(*, scene: str, keywords: Sequence[str], hits: Sequence[TrendHit]) -> str:
    top_hits = _top_unique_hits(hits=hits, limit=4)
    persona_titles = [
        hit.title for hit in top_hits if hit.keyword == "发疯文学 打工人" or "打工人" in hit.title
    ]
    primary_hook = _pick_primary_hook(keywords=keywords, hits=hits)
    tension = _infer_tension(scene)
    expression_template = " / ".join(persona_titles[:2]) or "打工人发疯文学"

    lines = [
        "# XHS Trend Scan Live Context",
        "",
        f"已执行实时站内热点扫描（{date.today().isoformat()}）：",
        f"- 查询词：{', '.join(f'`{keyword}`' for keyword in keywords)}",
        "",
        "高互动表达样本：",
    ]
    for hit in top_hits:
        lines.append(
            f"- `{hit.title}` by `{hit.author or '匿名'}`"
            f"（{hit.likes}赞/{hit.comments}评/{hit.shares}分享/{hit.collects}藏）"
        )

    lines.extend(
        [
            "",
            "建议写法：",
            f"- 主切口：`{primary_hook}`",
            f"- 表达模版：`{expression_template}`",
            f"- 场景张力：`{tension}`",
            "- 约束：只借情绪结构和讨论点，不复写原题，不堆砌热词。",
        ]
    )
    return "\n".join(lines)


def _top_unique_hits(*, hits: Sequence[TrendHit], limit: int) -> list[TrendHit]:
    ranked = sorted(hits, key=lambda item: item.score, reverse=True)
    titles_seen: set[str] = set()
    unique_hits: list[TrendHit] = []
    for hit in ranked:
        normalized = re.sub(r"\s+", "", hit.title)
        if normalized in titles_seen:
            continue
        titles_seen.add(normalized)
        unique_hits.append(hit)
        if len(unique_hits) >= limit:
            break
    return unique_hits


def _pick_primary_hook(*, keywords: Sequence[str], hits: Sequence[TrendHit]) -> str:
    if "怎么才周四" in keywords:
        return "怎么才周四"
    if "发疯文学 打工人" in keywords:
        return "打工人发疯文学"
    best_hit = max(hits, key=lambda item: item.score, default=None)
    if best_hit is not None:
        return best_hit.keyword
    return keywords[0]


def _infer_tension(scene: str) -> str:
    if "需求" in scene and any(cue in scene for cue in ("下班", "工位", "群里", "老板", "领导")):
        return "下班前被新需求拽回工位"
    if any(cue in scene for cue in ("老板", "领导")):
        return "情绪快要下班时又被上级一句话拽回现实"
    if any(cue in scene for cue in ("开会", "会议")):
        return "本来已经快要解放，结果又被会议续上半条命"
    return "把一个临近释放却突然被拽回现实的瞬间写具体"


def _extract_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        texts: list[str] = []
        for item in payload:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(texts)
    return json.dumps(payload, ensure_ascii=False)


def _extract_json_payload(payload: object) -> object:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict) and "text" in first:
            try:
                return json.loads(str(first["text"]))
            except json.JSONDecodeError:
                return {"text": str(first["text"])}
    try:
        return json.loads(_extract_text(payload))
    except json.JSONDecodeError:
        return {"text": _extract_text(payload)}
