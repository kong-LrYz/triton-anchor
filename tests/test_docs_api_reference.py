import io
import ast
import runpy
import sys
import types
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "docs" / "scripts" / "gen_api_reference.py"
PACKAGE_ROOT = REPO_ROOT / "python" / "triton_anchor"


def _load_generator():
    fake_module = types.ModuleType("mkdocs_gen_files")
    fake_module.open = lambda *_args, **_kwargs: io.StringIO()
    with patch.dict(sys.modules, {"mkdocs_gen_files": fake_module}):
        return runpy.run_path(str(GENERATOR))


def test_discovers_every_public_definition_once():
    generator = _load_generator()

    sections = generator["_discover_public_api"](PACKAGE_ROOT)
    api_paths = [api_path for _, entries in sections for api_path in entries]
    expected_paths = []
    for source_path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative_path = source_path.relative_to(PACKAGE_ROOT)
        if "tests" in relative_path.parts:
            continue
        if relative_path.name == "__init__.py" or relative_path.name.startswith("_"):
            continue
        module_name = "triton_anchor." + ".".join(relative_path.with_suffix("").parts)
        tree = ast.parse(source_path.read_text())
        expected_paths.extend(
            f"{module_name}.{node.name}"
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        )

    assert [section for section, _ in sections] == [
        "Core API",
        "Adapters",
        "Extensions",
    ]
    assert sorted(api_paths) == sorted(expected_paths)
    assert len(api_paths) == len(set(api_paths))
    assert all(".__init__." not in api_path for api_path in api_paths)
    assert all(".tests." not in api_path for api_path in api_paths)
    assert all(not api_path.rsplit(".", 1)[-1].startswith("_") for api_path in api_paths)


def test_every_public_api_and_method_has_a_docstring():
    generator = _load_generator()

    assert generator["_find_missing_docstrings"](PACKAGE_ROOT) == []


def test_every_public_api_docstring_is_english():
    generator = _load_generator()

    assert generator["_find_non_english_docstrings"](PACKAGE_ROOT) == []
