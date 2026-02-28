"""RAG chain connecting retriever to Ollama LLM."""

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.config import settings
from src.retrieval.vector_store import CodeVectorStore
from src.generation.prompts import SYSTEM_PROMPT, CONTEXT_CHUNK_TEMPLATE


class CodeQAChain:
    """RAG chain for answering questions about a codebase."""

    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.store = CodeVectorStore(repo_name)
        self.llm = ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=settings.temperature,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "## Retrieved Code Context\n\n{context}\n\n## Question\n\n{question}"),
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()
        self.history = []

    def ask(self, question: str, top_k: int = 0, language: str = None,
            file_path_contains: str = None, chunk_type: str = None) -> dict:
        """Ask a question about the codebase.

        Returns dict with: answer, sources, chunks_used
        """
        top_k = top_k or settings.retrieval_top_k

        # Retrieve relevant chunks
        results = self.store.search(
            query=question,
            top_k=top_k,
            language=language,
            file_path_contains=file_path_contains,
            chunk_type=chunk_type,
        )

        if not results:
            return {
                "answer": "No relevant code found in the indexed repository for this question.",
                "sources": [],
                "chunks_used": 0,
            }

        # Format context from retrieved chunks
        context = self._format_context(results)

        # Generate answer
        answer = self.chain.invoke({
            "context": context,
            "question": question,
        })

        # Extract source references
        sources = []
        for r in results:
            m = r["metadata"]
            sources.append({
                "file": m.get("file_path", "unknown"),
                "lines": f"{m.get('start_line', '?')}-{m.get('end_line', '?')}",
                "type": m.get("chunk_type", "unknown"),
                "name": m.get("name", "unknown"),
                "score": r.get("score", 0),
            })

        # Store in history for multi-turn
        self.history.append({"question": question, "answer": answer})

        return {
            "answer": answer,
            "sources": sources,
            "chunks_used": len(results),
        }

    def _format_context(self, results: list[dict]) -> str:
        """Format retrieved chunks into context string for the LLM."""
        formatted = []
        for r in results:
            m = r["metadata"]
            chunk_text = CONTEXT_CHUNK_TEMPLATE.format(
                file_path=m.get("file_path", "unknown"),
                start_line=m.get("start_line", "?"),
                end_line=m.get("end_line", "?"),
                code_type=m.get("chunk_type", "unknown"),
                name=m.get("name", "unknown"),
                language=m.get("language", "python"),
                code=r["content"],
            )
            formatted.append(chunk_text)
        return "\n\n".join(formatted)


if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    repo = sys.argv[1] if len(sys.argv) > 1 else "fastapi"
    question = sys.argv[2] if len(sys.argv) > 2 else "How does FastAPI handle routing?"

    console.print(f"\n[bold]Querying {repo}: {question}[/bold]\n")

    qa = CodeQAChain(repo)
    result = qa.ask(question)

    console.print(Markdown(result["answer"]))
    console.print(f"\n[dim]Sources ({result['chunks_used']} chunks used):[/dim]")
    for s in result["sources"]:
        console.print(f"  [cyan]{s['file']}[/cyan]:{s['lines']} ({s['type']}: {s['name']}) [dim]score={s['score']:.3f}[/dim]")