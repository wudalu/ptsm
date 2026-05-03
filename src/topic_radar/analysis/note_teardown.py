from __future__ import annotations

from dataclasses import dataclass, field
import re

from topic_radar.platforms.xiaohongshu import FeedDetail, Comment


@dataclass
class TeardownResult:
    feed_id: str
    title: str
    hook_type: str
    hook_confidence: float
    body_structure: str
    engagement_triggers: list[str]
    trigger_confidence: float = 0.0
    comment_signals: CommentSignals | None = None


@dataclass
class CommentSignals:
    question_density: float
    top_terms: list[tuple[str, int]]
    sentiment_ratio: float
    is_real_discussion: bool
    comment_count: int = 0


_HOOK_PATTERNS: list[tuple[str, str, float]] = [
    ("悬念", r"你绝对(想不到|不知道|没见过|猜不到)", 0.95),
    ("悬念", r"(居然|竟然|原来).{0,20}[，。！？]", 0.80),
    ("反常识", r"(其实|真正的|根本|从来).{2,15}(不是|没有|不会|不需要)", 0.90),
    ("反常识", r"你以为.{2,10}(其实|实际)?", 0.85),
    ("反常识", r"(别|不要|别再|千万别).{2,15}[了]", 0.80),
    ("情绪共鸣", r"(打工人|社畜|牛马|搬砖人|加班|内卷|焦虑|emo)", 0.90),
    ("情绪共鸣", r"(\b我\b).{0,10}(受不了|崩溃|累了|倦了|无力|窒息)", 0.85),
    ("情绪共鸣", r"(终于|总算|可算).{2,10}[了]", 0.75),
    ("利益驱动", r"(保姆级|手把手|一篇搞懂|彻底理解|零基础|一学就会|速成)", 0.90),
    ("利益驱动", r"(\d+个|\d+招|\d+条|\d+步|\d+分钟).{0,5}(学会|搞定|解决|掌握)", 0.85),
    ("身份认同", r"(30岁|35岁|95后|00后|独居|单身|已婚|宝妈|职场新人)", 0.85),
    ("身份认同", r"(当[你我].{2,8}(时候|以后))", 0.80),
]


def teardown(detail: FeedDetail) -> TeardownResult:
    hook_type, hook_conf = _classify_hook(detail.title)
    body_structure = _classify_body(detail.body)
    triggers = _detect_triggers(detail.title, detail.body)

    trigger_conf = _compute_trigger_confidence(detail, triggers)
    comment_sigs = analyze_comment_signals(detail.comments) if detail.comments else None

    return TeardownResult(
        feed_id=detail.feed_id,
        title=detail.title,
        hook_type=hook_type,
        hook_confidence=hook_conf,
        body_structure=body_structure,
        engagement_triggers=triggers,
        trigger_confidence=trigger_conf,
        comment_signals=comment_sigs,
    )


def _classify_hook(title: str) -> tuple[str, float]:
    best_type, best_conf = "信息直述", 0.3
    for hook_type, pattern, confidence in _HOOK_PATTERNS:
        if re.search(pattern, title):
            if confidence > best_conf:
                best_type, best_conf = hook_type, confidence
    return best_type, best_conf


def _classify_body(body: str) -> str:
    if not body.strip():
        return "短帖"

    starts = body[:60]
    question_density = starts.count("？") + starts.count("?")

    if any(cue in starts for cue in ("你是不是", "你有没有", "每人", "你们", "大家")):
        return "问题导入式"
    if question_density >= 2:
        return "问题驱动式"
    if any(cue in starts for cue in ("首先", "第一步", "准备", "需要", "材料")):
        return "教程式"
    if any(cue in starts for cue in ("昨天", "今天", "上周", "最近", "刚刚", "前天")) and question_density == 0:
        return "故事式"

    return "观点陈述式"


_TRIGGER_PATTERNS = [
    ("投票式提问", r"(你[们]?.{0,8}(吗|呢|\?|？)|大家.{0,8}(吗|呢|\?|？))"),
    ("留白邀请", r"(你们呢|你呢|聊聊|说说|分享一下|蹲一个|先收藏|一起聊聊)"),
    ("争议点设置", r"(有人说|很多人觉得|对吗|对吧|是不是)"),
    ("经验交换", r"(求推荐|有没有.{0,5}推荐|怎么办|怎么解决|求助|怎么.{0,5}呢)"),
    ("身份呼唤", r"(打工人|社畜|牛马|宝妈|独居女孩|一个人住|实习生)"),
]


def _detect_triggers(title: str, body: str) -> list[str]:
    triggers: list[str] = []
    combined = f"{title}\n{body}"
    for trigger_name, pattern in _TRIGGER_PATTERNS:
        if re.search(pattern, combined):
            triggers.append(trigger_name)
    if triggers and "留白邀请" not in triggers:
        if body.rstrip().endswith(("？", "?")):
            triggers.append("留白邀请")
    return triggers


def _compute_trigger_confidence(detail: FeedDetail, triggers: list[str]) -> float:
    base = len(triggers) * 0.25
    if detail.comments_count > 50:
        base += 0.25
    if detail.likes > 200:
        base += 0.15
    return min(base, 1.0)


def analyze_comment_signals(comments: list[Comment]) -> CommentSignals:
    if not comments:
        return CommentSignals(
            question_density=0.0, top_terms=[],
            sentiment_ratio=0.5, is_real_discussion=False, comment_count=0,
        )

    question_count = sum(1 for c in comments if c.is_question)
    question_density = question_count / len(comments)

    top_terms = _extract_top_terms(comments, limit=10)

    positive, negative = _estimate_sentiment(comments)
    total_sent = positive + negative
    sentiment = positive / total_sent if total_sent > 0 else 0.5

    is_real = question_density > 0.15 and len(comments) >= 5
    if len(comments) >= 10 and len(top_terms) >= 5 and sentiment > 0.3:
        is_real = True

    return CommentSignals(
        question_density=round(question_density, 3),
        top_terms=top_terms[:10],
        sentiment_ratio=round(sentiment, 3),
        is_real_discussion=is_real,
        comment_count=len(comments),
    )


def _extract_top_terms(comments: list[Comment], limit: int) -> list[tuple[str, int]]:
    term_freq: dict[str, int] = {}
    for comment in comments:
        terms = _tokenize_chinese(comment.content)
        for term in terms:
            if len(term) >= 2:
                term_freq[term] = term_freq.get(term, 0) + 1
    return sorted(term_freq.items(), key=lambda x: x[1], reverse=True)[:limit]


def _tokenize_chinese(text: str) -> list[str]:
    cleaned = re.sub(r"[^一-鿿㐀-䶿a-zA-Z0-9]", " ", text)
    return [t.strip().lower() for t in cleaned.split() if t.strip()]


_POSITIVE_TERMS = {
    "好", "不错", "喜欢", "赞", "厉害", "棒", "优秀", "美", "好看",
    "有用", "实用", "干货", "学到了", "种草", "有道理", "真实",
    "感动", "温暖", "治愈", "羡慕", "好评",
}
_NEGATIVE_TERMS = {
    "不好", "差", "烂", "假", "无聊", "无语", "炒作", "营销",
    "忽悠", "坑", "失望", "举报",
}


def _estimate_sentiment(comments: list[Comment]) -> tuple[int, int]:
    positive = 0
    negative = 0
    for comment in comments:
        content = comment.content
        pos_count = sum(1 for t in _POSITIVE_TERMS if t in content)
        neg_count = sum(1 for t in _NEGATIVE_TERMS if t in content)
        if pos_count > neg_count:
            positive += 1
        elif neg_count > pos_count:
            negative += 1
    return positive, negative
