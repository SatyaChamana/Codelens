"""Build a visual directory tree of a repository."""

from pathlib import Path
from src.config import settings


def should_skip(name: str) -> bool:
    """Check if a file/directory should be skipped."""
    for pattern in settings.skip_patterns:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False


def build_tree(repo_path: str, max_depth: int = 4) -> str:
    """Build a text representation of the repo directory tree.

    Args:
        repo_path: Path to the repository
        max_depth: How deep to traverse (default 4)

    Returns:
        String with the visual tree
    """
    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"Path not found: {repo_path}")

    lines = [f"{repo.name}/"]
    _walk(repo, lines, prefix="", depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _walk(directory: Path, lines: list, prefix: str, depth: int, max_depth: int):
    """Recursively walk and build tree lines."""
    if depth >= max_depth:
        return

    # Get sorted entries, directories first
    try:
        entries = sorted(
            directory.iterdir(),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
    except PermissionError:
        return

    # Filter out skipped entries
    entries = [e for e in entries if not should_skip(e.name)]

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "

        if entry.is_dir():
            # Count code files inside
            code_count = sum(
                1 for f in entry.rglob("*")
                if f.is_file() and f.suffix in settings.supported_extensions
            )
            suffix = f"  ({code_count} files)" if code_count > 0 else ""
            lines.append(f"{prefix}{connector}{entry.name}/{suffix}")
            _walk(entry, lines, prefix + extension, depth + 1, max_depth)
        else:
            size = entry.stat().st_size
            size_str = _format_size(size)
            lines.append(f"{prefix}{connector}{entry.name}  [{size_str}]")


def _format_size(size_bytes: int) -> str:
    """Format file size in human readable form."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def get_structure_summary(repo_path: str) -> dict:
    """Get a structured summary of the repo for the RAG context.

    This gives the LLM an understanding of how the project is organized.
    """
    repo = Path(repo_path)
    summary = {
        "name": repo.name,
        "top_level_dirs": [],
        "top_level_files": [],
        "total_dirs": 0,
        "total_files": 0,
    }

    for entry in sorted(repo.iterdir(), key=lambda e: e.name.lower()):
        if should_skip(entry.name):
            continue
        if entry.is_dir():
            code_files = [
                str(f.relative_to(repo))
                for f in entry.rglob("*")
                if f.is_file() and f.suffix in settings.supported_extensions
            ]
            summary["top_level_dirs"].append({
                "name": entry.name,
                "file_count": len(code_files),
            })
            summary["total_dirs"] += 1
            summary["total_files"] += len(code_files)
        elif entry.is_file():
            summary["top_level_files"].append(entry.name)
            summary["total_files"] += 1

    return summary


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "./repos/fastapi"
    print(build_tree(repo, max_depth=3))
    print("\n---\n")
    print(get_structure_summary(repo))