"""The dependency rules between layers, enforced by reading every import.

Dependencies point inwards: api -> services -> ports -> domain, with
infrastructure implementing the ports. A violation fails this test, so the
layering cannot erode unnoticed.
"""

import ast
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
LAYERS = {"api", "domain", "services", "ports", "infrastructure", "cities", "jobs", "evaluation"}
FRAMEWORKS = {"fastapi", "starlette", "sqlalchemy", "geoalchemy2", "alembic", "pgvector"}


def imported_modules(layer: str) -> dict[str, set[str]]:
    """Top-level module names imported by each file of a layer."""
    result: dict[str, set[str]] = {}
    for path in (BACKEND / layer).rglob("*.py"):
        names: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module.split(".")[0])
        result[str(path.relative_to(BACKEND))] = names
    return result


def violations(layer: str, forbidden: set[str]) -> list[str]:
    return [
        f"{file} imports {name}"
        for file, names in imported_modules(layer).items()
        for name in sorted(names & forbidden)
    ]


def third_party_imports(layer: str) -> list[str]:
    return [
        f"{file} imports {name}"
        for file, names in imported_modules(layer).items()
        for name in sorted(names - sys.stdlib_module_names - LAYERS)
    ]


def test_domain_uses_only_the_standard_library_and_itself() -> None:
    assert third_party_imports("domain") == []
    assert violations("domain", LAYERS - {"domain"}) == []


def test_ports_depend_only_on_the_domain() -> None:
    assert third_party_imports("ports") == []
    assert violations("ports", LAYERS - {"domain", "ports"}) == []


def test_city_configurations_are_plain_data_built_on_the_domain() -> None:
    assert third_party_imports("cities") == []
    assert violations("cities", LAYERS - {"domain", "cities"}) == []


def test_services_depend_on_ports_not_on_infrastructure_or_frameworks() -> None:
    assert violations("services", {"api", "infrastructure", "jobs"} | FRAMEWORKS) == []


@pytest.mark.parametrize("layer", ["domain", "ports", "services", "infrastructure", "cities"])
def test_nothing_below_the_api_imports_the_api(layer: str) -> None:
    assert violations(layer, {"api"}) == []


def test_the_api_never_imports_offline_jobs() -> None:
    assert violations("api", {"jobs"}) == []


@pytest.mark.parametrize(
    "layer", ["api", "domain", "services", "ports", "infrastructure", "cities", "jobs"]
)
def test_the_app_never_imports_the_evaluation_code(layer: str) -> None:
    """The evaluation needs heavy libraries the deployed image does not have."""
    assert violations(layer, {"evaluation"}) == []


def test_only_the_evaluation_package_imports_the_local_model_library() -> None:
    for layer in LAYERS - {"evaluation"}:
        assert violations(layer, {"sentence_transformers", "torch", "matplotlib"}) == []
