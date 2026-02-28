"""CodeLens CLI - Main entry point."""

import sys
from rich.console import Console

console = Console()

USAGE = """
[bold]CodeLens[/bold] - Codebase Q&A with RAG

[bold]Usage:[/bold]
    python -m src.main ingest <github_url>    Index a GitHub repository
    python -m src.main ask "<question>"        Ask a single question
    python -m src.main chat                    Start interactive chat
    python -m src.main list                    List indexed repositories
    python -m src.main stats <repo_name>       Show stats for a repository

[bold]Examples:[/bold]
    python -m src.main ingest https://github.com/tiangolo/fastapi
    python -m src.main ask "How does dependency injection work?"
    python -m src.main chat
"""


def main():
    if len(sys.argv) < 2:
        console.print(USAGE)
        return

    command = sys.argv[1].lower()

    if command == "ingest":
        if len(sys.argv) < 3:
            console.print("[red]Please provide a GitHub URL.[/red]")
            return
        github_url = sys.argv[2]
        # TODO: Implement full ingestion pipeline
        # 1. Clone repo
        # 2. Discover code files
        # 3. Parse into code units
        # 4. Chunk
        # 5. Embed and store in ChromaDB
        from src.ingestion.cloner import clone_repo
        from src.utils.language_detector import get_code_files, get_repo_stats

        path = clone_repo(github_url)
        files = get_code_files(str(path))
        stats = get_repo_stats(files)
        console.print(f"\n[green]Discovered {stats['total_files']} code files ({stats['total_lines']} lines)[/green]")
        console.print(f"Languages: {stats['languages']}")
        console.print("\n[yellow]Next step: parsing and embedding (coming Day 3-5)[/yellow]")

    elif command == "ask":
        if len(sys.argv) < 3:
            console.print("[red]Please provide a question.[/red]")
            return
        question = sys.argv[2]
        # TODO: Implement query pipeline
        console.print(f"[yellow]Query pipeline coming Day 6. Question: {question}[/yellow]")

    elif command == "chat":
        # TODO: Implement interactive chat
        console.print("[yellow]Interactive chat coming Day 6.[/yellow]")

    elif command == "list":
        from src.ingestion.cloner import list_cloned_repos
        repos = list_cloned_repos()
        if not repos:
            console.print("[yellow]No repositories indexed yet.[/yellow]")
        for repo in repos:
            console.print(f"  [cyan]{repo['name']}[/cyan] - {repo['code_files']} code files")

    elif command == "stats":
        if len(sys.argv) < 3:
            console.print("[red]Please provide a repository name.[/red]")
            return
        # TODO: Show detailed stats
        console.print("[yellow]Stats coming soon.[/yellow]")
    elif command == "tree":
        if len(sys.argv) < 3:
            console.print("[red]Please provide a repository name.[/red]")
            return
        repo_name = sys.argv[2]
        repo_path = f"./repos/{repo_name}"
        from src.utils.tree_builder import build_tree
        try:
            tree = build_tree(repo_path, max_depth=3)
            console.print(tree)
        except FileNotFoundError:
            console.print(f"[red]Repository not found: {repo_name}[/red]")
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print(USAGE)


if __name__ == "__main__":
    main()
