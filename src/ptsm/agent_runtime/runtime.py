from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from ptsm.agent_runtime.agents import FengkuangDraftingAgent
from ptsm.agent_runtime.graph.builder import build_execution_graph
from ptsm.agent_runtime.nodes.executor import build_executor_node
from ptsm.agent_runtime.nodes.ingest import build_ingest_node
from ptsm.agent_runtime.nodes.planner import build_planner_node
from ptsm.agent_runtime.nodes.reflector import build_reflector_node
from ptsm.agent_runtime.state import ExecutionState
from ptsm.config.settings import Settings, get_settings
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.llm.factory import build_drafting_backend
from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver
from ptsm.infrastructure.memory.store import (
    ExecutionMemoryStore,
    FileExecutionMemory,
    InMemoryExecutionMemory,
)
from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"
SKILL_ROOT = PACKAGE_ROOT / "skills" / "builtin"
DOMAIN_FENGKUANG = "发疯文学"
DEFAULT_RUNTIME_STATE_DIR = Path(".ptsm") / "agent_runtime"


def build_fengkuang_workflow(
    memory: ExecutionMemoryStore | None = None,
    drafting_agent: FengkuangDraftingAgent | None = None,
    max_attempts: int = 2,
    settings: Settings | None = None,
    artifact_store: FileArtifactStore | None = None,
    checkpointer: object | None = None,
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
    return build_execution_graph(
        ingest=build_ingest_node(drafting_provider=drafting_provider),
        planner=build_planner_node(
            domain=DOMAIN_FENGKUANG,
            playbooks=playbooks,
            playbook_loader=playbook_loader,
            skills=skills,
            skill_loader=skill_loader,
        ),
        executor=build_executor_node(drafting_agent=drafting_agent),
        reflector=build_reflector_node(max_attempts=max_attempts),
        finalize=build_finalize_node(
            execution_memory=execution_memory,
            artifact_store=artifact_store,
        ),
        checkpointer=checkpointer or InMemorySaver(),
    )


def build_file_backed_runtime_state(
    base_dir: Path | str = DEFAULT_RUNTIME_STATE_DIR,
) -> tuple[FileExecutionMemory, FileCheckpointSaver]:
    root = Path(base_dir).resolve()
    return (
        FileExecutionMemory(path=root / "execution-memory.json"),
        FileCheckpointSaver(path=root / "checkpoints.pkl"),
    )


def build_finalize_node(
    *,
    execution_memory: ExecutionMemoryStore,
    artifact_store: FileArtifactStore,
):
    def finalize(state: ExecutionState) -> ExecutionState:
        if state.get("reflection_decision") == "fail" or not state.get("final_content"):
            return {"status": "failed"}

        activated_skills = list(state.get("activated_skills", []))
        artifact_path = artifact_store.write(
            {
                "playbook_id": state["playbook_id"],
                "drafting_provider": state["drafting_provider"],
                "loaded_skills": activated_skills,
                "activated_skills": activated_skills,
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

    return finalize
