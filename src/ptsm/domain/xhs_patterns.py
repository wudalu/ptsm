from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha1
from typing import Any, Iterable


@dataclass(frozen=True)
class XhsSample:
    sample_id: str
    lane: str
    keyword: str
    title: str
    author: str = ""
    feed_id: str | None = None
    xsec_token: str | None = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    collects: int = 0
    cover_width: int | None = None
    cover_height: int | None = None
    has_cover_url: bool = False
    collected_at: str = ""
    source: str = "xiaohongshu-mcp"

    @property
    def engagement_score(self) -> int:
        return self.likes + (self.comments * 4) + (self.shares * 6) + (self.collects * 2)

    @property
    def cover_ratio(self) -> str | None:
        if not self.cover_width or not self.cover_height:
            return None
        ratio = self.cover_width / self.cover_height
        if abs(ratio - 0.75) <= 0.03:
            return "3:4"
        if abs(ratio - 1.0) <= 0.03:
            return "1:1"
        return f"{self.cover_width}:{self.cover_height}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["engagement_score"] = self.engagement_score
        data["cover_ratio"] = self.cover_ratio
        return data


@dataclass(frozen=True)
class PostFormatPattern:
    pattern_id: str
    lane: str
    status: str
    title_hook: str
    body_structure: str
    image_sequence: list[str]
    save_trigger: str
    comment_trigger: str
    example_titles: list[str]
    source_sample_ids: list[str]
    cover_ratio: str | None = None
    created_at: str = ""
    score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_xhs_sample(
    row: dict[str, Any],
    *,
    lane: str,
    collected_at: str,
) -> XhsSample:
    title = str(row.get("title") or "").strip()
    feed_id = _optional_str(row.get("feed_id"))
    sample_id = (
        _optional_str(row.get("sample_id"))
        or feed_id
        or _stable_sample_id(lane=lane, keyword=str(row.get("keyword") or ""), title=title)
    )
    return XhsSample(
        sample_id=sample_id,
        lane=str(row.get("lane") or lane),
        keyword=str(row.get("keyword") or "").strip(),
        title=title,
        author=str(row.get("author") or "").strip(),
        feed_id=feed_id,
        xsec_token=_optional_str(row.get("xsec_token")),
        likes=_to_int(row.get("likes")),
        comments=_to_int(row.get("comments")),
        shares=_to_int(row.get("shares")),
        collects=_to_int(row.get("collects")),
        cover_width=_to_optional_int(row.get("cover_width")),
        cover_height=_to_optional_int(row.get("cover_height")),
        has_cover_url=bool(row.get("has_cover_url")),
        collected_at=str(row.get("collected_at") or collected_at),
        source=str(row.get("source") or "xiaohongshu-mcp"),
    )


def load_samples_from_payload(payload: dict[str, Any], *, lane: str) -> list[XhsSample]:
    collected_at = str(payload.get("collected_at") or payload.get("created_at") or "")
    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list):
        raw_samples = payload.get("raw_trending") if isinstance(payload.get("raw_trending"), list) else []
    return [
        normalize_xhs_sample(sample, lane=lane, collected_at=collected_at)
        for sample in raw_samples
        if isinstance(sample, dict) and str(sample.get("title") or "").strip()
    ]


def analyze_samples_to_patterns(
    samples: Iterable[XhsSample],
    *,
    lane: str,
    created_at: str,
) -> list[PostFormatPattern]:
    grouped: dict[str, list[XhsSample]] = {}
    for sample in samples:
        if sample.lane != lane:
            continue
        grouped.setdefault(_infer_title_hook(sample.title), []).append(sample)

    patterns: list[PostFormatPattern] = []
    for title_hook, group in grouped.items():
        ranked = sorted(group, key=lambda sample: sample.engagement_score, reverse=True)
        source_ids = [sample.sample_id for sample in ranked[:6]]
        example_titles = [sample.title for sample in ranked[:3]]
        score = sum(sample.engagement_score for sample in ranked)
        pattern_id = _stable_pattern_id(lane=lane, title_hook=title_hook, source_ids=source_ids)
        patterns.append(
            PostFormatPattern(
                pattern_id=pattern_id,
                lane=lane,
                status="candidate",
                title_hook=title_hook,
                body_structure=_body_structure_for_hook(title_hook),
                image_sequence=_image_sequence_for_hook(title_hook),
                save_trigger=_save_trigger_for_hook(title_hook),
                comment_trigger="评论区交一个具体例子或你会先试的角落",
                example_titles=example_titles,
                source_sample_ids=source_ids,
                cover_ratio=_dominant_cover_ratio(ranked),
                created_at=created_at,
                score=score,
            )
        )
    return sorted(patterns, key=lambda pattern: pattern.score, reverse=True)


def _infer_title_hook(title: str) -> str:
    lowered = title.lower()
    if "突然意识到" in title:
        return "sudden_realization"
    if "人，你该" in title or "人,你该" in title:
        return "you_should_enrich"
    if "vs" in lowered or "前后" in title:
        return "before_after_contrast"
    if any(cue in title for cue in ("低成本", "建议收藏", "清单", "教程")):
        return "saveable_list"
    if any(cue in title for cue in ("过程", "完成", "原来这么简单", "新手必看")):
        return "process_or_tutorial"
    return "concrete_scene_hook"


def _body_structure_for_hook(title_hook: str) -> str:
    mapping = {
        "sudden_realization": "ordinary friction -> sudden realization -> one variable -> checklist -> comment",
        "you_should_enrich": "direct address -> ignored corner/object -> low-cost variable -> action boundary -> comment",
        "before_after_contrast": "before state -> changed variable -> after detail -> saveable comparison -> comment",
        "saveable_list": "problem -> low-cost checklist -> when to use -> comment",
        "process_or_tutorial": "finished state -> material/process -> three steps -> beginner note -> comment",
    }
    return mapping.get(title_hook, "specific scene -> one variable -> checklist -> comment")


def _image_sequence_for_hook(title_hook: str) -> list[str]:
    if title_hook == "process_or_tutorial":
        return ["cover", "materials", "process", "mini checklist", "finished detail", "comment invitation"]
    if title_hook == "before_after_contrast":
        return ["cover", "before state", "variable/material flat lay", "mini checklist", "after state", "comment invitation"]
    return ["cover", "before state", "variable/material flat lay", "mini checklist", "after state", "comment invitation"]


def _save_trigger_for_hook(title_hook: str) -> str:
    if title_hook in {"saveable_list", "process_or_tutorial"}:
        return "建议收藏的三步清单"
    if title_hook == "before_after_contrast":
        return "可截图的前后对照清单"
    return "三步清单"


def _dominant_cover_ratio(samples: list[XhsSample]) -> str | None:
    counts: dict[str, int] = {}
    for sample in samples:
        ratio = sample.cover_ratio
        if ratio:
            counts[ratio] = counts.get(ratio, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _stable_sample_id(*, lane: str, keyword: str, title: str) -> str:
    digest = sha1(f"{lane}|{keyword}|{title}".encode("utf-8")).hexdigest()[:10]
    return f"xhs-{digest}"


def _stable_pattern_id(*, lane: str, title_hook: str, source_ids: list[str]) -> str:
    digest = sha1("|".join(source_ids).encode("utf-8")).hexdigest()[:8]
    return f"{lane}.{title_hook}.{digest}"


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0


def _to_optional_int(value: object) -> int | None:
    parsed = _to_int(value)
    return parsed if parsed > 0 else None
