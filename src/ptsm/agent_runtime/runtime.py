from __future__ import annotations

from pathlib import Path
from typing import Any
from typing_extensions import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from ptsm.agent_runtime.agents import FengkuangDraftingAgent
from ptsm.config.settings import Settings, get_settings
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.llm.factory import build_drafting_backend
from ptsm.infrastructure.memory.store import InMemoryExecutionMemory
from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"
SKILL_ROOT = PACKAGE_ROOT / "skills" / "builtin"
DOMAIN_FENGKUANG = "发疯文学"


class FengkuangState(TypedDict, total=False):
    scene: str
    platform: str
    account_id: str
    status: str
    playbook_id: str
    required_skills: list[str]
    draft_content: dict[str, Any]
    final_content: dict[str, Any]
    reflection_feedback: str
    required_revision: bool
    attempt_count: int
    drafting_provider: str
    planner_prompt: str
    reflection_prompt: str
    reflection_rules: dict[str, str]
    loaded_skills: list[str]
    loaded_skill_contents: list[str]
    artifact_path: str


def build_fengkuang_workflow(
    memory: InMemoryExecutionMemory | None = None,
    drafting_agent: FengkuangDraftingAgent | None = None,
    max_attempts: int = 2,
    settings: Settings | None = None,
    artifact_store: FileArtifactStore | None = None,
):
    """Build a dry-run fengkuang workflow with one revision loop."""
    execution_memory = memory or InMemoryExecutionMemory()
    playbooks = PlaybookRegistry(playbook_root=PLAYBOOK_ROOT)
    playbook_loader = PlaybookLoader(playbook_root=PLAYBOOK_ROOT)
    skills = SkillRegistry(skill_root=SKILL_ROOT)
    skill_loader = SkillLoader(skills)
    settings = settings or get_settings()
    drafting_agent = drafting_agent or FengkuangDraftingAgent(
        backend=build_drafting_backend(settings)
    )
    drafting_provider = getattr(drafting_agent, "provider_name", "custom")
    artifact_store = artifact_store or FileArtifactStore()

    def ingest_request(state: FengkuangState) -> FengkuangState:
        return {
            "status": "running",
            "attempt_count": 0,
            "required_revision": False,
            "scene": state["scene"],
            "platform": state["platform"],
            "account_id": state["account_id"],
            "drafting_provider": drafting_provider,
        }

    def select_playbook(state: FengkuangState) -> FengkuangState:
        playbook = playbooks.select(domain=DOMAIN_FENGKUANG, platform=state["platform"])
        # Skill list is sourced from the playbook, but we still touch the registry to validate discovery.
        discovered = {skill.skill_name for skill in skills.list_skills()}
        missing = [name for name in playbook.required_skills if name not in discovered]
        if missing:
            raise LookupError(f"Missing required skills: {missing}")
        return {
            "playbook_id": playbook.playbook_id,
            "required_skills": playbook.required_skills,
        }

    def load_assets(state: FengkuangState) -> FengkuangState:
        playbook = playbook_loader.load(state["playbook_id"])
        loaded_skills = [skill_loader.load(name) for name in state["required_skills"]]
        return {
            "planner_prompt": playbook.planner_prompt,
            "reflection_prompt": playbook.reflection_prompt,
            "reflection_rules": playbook.definition.reflection,
            "loaded_skills": [skill.skill.skill_name for skill in loaded_skills],
            "loaded_skill_contents": [skill.content for skill in loaded_skills],
        }

    def draft_content(state: FengkuangState) -> FengkuangState:
        attempt_count = state["attempt_count"] + 1
        draft = drafting_agent.generate(
            scene=state["scene"],
            reflection_feedback=state.get("reflection_feedback"),
            planner_prompt=state.get("planner_prompt"),
            skill_contents=state.get("loaded_skill_contents", []),
        )
        return {
            "attempt_count": attempt_count,
            "draft_content": draft,
        }

    def reflect_content(state: FengkuangState) -> FengkuangState:
        rules = state["reflection_rules"]
        body = state["draft_content"]["body"]
        required_hashtag = rules["required_hashtag"]
        required_phrase = rules["must_include_phrase"]
        passed = required_hashtag in state["draft_content"]["hashtags"] and required_phrase in body
        if passed:
            return {
                "required_revision": False,
                "final_content": state["draft_content"],
                "reflection_feedback": "",
            }
        return {
            "required_revision": True,
            "reflection_feedback": state["reflection_prompt"],
        }

    def decide_next(state: FengkuangState) -> Literal["draft_content", "finalize"]:
        if state["required_revision"] and state["attempt_count"] < max_attempts:
            return "draft_content"
        return "finalize"

    def finalize(state: FengkuangState) -> FengkuangState:
        if state["required_revision"]:
            return {"status": "failed"}

        artifact_path = artifact_store.write(
            {
                "playbook_id": state["playbook_id"],
                "drafting_provider": state["drafting_provider"],
                "loaded_skills": state["loaded_skills"],
                "final_content": state["final_content"],
            },
            run_key=f"{state['account_id']}-{state['playbook_id']}-{state['attempt_count']}",
        )

        execution_memory.record(
            namespace=("accounts", state["account_id"], "lessons"),
            item={
                "playbook_id": state["playbook_id"],
                "scene": state["scene"],
                "attempt_count": state["attempt_count"],
                "final_body": state["final_content"]["body"],
            },
        )
        return {"status": "completed", "artifact_path": str(artifact_path)}

    graph = StateGraph(FengkuangState)
    graph.add_node("ingest_request", ingest_request)
    graph.add_node("select_playbook", select_playbook)
    graph.add_node("load_assets", load_assets)
    graph.add_node("draft_content", draft_content)
    graph.add_node("reflect_content", reflect_content)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "ingest_request")
    graph.add_edge("ingest_request", "select_playbook")
    graph.add_edge("select_playbook", "load_assets")
    graph.add_edge("load_assets", "draft_content")
    graph.add_edge("draft_content", "reflect_content")
    graph.add_conditional_edges("reflect_content", decide_next)
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=InMemorySaver())
