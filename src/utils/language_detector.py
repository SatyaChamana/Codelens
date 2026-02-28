"""Detect programming languages and discover code files in a repository."""

from pathlib import Path
from dataclasses import dataclass

from src.config import settings


@dataclass
class CodeFile:
    """Represents a discovered code file."""

    path: str          # Relative path within the repo
    abs_path: str      # Absolute path on disk
    language: str      # Detected language
    extension: str     # File extension
    size_bytes: int    # File size
    line_count: int    # Number of lines


def should_skip(path: Path) -> bool:
    """Check if a path should be skipped during traversal."""
    path_str = str(path)
    for pattern in settings.skip_patterns:
        if pattern in path_str:
            return True
    return False


def count_lines(file_path: Path) -> int:
    """Count lines in a file, handling encoding issues gracefully."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def get_code_files(repo_path: str) -> list[CodeFile]:
    """Discover all code files in a repository.

    Args:
        repo_path: Path to the cloned repository

    Returns:
        List of CodeFile objects with metadata
    """
    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"Repository path not found: {repo_path}")

    code_files = []

    for file_path in repo.rglob("*"):
        # Skip directories
        if not file_path.is_file():
            continue

        # Skip ignored patterns
        if should_skip(file_path):
            continue

        # Check if the extension is supported
        ext = file_path.suffix.lower()
        if ext not in settings.supported_extensions:
            continue

        # Skip very large files (likely generated or data files)
        size = file_path.stat().st_size
        if size > 1_000_000:  # 1MB limit
            continue

        # Skip empty files
        if size == 0:
            continue

        language = settings.supported_extensions[ext]
        rel_path = str(file_path.relative_to(repo))

        code_files.append(CodeFile(
            path=rel_path,
            abs_path=str(file_path),
            language=language,
            extension=ext,
            size_bytes=size,
            line_count=count_lines(file_path),
        ))

    # Sort by path for consistent ordering
    code_files.sort(key=lambda f: f.path)
    return code_files


def get_repo_stats(code_files: list[CodeFile]) -> dict:
    """Generate summary statistics for discovered files."""
    if not code_files:
        return {"total_files": 0}

    languages = {}
    total_lines = 0

    for f in code_files:
        languages[f.language] = languages.get(f.language, 0) + 1
        total_lines += f.line_count

    return {
        "total_files": len(code_files),
        "total_lines": total_lines,
        "languages": dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)),
        "avg_file_lines": total_lines // len(code_files) if code_files else 0,
    }


if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.table import Table

    console = Console()

    repo_path = sys.argv[1] if len(sys.argv) > 1 else "./repos/fastapi"

    files = get_code_files(repo_path)
    stats = get_repo_stats(files)

    console.print(f"\n[bold]Repository: {repo_path}[/bold]")
    console.print(f"Total files: {stats['total_files']}")
    console.print(f"Total lines: {stats['total_lines']}")
    console.print(f"Languages: {stats['languages']}")

    # Show first 20 files
    table = Table(title="Code Files (first 20)")
    table.add_column("Path", style="cyan")
    table.add_column("Language", style="green")
    table.add_column("Lines", justify="right")

    for f in files[:20]:
        table.add_row(f.path, f.language, str(f.line_count))

    console.print(table)
