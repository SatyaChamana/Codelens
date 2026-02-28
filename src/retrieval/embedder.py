"""Batch embedding via Ollama using nomic-embed-text."""

from ollama import Client, ResponseError
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from src.config import settings


# nomic-embed-text context is 2048 tokens; stay safely under
MAX_EMBED_CHARS = 7000  # ~1750 tokens at 4 chars/token


def _truncate(text: str) -> str:
    """Truncate text to fit within the embedding model's context window."""
    if len(text) <= MAX_EMBED_CHARS:
        return text
    return text[:MAX_EMBED_CHARS]


def get_embeddings(texts: list[str], model: str = "") -> list[list[float]]:
    """Embed a list of texts in batches via Ollama.

    Args:
        texts: List of strings to embed.
        model: Ollama embedding model name. Defaults to settings.embedding_model.

    Returns:
        List of embedding vectors (one per input text).
    """
    if not texts:
        return []

    model = model or settings.embedding_model
    client = Client(host=settings.ollama_base_url)
    batch_size = settings.embedding_batch_size
    all_embeddings: list[list[float]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Embedding chunks...", total=len(texts))

        for i in range(0, len(texts), batch_size):
            batch = [_truncate(t) for t in texts[i : i + batch_size]]
            try:
                # Embed one at a time to avoid exceeding the model's
                # aggregate context limit when batching large chunks.
                for text in batch:
                    resp = client.embed(model=model, input=[text])
                    all_embeddings.extend(resp.embeddings)
            except ResponseError as e:
                if "not found" in str(e).lower():
                    raise RuntimeError(
                        f"Embedding model '{model}' not found. "
                        f"Run: ollama pull {model}"
                    ) from e
                raise
            except Exception as e:
                raise RuntimeError(
                    f"Failed to connect to Ollama at {settings.ollama_base_url}. "
                    f"Is Ollama running? Error: {e}"
                ) from e

            progress.update(task, advance=len(batch))

    return all_embeddings
