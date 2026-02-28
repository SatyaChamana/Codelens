"""Language-aware code parsing using tree-sitter."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter_python as tspython
from tree_sitter import Language, Parser


PY_LANGUAGE = Language(tspython.language())

parser = Parser(PY_LANGUAGE)


@dataclass
class CodeUnit:
    """A meaningful unit of code extracted from a file."""

    type: str              # "function", "class", "method", "module_docstring", "imports"
    name: str              # Function/class name or descriptive label
    code: str              # The actual source code
    docstring: str         # Extracted docstring if present
    start_line: int        # Starting line number (1-indexed)
    end_line: int          # Ending line number (1-indexed)
    file_path: str         # Relative path in the repo
    language: str          # Programming language
    parent_class: str = "" # If this is a method, the parent class name


def parse_python_file(file_path: str, repo_root: str = "") -> list[CodeUnit]:
    """Parse a Python file into meaningful code units.

    Extracts:
        - Module-level docstring
        - Import blocks
        - Functions (top-level)
        - Classes (with their methods as separate units)

    Args:
        file_path: Absolute path to the Python file
        repo_root: Root of the repo (for computing relative paths)

    Returns:
        List of CodeUnit objects
    """
    path = Path(file_path)
    try:
        source_code = path.read_bytes()
        source_text = source_code.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    # Compute relative path
    if repo_root:
        rel_path = str(path.relative_to(repo_root))
    else:
        rel_path = str(path)

    tree = parser.parse(source_code)
    root_node = tree.root_node

    units = []
    source_lines = source_text.split("\n")

    # Walk top-level children
    for node in root_node.children:

        # Module docstring (expression_statement containing a string at top level)
        if node.type == "expression_statement" and node.children:
            child = node.children[0]
            if child.type == "string":
                docstring = _extract_text(child, source_lines)
                units.append(CodeUnit(
                    type="module_docstring",
                    name="module_docstring",
                    code=_extract_text(node, source_lines),
                    docstring=docstring,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    file_path=rel_path,
                    language="python",
                ))

        # Import statements (group consecutive imports together)
        elif node.type in ("import_statement", "import_from_statement"):
            # Check if we already have an imports unit we can extend
            if units and units[-1].type == "imports":
                prev = units[-1]
                new_code = _extract_text(node, source_lines)
                units[-1] = CodeUnit(
                    type="imports",
                    name="imports",
                    code=prev.code + "\n" + new_code,
                    docstring="",
                    start_line=prev.start_line,
                    end_line=node.end_point[0] + 1,
                    file_path=rel_path,
                    language="python",
                )
            else:
                units.append(CodeUnit(
                    type="imports",
                    name="imports",
                    code=_extract_text(node, source_lines),
                    docstring="",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    file_path=rel_path,
                    language="python",
                ))

        # Functions
        elif node.type == "function_definition":
            unit = _parse_function(node, source_lines, rel_path, parent_class="")
            if unit:
                units.append(unit)

        # Classes
        elif node.type == "class_definition":
            class_units = _parse_class(node, source_lines, rel_path)
            units.extend(class_units)

        # Decorated definitions (functions or classes with @decorators)
        elif node.type == "decorated_definition":
            for child in node.children:
                if child.type == "function_definition":
                    unit = _parse_function(node, source_lines, rel_path, parent_class="")
                    if unit:
                        units.append(unit)
                elif child.type == "class_definition":
                    class_units = _parse_class(node, source_lines, rel_path)
                    units.extend(class_units)

    return units


def _parse_function(node, source_lines: list, file_path: str, parent_class: str) -> Optional[CodeUnit]:
    """Extract a function definition as a CodeUnit."""
    # Find the function name
    name = ""
    for child in node.children:
        if child.type == "identifier":
            name = _extract_text(child, source_lines)
            break
        # Handle decorated definitions
        if child.type == "function_definition":
            for subchild in child.children:
                if subchild.type == "identifier":
                    name = _extract_text(subchild, source_lines)
                    break
            break

    if not name:
        name = "unknown_function"

    code = _extract_text(node, source_lines)
    docstring = _extract_docstring(node, source_lines)

    unit_type = "method" if parent_class else "function"

    return CodeUnit(
        type=unit_type,
        name=name,
        code=code,
        docstring=docstring,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        file_path=file_path,
        language="python",
        parent_class=parent_class,
    )


def _parse_class(node, source_lines: list, file_path: str) -> list[CodeUnit]:
    """Extract a class and its methods as separate CodeUnits."""
    units = []

    # Find class name
    class_name = ""
    class_body = None

    for child in node.children:
        if child.type == "identifier":
            class_name = _extract_text(child, source_lines)
        elif child.type == "class_definition":
            # Decorated class: dig into the actual class node
            for subchild in child.children:
                if subchild.type == "identifier":
                    class_name = _extract_text(subchild, source_lines)
                elif subchild.type == "block":
                    class_body = subchild
        elif child.type == "block":
            class_body = child

    if not class_name:
        class_name = "UnknownClass"

    # First, add the class itself as a unit (signature + docstring + structure)
    class_code = _extract_text(node, source_lines)
    class_docstring = ""

    if class_body:
        class_docstring = _extract_docstring_from_body(class_body, source_lines)

    units.append(CodeUnit(
        type="class",
        name=class_name,
        code=class_code,
        docstring=class_docstring,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        file_path=file_path,
        language="python",
    ))

    # Then extract each method as a separate unit
    if class_body:
        for child in class_body.children:
            if child.type == "function_definition":
                method = _parse_function(child, source_lines, file_path, parent_class=class_name)
                if method:
                    units.append(method)
            elif child.type == "decorated_definition":
                for subchild in child.children:
                    if subchild.type == "function_definition":
                        method = _parse_function(child, source_lines, file_path, parent_class=class_name)
                        if method:
                            units.append(method)

    return units


def _extract_text(node, source_lines: list) -> str:
    """Extract the source text for a node."""
    start_line = node.start_point[0]
    end_line = node.end_point[0]

    if start_line == end_line:
        return source_lines[start_line][node.start_point[1]:node.end_point[1]]

    lines = []
    for i in range(start_line, min(end_line + 1, len(source_lines))):
        lines.append(source_lines[i])
    return "\n".join(lines)


def _extract_docstring(node, source_lines: list) -> str:
    """Extract docstring from a function/class node."""
    # Look for a block child, then find the first expression_statement with a string
    for child in node.children:
        if child.type == "block":
            return _extract_docstring_from_body(child, source_lines)
    return ""


def _extract_docstring_from_body(body_node, source_lines: list) -> str:
    """Extract docstring from a block/body node."""
    for child in body_node.children:
        if child.type == "expression_statement" and child.children:
            first = child.children[0]
            if first.type == "string":
                text = _extract_text(first, source_lines)
                # Clean up triple quotes
                text = text.strip()
                for quote in ['"""', "'''"]:
                    if text.startswith(quote) and text.endswith(quote):
                        text = text[3:-3].strip()
                return text
        # If the first statement isn't a docstring, there is no docstring
        elif child.type != "comment":
            break
    return ""


if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.table import Table

    console = Console()

    file_path = sys.argv[1] if len(sys.argv) > 1 else "./repos/fastapi/fastapi/applications.py"
    repo_root = sys.argv[2] if len(sys.argv) > 2 else "./repos/fastapi"

    units = parse_python_file(file_path, repo_root)

    console.print(f"\n[bold]Parsed: {file_path}[/bold]")
    console.print(f"Found {len(units)} code units\n")

    table = Table(title="Code Units")
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Name", style="green", width=30)
    table.add_column("Lines", justify="right", width=10)
    table.add_column("Docstring", width=50)

    for unit in units:
        line_range = f"{unit.start_line}-{unit.end_line}"
        doc_preview = unit.docstring[:47] + "..." if len(unit.docstring) > 50 else unit.docstring
        table.add_row(unit.type, unit.name, line_range, doc_preview)

    console.print(table)

    # Show one full unit as example
    if units:
        console.print(f"\n[bold]Example unit ({units[-1].type}: {units[-1].name}):[/bold]")
        console.print(f"```python\n{units[-1].code[:500]}\n```")