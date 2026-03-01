"""CodeLens - Streamlit Web Interface."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from src.ingestion.cloner import clone_repo, list_cloned_repos
from src.retrieval.vector_store import CodeVectorStore
from src.generation.chain import CodeQAChain


# Page config
st.set_page_config(
    page_title="CodeLens",
    page_icon="🔍",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    .stChatMessage [data-testid="stMarkdownContainer"] pre {
        background-color: #1e1e1e;
        border-radius: 8px;
        padding: 12px;
    }
    .source-box {
        background-color: #f0f2f6;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 4px 0;
        font-size: 0.85em;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)


def get_indexed_repos():
    """Get list of repos that have been indexed in ChromaDB."""
    try:
        store = CodeVectorStore("_dummy")
        collections = store.list_collections()
        repos = []
        for c in collections:
            if c.startswith("repo_"):
                name = c.replace("repo_", "")
                s = CodeVectorStore(name)
                repos.append({"name": name, "chunks": s.count})
        return repos
    except Exception:
        return []


def ingest_repo(github_url):
    """Run the full ingestion pipeline with progress updates."""
    from src.utils.language_detector import get_code_files, get_repo_stats
    from src.ingestion.parser import parse_python_file
    from src.ingestion.chunker import chunk_code_units

    progress = st.progress(0, text="Cloning repository...")

    # Clone
    repo_path = clone_repo(github_url)
    repo_name = repo_path.name
    progress.progress(15, text="Discovering code files...")

    # Discover
    code_files = get_code_files(str(repo_path))
    stats = get_repo_stats(code_files)
    python_files = [f for f in code_files if f.language == "python"]
    progress.progress(25, text=f"Parsing {len(python_files)} Python files...")

    # Parse
    all_units = []
    for i, f in enumerate(python_files):
        try:
            units = parse_python_file(f.abs_path, str(repo_path))
            all_units.extend(units)
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            pct = 25 + int(35 * (i + 1) / len(python_files))
            progress.progress(pct, text=f"Parsing {i + 1}/{len(python_files)} files...")

    progress.progress(60, text=f"Chunking {len(all_units)} code units...")

    # Chunk
    all_chunks = chunk_code_units(all_units)
    progress.progress(65, text=f"Embedding {len(all_chunks)} chunks (this takes a few minutes)...")

    # Embed and store
    store = CodeVectorStore(repo_name)
    batch_size = 50
    total = len(all_chunks)
    for i in range(0, total, batch_size):
        batch = all_chunks[i:i + batch_size]
        store.add_chunks(batch)
        pct = 65 + int(30 * min(i + batch_size, total) / total)
        progress.progress(pct, text=f"Embedding {min(i + batch_size, total)}/{total} chunks...")

    progress.progress(100, text="Done!")
    return repo_name, stats, len(all_chunks)


# ---- Sidebar ----
with st.sidebar:
    st.title("🔍 CodeLens")
    st.caption("Chat with any codebase")

    st.divider()

    # Ingest section
    st.subheader("Index a Repository")
    github_url = st.text_input(
        "GitHub URL",
        placeholder="https://github.com/owner/repo",
        label_visibility="collapsed",
    )
    ingest_btn = st.button("Index Repository", use_container_width=True)

    if ingest_btn and github_url:
        try:
            repo_name, stats, chunk_count = ingest_repo(github_url)
            st.success(f"Indexed **{repo_name}**: {chunk_count} chunks from {stats['total_files']} files")
        except Exception as e:
            st.error(f"Failed: {e}")

    st.divider()

    # Repo selection
    st.subheader("Select Repository")
    repos = get_indexed_repos()

    if not repos:
        st.info("No repositories indexed yet. Paste a GitHub URL above to get started.")
        selected_repo = None
    else:
        repo_options = {f"{r['name']} ({r['chunks']} chunks)": r['name'] for r in repos}
        selected_label = st.selectbox("Repository", options=list(repo_options.keys()), label_visibility="collapsed")
        selected_repo = repo_options[selected_label]

    st.divider()

    # Filters
    st.subheader("Search Filters")
    filter_type = st.selectbox(
        "Code type",
        options=["All", "function", "method", "class", "imports"],
        index=0,
    )
    filter_path = st.text_input(
        "File path contains",
        placeholder="e.g. routing, auth, models",
    )

    st.divider()
    st.caption("Built with LangChain, Ollama, ChromaDB, tree-sitter")


# ---- Main Chat Area ----
if not selected_repo:
    st.title("🔍 CodeLens")
    st.markdown("### Chat with any codebase")
    st.markdown(
        "Index a GitHub repository using the sidebar, then start asking questions about the code."
    )
    st.markdown("**Example questions:**")
    st.markdown(
        "- How does dependency injection work?\n"
        "- Where is the Request object defined?\n"
        "- What middleware is available?\n"
        "- Explain the main application class\n"
        "- How are routes registered?"
    )
else:
    # Two-column layout: chat on left, recommendations on right
    chat_col, rec_col = st.columns([3, 1])

    with rec_col:
        st.markdown("### 💡 Suggested Questions")

        # Generate FAQs based on repo contents
        faq_key = f"faqs_{selected_repo}"
        if faq_key not in st.session_state:
            with st.spinner("Scanning repo..."):
                try:
                    qa = CodeQAChain(selected_repo)
                    store = qa.store

                    # Sample some chunks to understand the repo
                    sample_results = store._collection.get(
                        limit=30,
                        include=["metadatas"],
                    )

                    # Gather file paths, class names, function names
                    files = set()
                    classes = set()
                    functions = set()
                    for meta in sample_results["metadatas"]:
                        files.add(meta.get("file_path", ""))
                        if meta.get("chunk_type") == "class":
                            classes.add(meta.get("name", ""))
                        if meta.get("chunk_type") == "function":
                            functions.add(meta.get("name", ""))
                        if meta.get("chunk_type") == "method" and meta.get("parent_class"):
                            classes.add(meta.get("parent_class", ""))

                    # Build smart FAQs based on what's actually in the repo
                    faqs = []

                    # Architecture question
                    faqs.append(f"What is the overall architecture of {selected_repo}?")

                    # Class-based questions
                    for cls in list(classes)[:3]:
                        if cls:
                            faqs.append(f"Explain the {cls} class and its purpose")

                    # Function-based questions
                    for func in list(functions)[:2]:
                        if func and not func.startswith("_"):
                            faqs.append(f"What does the {func} function do?")

                    # Directory-based questions
                    top_dirs = set()
                    for f in files:
                        parts = f.split("/")
                        if len(parts) > 1:
                            top_dirs.add(parts[0])

                    for d in list(top_dirs)[:2]:
                        if d:
                            faqs.append(f"What is the {d}/ directory responsible for?")

                    # Generic but useful questions
                    faqs.extend([
                        "What are the main entry points?",
                        "How is error handling done?",
                        "What external dependencies does this project use?",
                    ])

                    st.session_state[faq_key] = faqs[:10]

                except Exception as e:
                    st.session_state[faq_key] = [
                        f"What is the overall architecture of {selected_repo}?",
                        "What are the main classes and their purposes?",
                        "How is error handling done?",
                        "What are the main entry points?",
                        "What external dependencies are used?",
                    ]

        # Display FAQ buttons
        for faq in st.session_state[faq_key]:
            if st.button(faq, key=f"faq_{faq}", use_container_width=True):
                st.session_state["prefill_question"] = faq
                st.rerun()

    with chat_col:
        st.title(f"💬 {selected_repo}")

        # Initialize chat state
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "qa_chain" not in st.session_state or st.session_state.get("current_repo") != selected_repo:
            st.session_state.qa_chain = CodeQAChain(selected_repo)
            st.session_state.current_repo = selected_repo
            st.session_state.messages = []

        # Display chat history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    with st.expander(f"📄 Sources ({len(msg['sources'])} chunks)"):
                        for s in msg["sources"]:
                            st.markdown(
                                f'<div class="source-box">'
                                f'<strong>{s["file"]}</strong>:{s["lines"]} '
                                f'({s["type"]}: {s["name"]}) '
                                f'<em>score={s["score"]:.3f}</em></div>',
                                unsafe_allow_html=True,
                            )

        # Handle prefilled question from FAQ click
        prefill = st.session_state.pop("prefill_question", None)

        # Chat input
        prompt = st.chat_input("Ask about the codebase...")

        # Use prefill if no direct input
        active_question = prompt or prefill

        if active_question:
            # Show user message
            st.session_state.messages.append({"role": "user", "content": active_question})
            with st.chat_message("user"):
                st.markdown(active_question)

            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Searching codebase..."):
                    chunk_type = None if filter_type == "All" else filter_type
                    file_path = filter_path if filter_path else None

                    result = st.session_state.qa_chain.ask(
                        question=active_question,
                        chunk_type=chunk_type,
                        file_path_contains=file_path,
                    )

                st.markdown(result["answer"])

                if result["sources"]:
                    with st.expander(f"📄 Sources ({result['chunks_used']} chunks)"):
                        for s in result["sources"]:
                            st.markdown(
                                f'<div class="source-box">'
                                f'<strong>{s["file"]}</strong>:{s["lines"]} '
                                f'({s["type"]}: {s["name"]}) '
                                f'<em>score={s["score"]:.3f}</em></div>',
                                unsafe_allow_html=True,
                            )

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result["sources"],
            })