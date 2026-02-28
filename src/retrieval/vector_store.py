"""ChromaDB vector store for code chunks with metadata filtering."""

import hashlib
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.ingestion.chunker import CodeChunk
from src.retrieval.embedder import get_embeddings


class CodeVectorStore:
    """Persistent vector store backed by ChromaDB.

    One collection per repository. Chunks are stored with full metadata
    for filtering by language, file path, and code type.
    """

    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.collection_name = f"repo_{repo_name}"
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return self._collection.count()

    def add_chunks(self, chunks: list[CodeChunk]) -> int:
        """Embed and store a list of CodeChunks.

        Returns the number of chunks added.
        """
        if not chunks:
            return 0

        # Deduplicate by content hash to avoid re-embedding identical chunks
        seen: set[str] = set()
        unique_chunks: list[CodeChunk] = []
        for chunk in chunks:
            h = hashlib.md5(chunk.content.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique_chunks.append(chunk)

        texts = [c.content for c in unique_chunks]
        embeddings = get_embeddings(texts)

        ids = [
            f"{self.repo_name}_{hashlib.md5(t.encode()).hexdigest()}"
            for t in texts
        ]

        # ChromaDB metadata values must be str, int, float, or bool
        metadatas = []
        for c in unique_chunks:
            metadatas.append({
                "file_path": c.file_path,
                "language": c.language,
                "chunk_type": c.chunk_type,
                "name": c.name,
                "parent_class": c.parent_class,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "has_docstring": bool(c.docstring),
                "token_estimate": c.token_estimate,
            })

        # ChromaDB has a batch limit, so insert in batches
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            self._collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
            )

        return len(unique_chunks)

    def search(
        self,
        query: str,
        top_k: int = 0,
        language: Optional[str] = None,
        file_path_contains: Optional[str] = None,
        chunk_type: Optional[str] = None,
    ) -> list[dict]:
        """Search for code chunks by semantic similarity.

        Args:
            query: Natural language search query.
            top_k: Number of results. Defaults to settings.retrieval_top_k.
            language: Filter to a specific language (e.g. "python").
            file_path_contains: Filter to files whose path contains this string.
            chunk_type: Filter to a specific type ("function", "class", "method", etc.).

        Returns:
            List of dicts with keys: content, metadata, score.
        """
        top_k = top_k or settings.retrieval_top_k

        query_embedding = get_embeddings([query])[0]

        where_filters = self._build_where(language, file_path_contains, chunk_type)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, self.count) if self.count else top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filters:
            kwargs["where"] = where_filters

        results = self._collection.query(**kwargs)

        output = []
        if results and results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                output.append({
                    "content": doc,
                    "metadata": meta,
                    "score": 1 - dist,  # cosine distance -> similarity
                })

        return output

    def delete_collection(self):
        """Delete this repo's collection from ChromaDB."""
        self._client.delete_collection(self.collection_name)

    def list_collections(self) -> list[str]:
        """List all repo collections in the store."""
        return [c.name for c in self._client.list_collections()]

    @staticmethod
    def _build_where(
        language: Optional[str],
        file_path_contains: Optional[str],
        chunk_type: Optional[str],
    ) -> Optional[dict]:
        """Build a ChromaDB where filter from optional parameters."""
        conditions = []

        if language:
            conditions.append({"language": {"$eq": language}})
        if chunk_type:
            conditions.append({"chunk_type": {"$eq": chunk_type}})
        if file_path_contains:
            conditions.append({"file_path": {"$contains": file_path_contains}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
