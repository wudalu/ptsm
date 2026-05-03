from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
import re

from topic_radar.platforms.weibo import TrendingItem


@dataclass
class CrossPlatformSignal:
    topic: str
    platforms: list[str]
    first_seen_platform: str = ""
    velocity: str = "stable"
    shared_keywords: list[str] = field(default_factory=list)


@dataclass
class DiscoveredVertical:
    name: str
    keywords: list[str]
    confidence: float
    heat_signals: dict[str, float]
    discussion_density: str
    sample_topics: list[str] = field(default_factory=list)
    suggested_angles: list[str] = field(default_factory=list)
    comment_themes: list[str] = field(default_factory=list)
    is_noise: bool = False


def discover_cross_platform(platform_items: dict[str, list[TrendingItem]]) -> list[CrossPlatformSignal]:
    """Find topics appearing across multiple platforms."""
    all_topics: dict[str, dict[str, TrendingItem]] = {}

    for platform, items in platform_items.items():
        for item in items:
            normalized = _normalize_topic(item.title)
            if normalized not in all_topics:
                all_topics[normalized] = {}
            all_topics[normalized][platform] = item

    signals: list[CrossPlatformSignal] = []
    for topic, platform_data in all_topics.items():
        if len(platform_data) < 2:
            continue
        platforms = sorted(platform_data)
        first = min(platform_data.values(), key=lambda x: x.rank or 999)
        shared_kw = _extract_shared_keywords([item.title for item in platform_data.values()])
        velocity = _estimate_velocity(list(platform_data.values()))

        signals.append(CrossPlatformSignal(
            topic=topic,
            platforms=platforms,
            first_seen_platform=first.platform,
            velocity=velocity,
            shared_keywords=shared_kw[:5],
        ))

    signals.sort(key=lambda s: len(s.platforms), reverse=True)
    return signals


def discover_verticals(all_trending: list[TrendingItem]) -> list[DiscoveredVertical]:
    """Cluster trending topics into candidate verticals."""
    raw_clusters = _cluster_by_keywords(all_trending)

    verticals: list[DiscoveredVertical] = []
    for name, items in raw_clusters:
        if not items:
            continue
        keywords = _extract_shared_keywords([item.title for item in items])
        confidence = _calc_confidence(items)
        heat = _calc_heat(items)
        sample_topics = [item.title for item in items[:5]]
        density = _estimate_discussion_density(items)
        is_noise = len(items) < 3 and confidence < 0.3
        angles = _suggest_angles(name, [item.title for item in items])
        themes = _infer_comment_themes(name, [item.title for item in items])

        verticals.append(DiscoveredVertical(
            name=name,
            keywords=keywords[:8],
            confidence=round(confidence, 3),
            heat_signals=heat,
            discussion_density=density,
            sample_topics=sample_topics,
            suggested_angles=angles,
            comment_themes=themes,
            is_noise=is_noise,
        ))

    verticals.sort(key=lambda v: v.confidence, reverse=True)
    return verticals


def _normalize_topic(title: str) -> str:
    cleaned = re.sub(r"[#@！!～~\s]+", "", title)
    cleaned = re.sub(r"[热爆新]$", "", cleaned)
    return cleaned[:30]


_CLUSTER_CENTERS: list[tuple[str, list[str]]] = [
    ("修复系手作", ["修复", "手作", "手工", "改造", "旧物", "废物", "钩织", "编织", "翻新"]),
    ("情绪疗愈", ["治愈", "疗愈", "放松", "解压", "冥想", "情绪", "焦虑", "内耗", "松弛感"]),
    ("AI效率", ["AI", "人工智能", "效率", "自动化", "工具", "prompt", "ChatGPT", "DeepSeek", "智能"]),
    ("轻养生", ["养生", "睡眠", "恢复", "运动", "饮食", "咖啡", "熬夜", "泡脚", "拉伸"]),
    ("宠物陪伴", ["宠物", "猫", "狗", "陪伴", "遛狗", "铲屎官", "养宠", "宠物友好"]),
    ("文博非遗", ["文博", "非遗", "博物馆", "展览", "传统", "手艺", "节气", "文化"]),
    ("打工人日常", ["打工人", "上班", "加班", "工位", "社畜", "老板", "内卷", "裸辞", "副业"]),
    ("旅游出行", ["旅游", "旅行", "户外", "露营", "徒步", "自驾", "攻略"]),
    ("美食烹饪", ["美食", "烹饪", "做饭", "菜谱", "食材", "早餐", "便当", "探店"]),
    ("穿搭美妆", ["穿搭", "美妆", "护肤", "发型", "穿搭灵感", "素颜", "化妆"]),
    ("家居生活", ["家居", "收纳", "布置", "租房", "改造", "家具", "装饰"]),
    ("科技数码", ["手机", "数码", "开箱", "测评", "APP", "软件", "硬件"]),
]


def _cluster_by_keywords(items: list[TrendingItem]) -> list[tuple[str, list[TrendingItem]]]:
    clusters: dict[str, list[TrendingItem]] = {}
    unassigned: list[TrendingItem] = []

    for item in items:
        best_cluster = None
        best_score = 0
        for name, keywords in _CLUSTER_CENTERS:
            score = sum(1 for kw in keywords if kw in item.title)
            if score > best_score:
                best_score = score
                best_cluster = name
        if best_cluster and best_score >= 1:
            clusters.setdefault(best_cluster, []).append(item)
        else:
            unassigned.append(item)

    result = [(name, items) for name, items in clusters.items()]
    if unassigned:
        result.append(("其他话题", unassigned))
    return result


def _extract_shared_keywords(titles: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for title in titles:
        keywords = _tokenize_title(title)
        counter.update(kw for kw in keywords if len(kw) >= 2)
    return [kw for kw, _ in counter.most_common(15) if counter[kw] >= 1]


def _tokenize_title(title: str) -> list[str]:
    cleaned = re.sub(r"[　 \t\n\r#@]", "", title)
    tokens: list[str] = []
    i = 0
    while i < len(cleaned):
        ch = cleaned[i]
        if "一" <= ch <= "鿿":
            if i + 1 < len(cleaned) and "一" <= cleaned[i + 1] <= "鿿":
                tokens.append(cleaned[i:i + 2])
            else:
                tokens.append(ch)
            i += 1
        elif ch.isalnum():
            start = i
            while i < len(cleaned) and cleaned[i].isalnum():
                i += 1
            tokens.append(cleaned[start:i])
        else:
            i += 1
    return tokens


def _calc_confidence(items: list[TrendingItem]) -> float:
    n = len(items)
    hot_avg = sum(item.hot_score for item in items) / max(n, 1)
    base = min(n / 10, 1.0) * 0.5
    hot_sig = min(hot_avg / 500_000, 1.0) * 0.5
    return min(base + hot_sig, 1.0)


def _calc_heat(items: list[TrendingItem]) -> dict[str, float]:
    platform_items: dict[str, list[TrendingItem]] = {}
    for item in items:
        platform_items.setdefault(item.platform, []).append(item)

    heat: dict[str, float] = {}
    for platform, platform_items_list in platform_items.items():
        if platform_items_list:
            heat[platform] = round(sum(i.hot_score for i in platform_items_list) / len(platform_items_list), 1)
    return heat


def _estimate_discussion_density(items: list[TrendingItem]) -> str:
    avg = sum(item.hot_score for item in items) / max(len(items), 1)
    if avg > 500_000:
        return "high"
    if avg > 100_000:
        return "medium"
    return "low"


def _estimate_velocity(items: list[TrendingItem]) -> str:
    hot_scores = [item.hot_score for item in items]
    if not hot_scores:
        return "stable"
    avg = sum(hot_scores) / len(hot_scores)
    if avg > 800_000:
        return "accelerating"
    if avg > 300_000:
        return "steady"
    return "fading"


_HOOK_TEMPLATES = [
    "低门槛可复制 + 天然晒图欲望 + 评论区经验交换",
    "情绪共鸣切入 + 身份标签唤起 + 你来我往式讨论",
    "反常识开头 + 证据链展开 + 结尾留白邀请",
    "实用性驱动 + 模板化输出 + 收藏/转发激励",
]


def _suggest_angles(vertical: str, sample_titles: list[str]) -> list[str]:
    angles: list[str] = []
    if any(kw in vertical for kw in ("手作", "修复", "手工")):
        angles.append("{product}改造前后对比，你们猜花了多少钱？")
    if any(kw in vertical for kw in ("情绪", "疗愈", "治愈")):
        angles.append("下班后10分钟的{ritual}，整个人都松下来")
    if any(kw in vertical for kw in ("AI", "效率")):
        angles.append("普通人用AI{tool}搞定{task}，附上步骤")
    if any(kw in vertical for kw in ("养生", "睡眠")):
        angles.append("坚持{habit}一个月后，{benefit}了")
    if any(kw in vertical for kw in ("打工人", "上班")):
        angles.append("工位上的{action}，旁边同事问我链接")
    if not angles:
        angles.append("{curiosity}如何用{method}实现{outcome}")
    return angles[:3]


def _infer_comment_themes(vertical: str, sample_titles: list[str]) -> list[str]:
    themes: dict[str, int] = {}
    for title in sample_titles:
        if "?" in title or "？" in title or "吗" in title:
            themes.setdefault("提问求解", 0)
            themes["提问求解"] += 1
        if any(kw in title for kw in ("推荐", "分享", "测评")):
            themes.setdefault("经验交换", 0)
            themes["经验交换"] += 1
        if any(kw in title for kw in (":", "：", "第", "day", "Day")):
            themes.setdefault("打卡记录", 0)
            themes["打卡记录"] += 1
    return sorted(themes, key=themes.get, reverse=True)[:3]
