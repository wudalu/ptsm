from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src" / "ptsm"


@dataclass(frozen=True)
class BoundaryRule:
    package_prefix: str
    forbidden_prefixes: tuple[str, ...]
    description: str


RULES = (
    BoundaryRule(
        package_prefix="ptsm.interfaces",
        forbidden_prefixes=("ptsm.infrastructure", "ptsm.agent_runtime"),
        description="interfaces must depend on application-facing entrypoints, not runtime or infrastructure",
    ),
    BoundaryRule(
        package_prefix="ptsm.infrastructure",
        forbidden_prefixes=("ptsm.application", "ptsm.interfaces", "ptsm.agent_runtime"),
        description="infrastructure must stay as adapters, not depend upward on application, interfaces, or runtime",
    ),
    BoundaryRule(
        package_prefix="ptsm.agent_runtime",
        forbidden_prefixes=("ptsm.interfaces", "ptsm.application.use_cases"),
        description="agent_runtime must not depend on interfaces or application use case orchestration",
    ),
    BoundaryRule(
        package_prefix="ptsm.skills",
        forbidden_prefixes=("ptsm.application", "ptsm.interfaces", "ptsm.agent_runtime"),
        description="skills must stay request-scoped metadata/loading helpers, not runtime or application orchestrators",
    ),
    BoundaryRule(
        package_prefix="ptsm.playbooks",
        forbidden_prefixes=("ptsm.application", "ptsm.interfaces", "ptsm.agent_runtime"),
        description="playbooks must stay definition/loading modules, not runtime or application orchestrators",
    ),
)


def test_import_boundary_checker_reports_forbidden_imports(tmp_path: Path) -> None:
    path = tmp_path / "src" / "ptsm" / "interfaces" / "cli" / "bad.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from ptsm.infrastructure.observability.run_store import RunStore\n",
        encoding="utf-8",
    )

    violations = _find_boundary_violations(
        python_files=[path],
        project_root=tmp_path,
    )

    assert len(violations) == 1
    assert "interfaces must depend on application-facing entrypoints" in violations[0]
    assert "ptsm.infrastructure.observability.run_store" in violations[0]


def test_import_boundaries_hold() -> None:
    violations = _find_boundary_violations(
        python_files=sorted(SRC_ROOT.rglob("*.py")),
        project_root=PROJECT_ROOT,
    )
    assert not violations, "\n".join(violations)


def _find_boundary_violations(
    *,
    python_files: list[Path],
    project_root: Path,
) -> list[str]:
    violations: list[str] = []

    for path in python_files:
        module_name = _module_name_for_path(path=path, project_root=project_root)
        imports = _ptsm_imports_for_path(path)
        for rule in RULES:
            if not module_name.startswith(rule.package_prefix):
                continue
            for imported_name in imports:
                if any(imported_name.startswith(prefix) for prefix in rule.forbidden_prefixes):
                    violations.append(
                        f"{path.relative_to(project_root)} imports {imported_name} "
                        f"but rule '{rule.description}' forbids it"
                    )

    return violations


def _module_name_for_path(*, path: Path, project_root: Path) -> str:
    relative = path.relative_to(project_root / "src").with_suffix("")
    return ".".join(relative.parts)


def _ptsm_imports_for_path(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("ptsm."):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ptsm."):
            imports.add(node.module)
    return imports
