"""Smart code chunking that respects function and class boundaries."""

from dataclasses import dataclass, field
from typing import Optional

from src.ingestion.parser import CodeUnit
from src.config import settings


@dataclass
class CodeChunk:
    """A chunk ready for embedding with rich metadata."""

    content: str            # The text that gets embedded (context header + code)
    code: str               # Raw code without the header
    metadata: dict          # Everything we know about this chunk

    # Metadata fields for easy access
    file_path: str = ""
    language: str = ""
    chunk_type: str = ""    # function, method, class, imports, etc.
    name: str = ""
    parent_class: str = ""
    start_line: int = 0
    end_line: int = 0
    docstring: str = ""
    token_estimate: int = 0


def estimate_tokens(text: str) -> int:
    """Rough token estimate. 1 token ~ 4 characters for code."""
    return len(text) // 4


def build_context_header(unit: CodeUnit) -> str:
    """Build a context header that gets prepended to the chunk.

    This header helps the embedding model understand WHAT and WHERE
    this code is, dramatically improving retrieval quality.
    """
    parts = [f"File: {unit.file_path}"]

    if unit.parent_class:
        parts.append(f"Class: {unit.parent_class}")
        parts.append(f"Method: {unit.name}")
    elif unit.type == "class":
        parts.append(f"Class: {unit.name}")
    elif unit.type == "function":
        parts.append(f"Function: {unit.name}")
    elif unit.type == "imports":
        parts.append("Section: imports")
    elif unit.type == "module_docstring":
        parts.append("Section: module docstring")

    parts.append(f"Lines: {unit.start_line}-{unit.end_line}")
    parts.append(f"Language: {unit.language}")

    if unit.docstring:
        # Truncate long docstrings in the header
        doc_preview = unit.docstring[:200]
        if len(unit.docstring) > 200:
            doc_preview += "..."
        parts.append(f"Description: {doc_preview}")

    return " | ".join(parts)


def chunk_code_unit(unit: CodeUnit) -> list[CodeChunk]:
    """Turn a single CodeUnit into one or more chunks.

    Strategy:
        - Small units (< max_chunk_tokens): keep as one chunk
        - Large functions: split into signature+docstring chunk and body chunk
        - Large classes: already split into methods by the parser,
          but if the class itself is too big, we take just the signature
    """
    max_tokens = settings.max_chunk_tokens
    header = build_context_header(unit)
    full_content = f"{header}\n\n{unit.code}"
    tokens = estimate_tokens(full_content)

    # If it fits, ship it as one chunk
    if tokens <= max_tokens:
        return [_make_chunk(unit, full_content)]

    # For large classes: just keep the signature, docstring, and method list
    # (individual methods are already separate CodeUnits from the parser)
    if unit.type == "class":
        trimmed = _trim_class(unit)
        header = build_context_header(unit)
        content = f"{header}\n\n{trimmed}"
        return [_make_chunk(unit, content)]

    # For large functions/methods: split into logical parts
    if unit.type in ("function", "method"):
        return _split_function(unit, header, max_tokens)

    # For large import blocks or other types: hard split with overlap
    return _hard_split(unit, header, max_tokens)


def _make_chunk(unit: CodeUnit, content: str) -> CodeChunk:
    """Create a CodeChunk from a CodeUnit and formatted content."""
    return CodeChunk(
        content=content,
        code=unit.code,
        metadata={
            "file_path": unit.file_path,
            "language": unit.language,
            "chunk_type": unit.type,
            "name": unit.name,
            "parent_class": unit.parent_class,
            "start_line": unit.start_line,
            "end_line": unit.end_line,
            "has_docstring": bool(unit.docstring),
        },
        file_path=unit.file_path,
        language=unit.language,
        chunk_type=unit.type,
        name=unit.name,
        parent_class=unit.parent_class,
        start_line=unit.start_line,
        end_line=unit.end_line,
        docstring=unit.docstring,
        token_estimate=estimate_tokens(content),
    )


def _trim_class(unit: CodeUnit) -> str:
    """Extract just the class signature, docstring, and method signatures."""
    lines = unit.code.split("\n")
    trimmed_lines = []
    in_method_body = False
    indent_level = 0

    for line in lines:
        stripped = line.strip()

        # Always keep the class definition line
        if stripped.startswith("class "):
            trimmed_lines.append(line)
            in_method_body = False
            continue

        # Keep decorators
        if stripped.startswith("@"):
            trimmed_lines.append(line)
            in_method_body = False
            continue

        # Keep method signatures (def lines)
        if stripped.startswith("def "):
            trimmed_lines.append(line)
            in_method_body = True
            indent_level = len(line) - len(line.lstrip())
            continue

        # Keep docstrings right after class or method def
        if stripped.startswith('"""') or stripped.startswith("'''"):
            trimmed_lines.append(line)
            # Handle multi-line docstrings
            if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                # Docstring continues on next lines, but we just keep this line
                trimmed_lines.append("        ...")
            in_method_body = True
            continue

        # Skip method bodies
        if in_method_body:
            continue

        # Keep class-level assignments and other declarations
        if stripped and not stripped.startswith("#"):
            current_indent = len(line) - len(line.lstrip()) if stripped else 0
            # Class-level code (one indent level in)
            if 0 < current_indent <= 8:
                trimmed_lines.append(line)

    return "\n".join(trimmed_lines)


def _split_function(unit: CodeUnit, header: str, max_tokens: int) -> list[CodeChunk]:
    """Split a large function into signature+doc chunk and body chunks."""
    lines = unit.code.split("\n")
    chunks = []

    # Part 1: signature + docstring
    sig_lines = []
    body_start_idx = 0
    in_docstring = False
    docstring_done = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not docstring_done:
            sig_lines.append(line)

            # Track docstring boundaries
            if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                    # Single-line docstring
                    docstring_done = True
                    body_start_idx = i + 1
                else:
                    in_docstring = True
            elif in_docstring and (stripped.endswith('"""') or stripped.endswith("'''")):
                in_docstring = False
                docstring_done = True
                body_start_idx = i + 1
            elif not in_docstring and i > 0 and not stripped.startswith('"""') and not stripped.startswith("'''"):
                # No docstring found, body starts right after def line
                docstring_done = True
                body_start_idx = i
                break
        else:
            break

    # If we never found a docstring boundary, just take first 5 lines
    if not sig_lines or body_start_idx == 0:
        sig_lines = lines[:5]
        body_start_idx = 5

    sig_code = "\n".join(sig_lines)
    sig_unit = CodeUnit(
        type=unit.type,
        name=f"{unit.name} (signature)",
        code=sig_code,
        docstring=unit.docstring,
        start_line=unit.start_line,
        end_line=unit.start_line + len(sig_lines) - 1,
        file_path=unit.file_path,
        language=unit.language,
        parent_class=unit.parent_class,
    )
    sig_content = f"{header}\n\n{sig_code}"
    chunks.append(_make_chunk(sig_unit, sig_content))

    # Part 2: body in chunks
    body_lines = lines[body_start_idx:]
    if body_lines:
        body_text = "\n".join(body_lines)
        body_tokens = estimate_tokens(body_text)

        if body_tokens <= max_tokens:
            body_unit = CodeUnit(
                type=unit.type,
                name=f"{unit.name} (body)",
                code=body_text,
                docstring="",
                start_line=unit.start_line + body_start_idx,
                end_line=unit.end_line,
                file_path=unit.file_path,
                language=unit.language,
                parent_class=unit.parent_class,
            )
            body_content = f"{header}\n\n{body_text}"
            chunks.append(_make_chunk(body_unit, body_content))
        else:
            # Split body into overlapping windows
            chunk_size_lines = max(10, max_tokens // 10)  # Rough: 10 chars per line avg
            overlap_lines = 3

            i = 0
            part_num = 1
            while i < len(body_lines):
                end = min(i + chunk_size_lines, len(body_lines))
                chunk_lines = body_lines[i:end]
                chunk_text = "\n".join(chunk_lines)

                body_unit = CodeUnit(
                    type=unit.type,
                    name=f"{unit.name} (body part {part_num})",
                    code=chunk_text,
                    docstring="",
                    start_line=unit.start_line + body_start_idx + i,
                    end_line=unit.start_line + body_start_idx + end - 1,
                    file_path=unit.file_path,
                    language=unit.language,
                    parent_class=unit.parent_class,
                )
                body_content = f"{header}\n\n{chunk_text}"
                chunks.append(_make_chunk(body_unit, body_content))

                i = max(i + 1, end - overlap_lines)
                part_num += 1

    return chunks


def _hard_split(unit: CodeUnit, header: str, max_tokens: int) -> list[CodeChunk]:
    """Last resort: split text into overlapping windows."""
    lines = unit.code.split("\n")
    chunks = []
    chunk_size_lines = max(10, max_tokens // 10)
    overlap_lines = 3

    i = 0
    part_num = 1
    while i < len(lines):
        end = min(i + chunk_size_lines, len(lines))
        chunk_lines = lines[i:end]
        chunk_text = "\n".join(chunk_lines)

        chunk_unit = CodeUnit(
            type=unit.type,
            name=f"{unit.name} (part {part_num})",
            code=chunk_text,
            docstring="",
            start_line=unit.start_line + i,
            end_line=unit.start_line + end - 1,
            file_path=unit.file_path,
            language=unit.language,
            parent_class=unit.parent_class,
        )
        content = f"{header}\n\n{chunk_text}"
        chunks.append(_make_chunk(chunk_unit, content))

        i = max(i + 1, end - overlap_lines)
        part_num += 1

    return chunks


def chunk_code_units(units: list[CodeUnit]) -> list[CodeChunk]:
    """Process a list of CodeUnits into chunks."""
    all_chunks = []
    for unit in units:
        chunks = chunk_code_unit(unit)
        all_chunks.extend(chunks)
    return all_chunks


if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.table import Table
    from src.ingestion.parser import parse_python_file

    console = Console()

    file_path = sys.argv[1] if len(sys.argv) > 1 else "./repos/fastapi/fastapi/applications.py"
    repo_root = sys.argv[2] if len(sys.argv) > 2 else "./repos/fastapi"

    # Parse then chunk
    units = parse_python_file(file_path, repo_root)
    chunks = chunk_code_units(units)

    console.print(f"\n[bold]Parsed: {file_path}[/bold]")
    console.print(f"Code units: {len(units)} -> Chunks: {len(chunks)}\n")

    table = Table(title="Chunks")
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Name", style="green", width=35)
    table.add_column("Lines", justify="right", width=10)
    table.add_column("Tokens", justify="right", width=8)

    total_tokens = 0
    for chunk in chunks:
        line_range = f"{chunk.start_line}-{chunk.end_line}"
        table.add_row(chunk.chunk_type, chunk.name, line_range, str(chunk.token_estimate))
        total_tokens += chunk.token_estimate

    console.print(table)
    console.print(f"\n[bold]Total estimated tokens: {total_tokens}[/bold]")
    console.print(f"Average chunk size: {total_tokens // len(chunks) if chunks else 0} tokens")