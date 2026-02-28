# CodeLens - Execution Plan

## Rules (Read Every Morning)

1. 60-90 minutes BEFORE your day job. No phone, no X, no news.
2. Do NOT watch tutorials longer than 15 minutes. Build, get stuck, Google the specific error, keep building.
3. Each day has ONE deliverable. Ship it, commit it, move on.
4. Stuck for 30+ minutes? Write down the problem, move to the next task. Fresh eyes tomorrow.
5. Commit to GitHub EVERY day. Even a README update counts.
6. No coffee while you work on this. Water or green tea. Prove to yourself you can focus without it.

---

## WEEK 1: Core Pipeline (Days 1-7)

### Day 1 - Repo Setup + Git Clone Feature

**Goal**: Project is live on GitHub. You can clone any repo programmatically.

- [ ] Create GitHub repo "codelens"
- [ ] Unzip the starter kit, push it
- [ ] Set up virtual environment, install dependencies
- [ ] Create `.env` with your OpenAI API key
- [ ] Build `cloner.py`:
  - Takes a GitHub URL as input
  - Clones it into `repos/` directory
  - Returns the local path
  - Handles errors (bad URL, private repo, already cloned)
- [ ] Test it: clone FastAPI repo, clone Flask repo
- [ ] Commit and push

**What you'll learn**: subprocess/gitpython for Git operations, input validation, error handling.

```python
# By end of day, this should work:
from src.ingestion.cloner import clone_repo
path = clone_repo("https://github.com/tiangolo/fastapi")
print(path)  # ./repos/fastapi
```

---

### Day 2 - Language Detection + File Discovery

**Goal**: Given a cloned repo, find all code files and identify their language.

- [ ] Build `language_detector.py`:
  - Map file extensions to languages (.py -> Python, .js -> JavaScript, etc.)
  - Support: Python, JavaScript, TypeScript, Java, Go, Rust, C, C++
  - Skip: images, binaries, lock files, node_modules, .git, __pycache__
- [ ] Build `tree_builder.py`:
  - Walk the repo directory
  - Build a tree structure of all code files
  - Include file sizes and line counts
  - Output a clean text representation
- [ ] Test on FastAPI repo: how many Python files? Total lines of code?
- [ ] Commit and push

**What you'll learn**: os.walk/pathlib, file filtering patterns, working with real messy codebases.

```python
# By end of day:
from src.utils.language_detector import get_code_files
files = get_code_files("./repos/fastapi")
# Returns: [{"path": "fastapi/main.py", "language": "python", "lines": 45}, ...]
```

---

### Day 3 - Code Parsing (The Hard Day)

**Goal**: Parse Python files into meaningful units (functions, classes, module-level code).

- [ ] Install tree-sitter and tree-sitter-python
- [ ] Build `parser.py`:
  - Parse a Python file into its AST using tree-sitter
  - Extract: functions (with signatures, docstrings, body)
  - Extract: classes (with methods, docstrings)
  - Extract: top-level code and imports
  - Preserve line numbers for each extracted unit
- [ ] Each extracted unit should be a dict with:
  - `type`: "function" | "class" | "module"
  - `name`: function/class name
  - `code`: the actual source code
  - `docstring`: if present
  - `start_line`: line number
  - `end_line`: line number
  - `file_path`: relative path in repo
  - `language`: "python"
  - `imports`: list of imports in scope
- [ ] Test on 5 different Python files from FastAPI
- [ ] Commit and push

**This is the hardest day.** tree-sitter has a learning curve. Budget extra time. If you can't get tree-sitter working, fall back to a regex-based parser (split on `def ` and `class `) as a temporary solution. Don't let perfect be the enemy of done.

```python
# By end of day:
from src.ingestion.parser import parse_python_file
units = parse_python_file("./repos/fastapi/fastapi/main.py")
# Returns list of CodeUnit objects with type, name, code, docstring, line numbers
```

---

### Day 4 - Smart Chunking + Metadata

**Goal**: Turn parsed code units into chunks ready for embedding.

- [ ] Build `chunker.py`:
  - Small functions (< 500 tokens): keep as one chunk
  - Large functions/classes (> 500 tokens): split at logical points (method boundaries)
  - Each chunk includes a "context header":
    ```
    File: fastapi/routing.py
    Class: APIRouter
    Method: add_api_route
    Lines: 145-189
    ```
  - This header gets prepended to the code so the embedding captures context
- [ ] Build `metadata.py`:
  - Extract imports for each file
  - Extract function signatures (just the def line)
  - Extract class hierarchy if present
  - Build a "file summary" (first docstring + imports + list of functions/classes)
- [ ] Process the entire FastAPI repo through the pipeline: clone -> detect -> parse -> chunk
- [ ] Print stats: how many chunks? Average chunk size? Distribution by type?
- [ ] Commit and push

```python
# By end of day:
from src.ingestion.chunker import chunk_code_units
chunks = chunk_code_units(parsed_units)
# Each chunk has: content, metadata (file, language, type, name, lines, imports)
```

---

### Day 5 - Embeddings + Vector Store

**Goal**: All chunks are embedded and stored in ChromaDB. Basic search works.

- [ ] Build `embedder.py`:
  - Batch embedding with OpenAI API (don't embed one at a time, batch them)
  - Handle rate limits with retries
  - Log token usage and cost
- [ ] Build `vector_store.py`:
  - Initialize ChromaDB with persistence
  - Create a collection per repository
  - Store chunks with full metadata
  - Implement search with metadata filtering:
    - Filter by language
    - Filter by file path (glob patterns)
    - Filter by code unit type (function/class/module)
  - Return results with similarity scores
- [ ] Full pipeline test:
  - Ingest FastAPI repo end-to-end
  - Search: "How does dependency injection work?"
  - Search: "Where is the Request object defined?"
  - Search: "What middleware is available?"
  - Verify results make sense
- [ ] Commit and push

```python
# By end of day:
from src.retrieval.vector_store import CodeVectorStore
store = CodeVectorStore("fastapi")
results = store.search("How does routing work?", top_k=5)
# Returns relevant code chunks with file paths and line numbers
```

---

### Day 6 (Saturday) - RAG Chain + CLI

**Goal**: End-to-end Q&A works. You ask a question, you get an answer with code references.

- [ ] Build `prompts.py` with a code-specific system prompt:
  ```
  You are CodeLens, an expert code analyst. You answer questions about
  codebases using retrieved source code as evidence.

  Rules:
  - Always reference specific file paths and line numbers
  - Show relevant code snippets in your answers
  - If retrieved code doesn't answer the question, say so honestly
  - Explain code in plain English, then show the relevant snippet
  - Note connections between different parts of the codebase
  ```
- [ ] Build `chain.py`:
  - LangChain RAG chain connecting retriever to LLM
  - Format retrieved chunks with file paths and line numbers
  - Handle the case where no relevant code is found
- [ ] Build `memory.py`:
  - Conversation buffer for multi-turn Q&A
  - Track which files have been discussed
- [ ] Build CLI in `src/main.py`:
  - `python -m src.main ingest <github_url>` to index a repo
  - `python -m src.main ask "question"` for single questions
  - `python -m src.main chat` for interactive multi-turn mode
  - `python -m src.main list` to see indexed repos
- [ ] Test with 10+ different questions on FastAPI repo
- [ ] Commit and push

**This is the big day. By tonight, CodeLens works.**

---

### Day 7 (Sunday) - Polish + First Post

**Goal**: README is updated, project looks professional, you've told the world about it.

- [ ] Update README with:
  - Actual example Q&A output (copy real responses from your testing)
  - Stats: "Indexed FastAPI (X files, Y chunks) in Z seconds"
  - Any interesting findings from building it
- [ ] Clean up code: docstrings, type hints, remove debug prints
- [ ] Write LinkedIn post:
  - What you built
  - One interesting technical challenge (probably the chunking)
  - Link to GitHub
  - Keep it under 200 words
- [ ] Write X post (shorter version)
- [ ] Commit final version and push
- [ ] REST. You earned it.

---

## WEEK 2: UI + Experiments + Production (Days 8-14)

### Day 8 - Streamlit UI: Chat Interface

- [ ] Basic chat layout with message history
- [ ] Code syntax highlighting in responses (use st.code)
- [ ] Input field for GitHub URL to ingest new repos
- [ ] Sidebar showing indexed repos and stats

### Day 9 - Streamlit UI: Repo Explorer

- [ ] File tree view of the indexed repo in sidebar
- [ ] Click a file to see its summary (functions, classes, imports)
- [ ] "Explain this file" button
- [ ] Filter/scope questions to specific directories

### Day 10 - MLflow Integration

- [ ] Track experiments:
  - Chunking strategy (AST-aware vs naive text split)
  - Chunk size (300 vs 500 vs 800 tokens)
  - Retrieval method (similarity vs MMR)
  - Embedding model comparison
- [ ] Build `eval_retrieval.py`:
  - Create 20 test questions with known correct files
  - Measure: retrieval accuracy (is the right file in top-5?)
  - Compare configurations

### Day 11 - Retrieval Tuning

- [ ] Run the evaluation suite across configurations
- [ ] Try hybrid search: keyword (BM25) + semantic
- [ ] Implement re-ranking: retrieve 20, re-rank to top 5
- [ ] Document findings in a notebook
- [ ] Pick best configuration based on data

### Day 12 - Multi-Language Support

- [ ] Add tree-sitter grammars for JavaScript and TypeScript
- [ ] Update parser to handle JS/TS (functions, classes, exports, React components)
- [ ] Test on a real JS/TS repo (maybe Next.js or Express)
- [ ] Verify retrieval quality on non-Python codebases

### Day 13 (Saturday) - Docker + Documentation

- [ ] Write Dockerfile
- [ ] Write docker-compose.yml
- [ ] Test full app runs from `docker-compose up`
- [ ] Write a "Contributing" section in README
- [ ] Add architecture diagram to README

### Day 14 (Sunday) - Ship v1.0

- [ ] Final testing across 3 different repos
- [ ] Screenshot/GIF of the Streamlit UI
- [ ] LinkedIn post about the finished product
- [ ] X post
- [ ] Update portfolio website
- [ ] Tag v1.0 on GitHub
- [ ] CELEBRATE. Then plan Project 2.

---

## Stretch Goals (Week 3+, only if v1.0 is solid)

- [ ] Support private repos with GitHub token
- [ ] Incremental re-indexing (only changed files)
- [ ] Code dependency graph visualization
- [ ] Deploy to AWS EC2 or ECS
- [ ] VS Code extension (big reach goal)
- [ ] Add LlamaIndex as alternative to LangChain for comparison

---

## Resources (Reference Only, Don't Binge)

- tree-sitter Python bindings: https://github.com/tree-sitter/py-tree-sitter
- LangChain code understanding: https://python.langchain.com/docs/tutorials/rag/
- ChromaDB metadata filtering: https://docs.trychroma.com/guides
- OpenAI embeddings: https://platform.openai.com/docs/guides/embeddings
- Streamlit chat: https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-a-basic-chatbot

**Rule: Open a resource only when stuck on a specific problem. Don't study. Build.**

---

## Interview Prep (Practice This Out Loud)

> "Walk me through how CodeLens works."

"The user provides a GitHub URL. I clone the repo, then use tree-sitter to parse code into meaningful units like functions, classes, and modules, preserving line numbers and metadata. Small units become single chunks. Large ones get split at logical boundaries like method definitions. Each chunk gets a context header with its file path and scope, then it's embedded with OpenAI's embedding model and stored in ChromaDB with full metadata. When the user asks a question, I do a semantic search with optional metadata filters, retrieve the top relevant chunks, and pass them to the LLM with a prompt that forces file-path attribution. I tracked all my chunking and retrieval experiments in MLflow and found that AST-aware chunking outperformed naive text splitting by about 40% on retrieval accuracy."

> "What was the hardest part?"

"Getting the chunking right. Code is fundamentally different from natural language. A function split in half is useless. I had to balance between keeping full functions intact and staying within the embedding model's token limit. The tree-sitter AST gave me the granularity I needed, but mapping tree-sitter node types to meaningful code units took iteration. I logged every configuration in MLflow so I could compare objectively."
