"""Application configuration and settings."""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Ollama Settings
    ollama_base_url: str = "http://localhost:11434"
    
    # Paths
    repos_dir: str = "./repos"
    chroma_persist_dir: str = "./data/chroma_db"
    mlflow_tracking_uri: str = "./mlruns"

    # Embedding Settings (local via Ollama)
    embedding_model: str = "nomic-embed-text"  # Best open-source embedding model for Ollama
    embedding_batch_size: int = 50

    # LLM Settings (local via Ollama)
    llm_model: str = "llama3.2"  # Change to whatever model you have pulled
    temperature: float = 0.2  # Low temperature for code analysis (precision > creativity)
    max_tokens: int = 2048

    # Chunking Settings
    max_chunk_tokens: int = 500
    chunk_overlap_tokens: int = 50

    # Retrieval Settings
    retrieval_top_k: int = 8
    retrieval_method: str = "mmr"  # similarity, mmr, similarity_score_threshold

    # Supported Languages
    supported_extensions: dict = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".md": "markdown",
        ".txt": "text",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
    }

    # Directories/files to skip during ingestion
    skip_patterns: list = [
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        ".egg-info",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "*.min.js",
        "*.min.css",
        "package-lock.json",
        "yarn.lock",
        "poetry.lock",
        "Pipfile.lock",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

# Ensure directories exist
Path(settings.repos_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
