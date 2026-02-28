"""Extract file-level metadata for enriching chunks and providing context."""

from pathlib import Path
from typing import Optional

from src.ingestion.parser import CodeUnit


def build_file_summary(file_path: str, units: list[CodeUnit]) -> str:
    """Build a natural language summary of a file's contents.

    This gets embedded as its own chunk so the LLM can answer
    questions like "What does this file do?" or "Where is X defined?"
    """
    parts = [f"File: {file_path}"]

    # Module docstring
    for unit in units:
        if unit.type == "module_docstring" and unit.docstring:
            parts.append(f"Purpose: {unit.docstring[:300]}")
            break

    # Imports
    for unit in units:
        if unit.type == "imports":
            parts.append(f"Imports: {unit.code}")
            break

    # Functions
    functions = [u for u in units if u.type == "function"]
    if functions:
        func_names = [f.name for f in functions]
        parts.append(f"Functions defined: {', '.join(func_names)}")

    # Classes
    classes = [u for u in units if u.type == "class"]
    if classes:
        for cls in classes:
            methods = [u.name for u in units if u.type == "method" and u.parent_class == cls.name]
            method_str = f" with methods: {', '.join(methods)}" if methods else ""
            doc_str = f" - {cls.docstring[:100]}" if cls.docstring else ""
            parts.append(f"Class: {cls.name}{doc_str}{method_str}")

    return "\n".join(parts)


def extract_dependencies(units: list[CodeUnit]) -> list[str]:
    """Extract import dependencies from parsed code units."""
    deps = []
    for unit in units:
        if unit.type == "imports":
            for line in unit.code.split("\n"):
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    deps.append(line)
    return deps


if __name__ == "__main__":
    import sys
    from src.ingestion.parser import parse_python_file

    file_path = sys.argv[1] if len(sys.argv) > 1 else "./repos/fastapi/fastapi/applications.py"
    repo_root = sys.argv[2] if len(sys.argv) > 2 else "./repos/fastapi"

    units = parse_python_file(file_path, repo_root)
    summary = build_file_summary(file_path, units)
    deps = extract_dependencies(units)

    print("=== File Summary ===")
    print(summary)
    print("\n=== Dependencies ===")
    for d in deps:
        print(f"  {d}")