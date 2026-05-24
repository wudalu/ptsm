from __future__ import annotations

from pathlib import Path
import pytest
import tempfile
import yaml
from ptsm.evaluations.playbook_contracts import PlaybookEvalContract, load_playbook_eval_contract


XHS_PLAYBOOK_IDS = [
    "fengkuang_daily_post",
    "sushi_poetry_daily_post",
    "wuxia_character_post",
    "ai_tech_daily_post",
    "daily_english_post",
    "modern_psychology_post",
    "human_enrichment_daily_post",
    "world_cup_daily_post",
    "reddit_curation_daily_post",
]

FORMULAIC_MARKERS = ["首先", "其次", "最后", "综上", "本文", "作为AI"]
FUNCTIONAL_LABEL_MARKERS = [
    "可复制疯话：",
    "可复制疯话:",
    "今日可复制疯话：",
    "可复制通勤疯话：",
    "可收藏小结：",
    "可收藏小结:",
    "可收藏句型：",
    "可保存单元：",
    "可保存单元:",
    "评论交接：",
    "评论交接:",
    "可以先收藏清单：",
    "可收藏看球清单：",
    "看球清单可以先收藏：",
    "可保存三步：",
    "可复制疯话",
    "今日可复制疯话",
    "可复制通勤疯话",
    "可收藏小结",
    "可收藏句型",
    "可保存单元",
    "评论交接",
    "可以先收藏清单",
    "可收藏看球清单",
    "看球清单可以先收藏",
    "可保存三步",
]

BODY_LENGTH_BANDS = {
    "fengkuang_daily_post": (120, 380),
    "modern_psychology_post": (260, 620),
    "human_enrichment_daily_post": (180, 520),
    "sushi_poetry_daily_post": (180, 520),
    "daily_english_post": (180, 520),
    "ai_tech_daily_post": (220, 650),
    "world_cup_daily_post": (220, 620),
    "reddit_curation_daily_post": (220, 700),
    "wuxia_character_post": (700, 1100),
}

GENERIC_TITLE_MARKERS = {
    "fengkuang_daily_post": ["实录", "日常", "今日已疯", "发疯文学"],
    "modern_psychology_post": ["心理学小知识", "情绪管理干货", "小红书爆款"],
    "human_enrichment_daily_post": ["治愈生活", "精致日常", "改造分享"],
    "sushi_poetry_daily_post": ["苏轼诗词赏析", "诗词分享", "读书笔记"],
    "daily_english_post": ["每日英语单词", "英语学习干货", "万能表达"],
    "ai_tech_daily_post": ["AI科技资讯", "今日AI新闻", "科技速递"],
    "world_cup_daily_post": ["世界杯资讯", "比赛分析", "赛报"],
    "reddit_curation_daily_post": ["Reddit", "外网搬运", "英文讨论"],
    "wuxia_character_post": ["武侠人物评述", "人物分析", "读书笔记"],
}


class TestPlaybookEvalContract:
    def test_loads_fengkuang_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "fengkuang_daily_post")
        assert contract is not None
        assert contract.suite_id == "fengkuang_daily_post.default"
        assert "planner" in contract.node_contracts
        assert "executor" in contract.node_contracts
        assert "finalize" in contract.node_contracts
        constraints = contract.node_contracts["executor"].get("constraints", {})
        assert constraints.get("title_max_chars") == 30
        assert "打工人地铁生存实录" in constraints["title_must_not_equal_any"]
        assert "今日已疯" in constraints["image_text_must_not_equal_any"]
        assert "评论区" in constraints["body_must_include_comment_prompt_any"]
        assert "可复制" in constraints["body_must_include_save_trigger_any"]
        assert "变体要求" in constraints["body_must_not_include_any"]
        assert "comment_chain" in constraints["body_must_not_include_any"]
        quality_judge = contract.quality_judges["executor_content_quality"]
        assert quality_judge["evaluator_id"] == "llm.executor.content_quality"
        assert quality_judge["gate_level"] == "required"

    def test_missing_optional_contract_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            playbook_dir = Path(tmp) / "empty_playbook"
            playbook_dir.mkdir(parents=True)
            (playbook_dir / "playbook.yaml").write_text("playbook_id: empty_playbook")
            result = load_playbook_eval_contract(Path(tmp), "empty_playbook")
            assert result is None

    def test_invalid_node_contract_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            playbook_dir = Path(tmp) / "bad_playbook"
            playbook_dir.mkdir(parents=True)
            (playbook_dir / "playbook.yaml").write_text("playbook_id: bad_playbook")
            (playbook_dir / "evaluation.yaml").write_text("{}")
            with pytest.raises(ValueError, match="suite_id"):
                load_playbook_eval_contract(Path(tmp), "bad_playbook")

    def test_node_contracts_for_phase(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "fengkuang_daily_post")
        assert contract is not None
        nc = contract.node_contracts.get("executor", {})
        assert "title" in nc.get("required_fields", [])
        assert "hashtags" in nc.get("required_fields", [])

    def test_to_dict(self):
        contract = PlaybookEvalContract(
            suite_id="test.default",
            version=2,
            uses={"artifact": "artifact.v1"},
            node_contracts={"finalize": {"required_fields": ["playbook_id"]}},
        )
        d = contract.to_dict()
        assert d["suite_id"] == "test.default"
        assert d["version"] == 2

    def test_loads_modern_psychology_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "modern_psychology_post")
        assert contract is not None
        assert contract.suite_id == "modern_psychology_post.default"
        executor_constraints = contract.node_contracts["executor"]["constraints"]
        assert "#心理学" in executor_constraints["hashtags_must_include_any"]
        assert "诊断" in executor_constraints["body_must_not_include_any"]
        assert "变体要求" in executor_constraints["body_must_not_include_any"]
        assert "save_tool" in executor_constraints["body_must_not_include_any"]
        assert "专业帮助" in executor_constraints["body_must_include_all"]
        assert "评论区" in executor_constraints["body_must_include_comment_prompt_any"]
        assert "三栏" in executor_constraints["body_must_include_save_trigger_any"]
        assert (
            contract.quality_judges["executor_content_quality"]["evaluator_id"]
            == "llm.executor.content_quality"
        )

    def test_loads_human_enrichment_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "human_enrichment_daily_post")
        assert contract is not None
        assert contract.suite_id == "human_enrichment_daily_post.default"
        executor_constraints = contract.node_contracts["executor"]["constraints"]
        assert "#人类丰容计划" in executor_constraints["hashtags_must_include_any"]
        assert "变量" in executor_constraints["body_must_include_any"]
        assert "评论区" in executor_constraints["body_must_include_comment_prompt_any"]
        assert "清单" in executor_constraints["body_must_include_save_trigger_any"]
        assert "治好" in executor_constraints["body_must_not_include_any"]
        assert "image_brief" in executor_constraints["body_must_not_include_any"]
        assert "pattern_id" in executor_constraints["body_must_not_include_any"]
        assert "低成本" in executor_constraints["body_must_include_any"]
        assert "十分钟" in executor_constraints["body_must_include_any"]
        assert "今天能试" in executor_constraints["body_must_include_any"]
        quality_judge = contract.quality_judges["executor_content_quality"]
        assert quality_judge["evaluator_id"] == "llm.executor.content_quality"
        assert quality_judge["gate_level"] == "required"

    def test_loads_world_cup_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "world_cup_daily_post")
        assert contract is not None
        assert contract.suite_id == "world_cup_daily_post.default"
        executor_constraints = contract.node_contracts["executor"]["constraints"]
        assert "#世界杯" in executor_constraints["hashtags_must_include_any"]
        for term in ["赛前", "看点", "看球", "评论区", "清单"]:
            assert term in executor_constraints["body_must_include_any"]
        assert "评论区" in executor_constraints["body_must_include_comment_prompt_any"]
        assert "看球清单" in executor_constraints["body_must_include_save_trigger_any"]
        for forbidden in ["稳赚", "下注", "盘口", "预测比分", "内部消息", "官方消息"]:
            assert forbidden in executor_constraints["body_must_not_include_any"]
        quality_judge = contract.quality_judges["executor_content_quality"]
        assert quality_judge["evaluator_id"] == "llm.executor.content_quality"
        assert quality_judge["gate_level"] == "required"

    def test_loads_reddit_curation_contract(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, "reddit_curation_daily_post")
        assert contract is not None
        assert contract.suite_id == "reddit_curation_daily_post.default"
        executor_constraints = contract.node_contracts["executor"]["constraints"]
        assert "#Reddit" not in executor_constraints["hashtags_must_include_any"]
        for tag in ["#AI工具", "#人工智能", "#心理学", "#情绪管理", "#效率工具"]:
            assert tag in executor_constraints["hashtags_must_include_any"]
        assert "#Reddit" in executor_constraints["hashtags_must_not_include_any"]
        for term in ["AI", "工具", "压力", "评论区", "收藏"]:
            assert term in executor_constraints["body_must_include_any"]
        assert "评论区" in executor_constraints["body_must_include_comment_prompt_any"]
        assert "收藏" in executor_constraints["body_must_include_save_trigger_any"]
        for forbidden in [
            "Reddit",
            "reddit",
            "r/",
            "英文讨论",
            "翻成中文",
            "这次选的是",
            "source_url",
            "reddit.com",
            "我在Reddit上看到自己",
            "亲测",
            "诊断",
            "治好",
            "投资建议",
            "变体要求",
            "comment_chain",
            "save_tool",
            "identity_conflict",
        ]:
            assert forbidden in executor_constraints["body_must_not_include_any"]
        quality_judge = contract.quality_judges["executor_content_quality"]
        assert quality_judge["evaluator_id"] == "llm.executor.content_quality"
        assert quality_judge["gate_level"] == "required"

    def test_all_xhs_contracts_block_formulaic_cross_field_markers(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"

        for playbook_id in XHS_PLAYBOOK_IDS:
            contract = load_playbook_eval_contract(root, playbook_id)
            assert contract is not None
            constraints = contract.node_contracts["executor"]["constraints"]

            for marker in FORMULAIC_MARKERS:
                assert marker in constraints["combined_must_not_include_any"]

    def test_all_xhs_contracts_block_visible_functional_labels(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"

        for playbook_id in XHS_PLAYBOOK_IDS:
            contract = load_playbook_eval_contract(root, playbook_id)
            assert contract is not None
            constraints = contract.node_contracts["executor"]["constraints"]

            for marker in FUNCTIONAL_LABEL_MARKERS:
                assert marker in constraints["combined_must_not_include_any"]

    def test_all_xhs_contracts_define_domain_specific_body_length_bands(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"

        for playbook_id, (body_min, body_max) in BODY_LENGTH_BANDS.items():
            contract = load_playbook_eval_contract(root, playbook_id)
            assert contract is not None
            constraints = contract.node_contracts["executor"]["constraints"]

            assert constraints["body_min_chars"] == body_min
            assert constraints["body_max_chars"] == body_max

    def test_all_xhs_contracts_block_generic_title_substrings(self):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"

        for playbook_id, markers in GENERIC_TITLE_MARKERS.items():
            contract = load_playbook_eval_contract(root, playbook_id)
            assert contract is not None
            constraints = contract.node_contracts["executor"]["constraints"]

            for marker in markers:
                assert marker in constraints["title_must_not_include_any"]

    @pytest.mark.parametrize(
        ("playbook_id", "title_terms"),
        [
            ("fengkuang_daily_post", ["工牌", "群聊", "周报", "早会", "下班", "领导", "物件"]),
            ("modern_psychology_post", ["不是你", "边界", "复盘", "消息", "睡前", "AI"]),
            ("human_enrichment_daily_post", ["丰容", "变量", "角落", "书桌", "路线", "材料"]),
            ("ai_tech_daily_post", ["AI", "普通人", "搭子", "工具", "更新"]),
            ("sushi_poetry_daily_post", ["苏轼", "这一句", "读", "年味", "节气"]),
            ("wuxia_character_post", ["令狐冲", "黄蓉", "郭靖", "老款", "边界", "自由"]),
        ],
    )
    def test_research_affected_contracts_require_title_hook_terms(
        self,
        playbook_id,
        title_terms,
    ):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, playbook_id)
        assert contract is not None
        constraints = contract.node_contracts["executor"]["constraints"]

        for term in title_terms:
            assert term in constraints["title_must_include_any"]

    @pytest.mark.parametrize(
        ("playbook_id", "required_tags", "required_body_terms"),
        [
            ("sushi_poetry_daily_post", ["#苏轼"], ["苏轼"]),
            ("wuxia_character_post", ["#金庸", "#古龙"], ["《笑傲江湖》", "《射雕英雄传》"]),
            ("ai_tech_daily_post", ["#AI资讯"], ["是什么", "为什么重要", "普通人"]),
            ("daily_english_post", ["#每日英语"], ["音标", "词性", "例句", "翻译"]),
        ],
    )
    def test_remaining_xhs_playbooks_have_required_quality_contracts(
        self,
        playbook_id,
        required_tags,
        required_body_terms,
    ):
        root = Path(__file__).parent.parent.parent.parent / "src" / "ptsm" / "playbooks" / "definitions"
        contract = load_playbook_eval_contract(root, playbook_id)

        assert contract is not None
        assert contract.suite_id == f"{playbook_id}.default"
        executor = contract.node_contracts["executor"]
        assert set(["title", "image_text", "body", "hashtags"]).issubset(
            set(executor["required_fields"])
        )
        constraints = executor["constraints"]
        assert constraints["hashtags_must_include_any"] == required_tags
        for term in required_body_terms:
            assert term in constraints["body_must_include_any"]
        assert constraints["body_must_include_comment_prompt_any"]
        assert constraints["body_must_include_save_trigger_any"]
        for leaked_token in [
            "变体要求",
            "模板要求",
            "comment_chain",
            "save_tool",
            "identity_conflict",
        ]:
            assert leaked_token in constraints["body_must_not_include_any"]
        quality_judge = contract.quality_judges["executor_content_quality"]
        assert quality_judge["evaluator_id"] == "llm.executor.content_quality"
        assert quality_judge["gate_level"] == "required"
