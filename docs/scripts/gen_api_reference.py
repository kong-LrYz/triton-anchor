import ast
import re
from pathlib import Path

import mkdocs_gen_files


TARGET_PATH = "index.md"
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "python" / "triton_anchor"

SECTION_NAMES = ("Core API", "Adapters", "Extensions")


def _section_name(relative_path: Path) -> str:
    if relative_path.parts[0] == "adapters":
        return "Adapters"
    if relative_path.parts[0] in {"extensions", "language"}:
        return "Extensions"
    return "Core API"


def _public_source_files(package_root: Path):
    for source_path in sorted(package_root.rglob("*.py")):
        relative_path = source_path.relative_to(package_root)
        if "tests" in relative_path.parts:
            continue
        if relative_path.name == "__init__.py" or relative_path.name.startswith("_"):
            continue
        yield source_path, relative_path


def _public_definitions(source_path: Path):
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                yield node


def _module_name(relative_path: Path) -> str:
    return "triton_anchor." + ".".join(relative_path.with_suffix("").parts)


def _discover_public_api(package_root: Path):
    sections = {section_name: [] for section_name in SECTION_NAMES}
    for source_path, relative_path in _public_source_files(package_root):
        module_name = _module_name(relative_path)
        section_name = _section_name(relative_path)
        for node in _public_definitions(source_path):
            sections[section_name].append(f"{module_name}.{node.name}")
    return tuple((section_name, tuple(sections[section_name])) for section_name in SECTION_NAMES)


def _find_missing_docstrings(package_root: Path):
    missing = []
    for source_path, relative_path in _public_source_files(package_root):
        module_name = _module_name(relative_path)
        for node in _public_definitions(source_path):
            object_name = f"{module_name}.{node.name}"
            if ast.get_docstring(node) is None:
                missing.append(object_name)
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not member.name.startswith("_") and ast.get_docstring(member) is None:
                            missing.append(f"{object_name}.{member.name}")
    return missing


def _find_non_english_docstrings(package_root: Path):
    non_english = []
    for source_path, relative_path in _public_source_files(package_root):
        module_name = _module_name(relative_path)
        for node in _public_definitions(source_path):
            object_name = f"{module_name}.{node.name}"
            docstring = ast.get_docstring(node) or ""
            if re.search(r"[\u4e00-\u9fff]", docstring):
                non_english.append(object_name)
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if member.name.startswith("_"):
                            continue
                        docstring = ast.get_docstring(member) or ""
                        if re.search(r"[\u4e00-\u9fff]", docstring):
                            non_english.append(f"{object_name}.{member.name}")
    return non_english


def main() -> None:
    missing_docstrings = _find_missing_docstrings(PACKAGE_ROOT)
    if missing_docstrings:
        missing_list = "\n".join(f"- {name}" for name in missing_docstrings)
        raise RuntimeError(f"Public APIs missing docstrings:\n{missing_list}")

    non_english_docstrings = _find_non_english_docstrings(PACKAGE_ROOT)
    if non_english_docstrings:
        non_english_list = "\n".join(f"- {name}" for name in non_english_docstrings)
        raise RuntimeError(f"Public API docstrings must be English:\n{non_english_list}")

    api_sections = _discover_public_api(PACKAGE_ROOT)
    api_count = sum(len(api_objects) for _, api_objects in api_sections)
    rendered_api_count = 0
    with mkdocs_gen_files.open(TARGET_PATH, "w") as f:
        f.write("# API Reference\n\n")
        f.write(
            "1. API Reference 的用途：本页汇总 `triton-anchor` 对外提供的 Python API。\n\n"
        )
        f.write("2. 内容范围：涵盖核心编译能力、适配器和扩展机制。\n\n")
        f.write(
            "3. 文档阅读方式：\n\n"
            "    ```text\n"
            "    APIName(parameter: Type) -> ReturnType\n"
            "    Brief description.\n\n"
            "    Parameters: parameter (Type) — Description.\n"
            "    Returns: ReturnType — Description.\n"
            "    Raises: ErrorType — Condition.\n"
            "    ```\n\n"
            "    第一行用于确认 API 名称、参数类型和返回类型，下一行说明 API 的主要功能。\n\n"
            "    `Parameters`、`Returns` 和 `Raises` 分别说明输入参数、返回结果和可能出现的异常。\n\n"
        )

        for section_name, api_objects in api_sections:
            f.write(f"## {section_name}\n\n")
            for api_object in api_objects:
                f.write(f"::: {api_object}\n\n")
                rendered_api_count += 1
                if rendered_api_count < api_count:
                    f.write("---\n\n")


main()
