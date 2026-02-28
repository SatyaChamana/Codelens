"""Clone and manage GitHub repositories."""

import shutil
from pathlib import Path
from urllib.parse import urlparse

from git import Repo, GitCommandError
from rich.console import Console

from src.config import settings

console = Console()


def extract_repo_name(github_url: str) -> str:
    """Extract repository name from GitHub URL.

    Examples:
        https://github.com/tiangolo/fastapi -> fastapi
        https://github.com/tiangolo/fastapi.git -> fastapi
    """
    parsed = urlparse(github_url)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {github_url}. Expected format: https://github.com/owner/repo")

    repo_name = path_parts[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    return repo_name


def clone_repo(github_url: str, force: bool = False) -> Path:
    """Clone a GitHub repository into the repos directory.

    Args:
        github_url: Full GitHub URL (e.g., https://github.com/owner/repo)
        force: If True, delete existing clone and re-clone

    Returns:
        Path to the cloned repository
    """
    repo_name = extract_repo_name(github_url)
    target_path = Path(settings.repos_dir) / repo_name

    # Handle already-cloned repos
    if target_path.exists():
        if force:
            console.print(f"[yellow]Removing existing clone: {target_path}[/yellow]")
            shutil.rmtree(target_path)
        else:
            console.print(f"[green]Repository already cloned: {target_path}[/green]")
            return target_path

    # Clone
    console.print(f"[blue]Cloning {github_url}...[/blue]")
    try:
        Repo.clone_from(
            github_url,
            str(target_path),
            depth=1,  # Shallow clone (only latest commit, saves time and space)
        )
        console.print(f"[green]Cloned successfully to {target_path}[/green]")
    except GitCommandError as e:
        raise RuntimeError(f"Failed to clone {github_url}: {e}")

    return target_path


def list_cloned_repos() -> list[dict]:
    """List all cloned repositories with basic stats."""
    repos_path = Path(settings.repos_dir)
    repos = []

    for item in repos_path.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            # Count files
            code_files = sum(
                1 for f in item.rglob("*")
                if f.is_file() and f.suffix in settings.supported_extensions
            )
            repos.append({
                "name": item.name,
                "path": str(item),
                "code_files": code_files,
            })

    return repos


def delete_repo(repo_name: str) -> bool:
    """Delete a cloned repository."""
    target_path = Path(settings.repos_dir) / repo_name
    if target_path.exists():
        shutil.rmtree(target_path)
        console.print(f"[green]Deleted {repo_name}[/green]")
        return True
    console.print(f"[red]Repository not found: {repo_name}[/red]")
    return False


if __name__ == "__main__":
    # Quick test
    import sys

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://github.com/tiangolo/fastapi"

    path = clone_repo(url)
    print(f"\nCloned to: {path}")
    print(f"\nAll repos: {list_cloned_repos()}")
