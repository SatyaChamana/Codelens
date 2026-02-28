# CodeLens - One-Day Sprint Execution Plan

## Rules For Today

1. No phone, no X, no news. Full focus.
2. Do NOT watch tutorials. Build, get stuck, Google the specific error, keep building.
3. Each block has ONE deliverable. Ship it, commit it, move on.
4. Stuck for 20+ minutes? Write down the problem, skip to the next block. Circle back later.
5. Commit after EVERY block. Small commits > one big commit.
6. Water or green tea only. Prove you can focus without coffee.

---

## What's Already Done (Days 1-4)

- [x] `src/ingestion/cloner.py` - Clone any GitHub repo programmatically
- [x] `src/utils/language_detector.py` - Detect languages, discover code files, skip junk
- [x] `src/utils/tree_builder.py` - Build directory tree with file sizes and line counts
- [x] `src/ingestion/parser.py` - tree-sitter AST parsing into CodeUnit objects
- [x] `src/ingestion/chunker.py` - Smart chunking that respects function/class boundaries
- [x] `src/ingestion/metadata.py` - File summaries, import extraction, signatures
- [x] `src/generation/prompts.py` - System prompt, query template, context formatting
- [x] `src/config.py` - Settings (Ollama, ChromaDB, chunking params)
- [x] `src/main.py` - CLI skeleton (ingest, ask, chat, list, tree commands)

**Stack**: Ollama (local LLM + embeddings), ChromaDB, tree-sitter, LangChain, Rich CLI

---

## Today's Sprint

### Block 1 - Embedder + Vector Store (~90 min)

**Goal**: Chunks go in, semantic search comes out.

- [ ] Build `src/retrieval/embedder.py`:
  - Batch embedding via Ollama (`nomic-embed-text`)
  - Progress bar with Rich
  - Handle connection errors gracefully
- [ ] Build `src/retrieval/vector_store.py`:
  - ChromaDB with persistence (`./data/chroma_db`)
  - One collection per repository
  - `add_chunks()` - store chunks with full metadata
  - `search()` - semantic search with metadata filtering (language, file path, code type)
  - `delete_collection()` - remove a repo's data
  - Return results with similarity scores
- [ ] Smoke test: embed 10 chunks, search them, verify results make sense
- [ ] **Commit**

```python
# After this block:
from src.retrieval.vector_store import CodeVectorStore
store = CodeVectorStore("fastapi")
store.add_chunks(chunks)
results = store.search("How does routing work?", top_k=5)
```

---

### Block 2 - Full Ingestion Pipeline (~30 min)

**Goal**: One command indexes an entire repo end-to-end.

- [ ] Wire up the full pipeline in `src/main.py` `ingest` command:
  1. Clone repo
  2. Discover code files
  3. Parse each file into CodeUnits
  4. Chunk all CodeUnits
  5. Build file summaries (metadata.py) and add as chunks
  6. Embed and store in ChromaDB
  7. Print stats: files processed, chunks created, time taken
- [ ] Test: `python -m src.main ingest https://github.com/tiangolo/fastapi`
- [ ] **Commit**

---

### Block 3 - RAG Chain + Query Pipeline (~60 min)

**Goal**: Ask a question, get an answer with code references.

- [ ] Build `src/generation/chain.py`:
  - Connect ChromaDB retriever to Ollama LLM via LangChain
  - Format retrieved chunks using the existing `CONTEXT_CHUNK_TEMPLATE`
  - Feed formatted context + question into `QUERY_PROMPT_TEMPLATE`
  - Return answer + source references (file paths, line numbers)
- [ ] Build `src/generation/memory.py`:
  - Conversation buffer for multi-turn chat
  - Track which files have been discussed
  - Clear memory on repo switch
- [ ] Wire up CLI `ask` command: single question -> answer with sources
- [ ] Wire up CLI `chat` command: interactive loop with conversation memory
- [ ] Test with 5+ questions on FastAPI:
  - "How does dependency injection work?"
  - "Where is the Request object defined?"
  - "What middleware is available?"
  - "How does routing work?"
  - "Explain the APIRouter class"
- [ ] **Commit**

```python
# After this block:
python -m src.main ask "How does dependency injection work in FastAPI?"
# Returns: explanation with file paths, line numbers, and code snippets
```

---

### Block 4 - Streamlit UI (~90 min)

**Goal**: Web-based chat interface for CodeLens.

- [ ] Build `app.py` (project root):
  - Chat interface with message history
  - Code syntax highlighting in responses (st.code or markdown fences)
  - Sidebar:
    - Input field for GitHub URL + "Ingest" button with progress
    - List of indexed repos (click to select active repo)
    - Stats for selected repo (files, chunks, languages)
  - Source references shown below each answer (expandable)
- [ ] Build repo explorer page or sidebar tab:
  - File tree view of indexed repo
  - Click a file to see its summary (functions, classes, imports)
  - "Explain this file" button that auto-asks the question
- [ ] Test: ingest a repo via UI, ask questions, verify answers render properly
- [ ] **Commit**

---

### Block 5 - Docker + Production Ready (~45 min)

**Goal**: Anyone can run CodeLens with one command.

- [ ] Write `Dockerfile`:
  - Python 3.9+ base
  - Install dependencies
  - Expose Streamlit port
- [ ] Write `docker-compose.yml`:
  - CodeLens app service
  - Ollama service (for LLM + embeddings)
  - Shared volume for ChromaDB persistence
- [ ] Test: `docker-compose up` starts everything
- [ ] **Commit**

---

### Block 6 - Polish + Ship v1.0 (~45 min)

**Goal**: Project looks professional. The world knows about it.

- [ ] Update README with:
  - Project description + architecture diagram (text-based)
  - Setup instructions (local + Docker)
  - Actual example Q&A output (copy real responses)
  - Stats: "Indexed FastAPI (X files, Y chunks) in Z seconds"
  - Screenshots/GIFs of the Streamlit UI
  - Contributing section
- [ ] Clean up code: remove debug prints, add type hints where missing
- [ ] Update `src/main.py` `stats` command to show real data
- [ ] Final test: ingest a fresh repo, ask 5 questions, verify everything works
- [ ] Tag `v1.0` on GitHub
- [ ] **Commit and push**

---

## Stretch Goals (Only After v1.0 Ships)

Do these ONLY if you finish early. In priority order:

- [ ] Hybrid search: keyword (BM25) + semantic for better retrieval
- [ ] Re-ranking: retrieve 20, re-rank to top 5
- [ ] Multi-language support: add JS/TS tree-sitter grammars
- [ ] MLflow experiment tracking for chunking/retrieval configs
- [ ] Support private repos with GitHub token
- [ ] Incremental re-indexing (only changed files)

---

## Architecture (What You're Building Today)

```
GitHub URL
    │
    ▼
┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────┐
│  Cloner  │───▶│ Lang Detector │───▶│  Parser  │───▶│ Chunker  │
│          │    │ + Tree Builder│    │(tree-sit)│    │(AST-aware│
└──────────┘    └──────────────┘    └──────────┘    └──────────┘
                                                         │
                                                         ▼
┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────┐
│  Answer  │◀───│  RAG Chain   │◀───│ Retriever│◀───│ Embedder │
│ + Sources│    │  (Ollama)    │    │(ChromaDB)│    │(nomic-   │
└──────────┘    └──────────────┘    └──────────┘    │embed-text│
                                                    └──────────┘
    │
    ▼
┌──────────────────────────┐
│   Streamlit UI / CLI     │
│  Chat + Repo Explorer    │
└──────────────────────────┘
```

---

## Interview Prep (Practice This Out Loud)

> "Walk me through how CodeLens works."

"The user provides a GitHub URL. I clone the repo, then use tree-sitter to parse code into meaningful units like functions, classes, and modules, preserving line numbers and metadata. Small units become single chunks. Large ones get split at logical boundaries like method definitions. Each chunk gets a context header with its file path and scope, then it's embedded with Ollama's nomic-embed-text model and stored in ChromaDB with full metadata. When the user asks a question, I do a semantic search with optional metadata filters, retrieve the top relevant chunks, and pass them to a local LLM via Ollama with a prompt that forces file-path attribution. The whole thing runs locally - no API keys, no cloud dependencies."

> "What was the hardest part?"

"Getting the chunking right. Code is fundamentally different from natural language. A function split in half is useless. I had to balance between keeping full functions intact and staying within the embedding model's token limit. The tree-sitter AST gave me the granularity I needed, but mapping tree-sitter node types to meaningful code units took iteration."

> "Why local LLMs instead of OpenAI?"

"Privacy and cost. When you're analyzing proprietary codebases, sending code to external APIs is a non-starter for many companies. Running everything locally with Ollama means zero data leaves the machine, and there's no per-query cost after setup."
