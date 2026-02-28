"""CodeLens CLI - Main entry point."""

import sys
import time
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from src.config import settings

console = Console()

USAGE = """
[bold]CodeLens[/bold] - Codebase Q&A with RAG

[bold]Usage:[/bold]
    python -m src.main ingest <github_url>    Index a GitHub repository
    python -m src.main ask <repo> "<question>" Ask a single question
    python -m src.main chat <repo>             Start interactive chat
    python -m src.main list                    List indexed repositories

[bold]Examples:[/bold]
    python -m src.main ingest https://github.com/tiangolo/fastapi
    python -m src.main ask fastapi "How does dependency injection work?"
    python -m src.main chat fastapi
"""


def ingest(github_url: str):
    """Full ingestion pipeline: clone -> parse -> chunk -> embed -> store."""
    from src.ingestion.cloner import clone_repo
    from src.utils.language_detector import get_code_files, get_repo_stats
    from src.ingestion.parser import parse_python_file
    from src.ingestion.chunker import chunk_code_units
    from src.retrieval.vector_store import CodeVectorStore

    # Step 1: Clone
    repo_path = clone_repo(github_url)
    repo_name = repo_path.name

    # Step 2: Discover files
    code_files = get_code_files(str(repo_path))
    stats = get_repo_stats(code_files)
    console.print(f"[green]Found {stats['total_files']} code files ({stats['total_lines']} lines)[/green]")
    console.print(f"Languages: {stats['languages']}")

    # Step 3: Parse Python files
    python_files = [f for f in code_files if f.language == "python"]
    console.print(f"\n[blue]Parsing {len(python_files)} Python files...[/blue]")

    all_units = []
    failed = 0
    for i, f in enumerate(python_files):
        try:
            units = parse_python_file(f.abs_path, str(repo_path))
            all_units.extend(units)
        except Exception as e:
            failed += 1
        if (i + 1) % 50 == 0:
            console.print(f"  Parsed {i + 1}/{len(python_files)} files...")

    console.print(f"[green]Parsed {len(all_units)} code units from {len(python_files) - failed} files[/green]")
    if failed:
        console.print(f"[yellow]  ({failed} files had parse errors, skipped)[/yellow]")

    # Step 4: Chunk
    console.print(f"\n[blue]Chunking...[/blue]")
    all_chunks = chunk_code_units(all_units)
    console.print(f"[green]{len(all_units)} units -> {len(all_chunks)} chunks[/green]")

    # Step 5: Embed and store
    console.print(f"\n[blue]Embedding and storing in ChromaDB...[/blue]")
    console.print(f"[dim]This may take a few minutes for large repos.[/dim]")

    store = CodeVectorStore(repo_name)
    start = time.time()

    batch_size = 50
    total_added = 0
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        added = store.add_chunks(batch)
        total_added += added
        elapsed = time.time() - start
        console.print(f"  Embedded {min(i + batch_size, len(all_chunks))}/{len(all_chunks)} chunks ({elapsed:.0f}s)")

    elapsed = time.time() - start
    console.print(f"\n[bold green]Done! Indexed {repo_name}: {total_added} chunks in {elapsed:.0f}s[/bold green]")
    console.print(f"[dim]Run: python -m src.main chat {repo_name}[/dim]")


def ask(repo_name: str, question: str):
    """Ask a single question."""
    from src.generation.chain import CodeQAChain

    qa = CodeQAChain(repo_name)

    if qa.store.count == 0:
        console.print(f"[red]No data found for repo '{repo_name}'. Run ingest first.[/red]")
        return

    console.print(f"\n[dim]Searching {qa.store.count} chunks...[/dim]\n")

    result = qa.ask(question)

    console.print(Markdown(result["answer"]))

    console.print(f"\n[dim]--- Sources ({result['chunks_used']} chunks) ---[/dim]")
    for s in result["sources"]:
        console.print(f"  [cyan]{s['file']}[/cyan]:{s['lines']} ({s['type']}: {s['name']}) [dim]{s['score']:.3f}[/dim]")


def chat(repo_name: str):
    """Interactive multi-turn chat."""
    from src.generation.chain import CodeQAChain

    qa = CodeQAChain(repo_name)

    if qa.store.count == 0:
        console.print(f"[red]No data found for repo '{repo_name}'. Run ingest first.[/red]")
        return

    console.print(f"\n[bold]CodeLens Chat - {repo_name}[/bold]")
    console.print(f"[dim]{qa.store.count} chunks indexed. Type 'quit' to exit.[/dim]\n")

    while True:
        try:
            question = input("\n[You] > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        console.print(f"\n[dim]Thinking...[/dim]")
        result = qa.ask(question)

        console.print()
        console.print(Markdown(result["answer"]))

        console.print(f"\n[dim]Sources:[/dim]")
        for s in result["sources"]:
            console.print(f"  [cyan]{s['file']}[/cyan]:{s['lines']} [dim]({s['type']}: {s['name']})[/dim]")


def list_repos():
    """List all indexed repositories."""
    from src.retrieval.vector_store import CodeVectorStore
    store = CodeVectorStore("_dummy")
    collections = store.list_collections()
    repos = [c.replace("repo_", "") for c in collections if c.startswith("repo_")]
    if not repos:
        console.print("[yellow]No repositories indexed yet.[/yellow]")
    else:
        console.print("[bold]Indexed repositories:[/bold]")
        for r in repos:
            s = CodeVectorStore(r)
            console.print(f"  [cyan]{r}[/cyan] - {s.count} chunks")


def main():
    if len(sys.argv) < 2:
        console.print(USAGE)
        return

    command = sys.argv[1].lower()

    if command == "ingest":
        if len(sys.argv) < 3:
            console.print("[red]Usage: python -m src.main ingest <github_url>[/red]")
            return
        ingest(sys.argv[2])

    elif command == "ask":
        if len(sys.argv) < 4:
            console.print("[red]Usage: python -m src.main ask <repo_name> \"<question>\"[/red]")
            return
        ask(sys.argv[2], sys.argv[3])

    elif command == "chat":
        if len(sys.argv) < 3:
            console.print("[red]Usage: python -m src.main chat <repo_name>[/red]")
            return
        chat(sys.argv[2])

    elif command == "list":
        list_repos()

    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print(USAGE)


if __name__ == "__main__":
    main()