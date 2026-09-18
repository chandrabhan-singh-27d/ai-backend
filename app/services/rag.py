import asyncio
import logging
from typing import TypedDict

from app.config import RAG_TOP_K
from app.services.embeddings import embed
from app.services.llm import chat
from app.services.tracing import get_tracer
from app.services.vector_store import VectorStore, get_store

logger = logging.getLogger("app.services.rag")


class Document(TypedDict):
    id: str
    text: str
    score: float


def build_prompt(question: str, documents: list[Document]) -> str:
    context = "\n\n".join(f"- {doc['text']}" for doc in documents)
    return f"""Answer the question based on the context below.
If the context doesn't contain the answer, say "I don't have enough information."

Context: 
{context}

Question: {question}"""


async def answer_question(question: str, store: VectorStore | None = None) -> str:
    tracer = get_tracer()
    with tracer.start_as_current_span("answer_question"):
        with tracer.start_as_current_span("embedding"):
            query_embedding = (await embed([question]))[0]
        store = store or get_store()

        with tracer.start_as_current_span("store.search"):
            searched_documents = await asyncio.to_thread(
                store.search, query_embedding, RAG_TOP_K
            )

        logger.info(
            "rag_retrieval",
            extra={
                "extra_fields": {"question": question[:100], "doc_count": len(searched_documents)}
            },
        )

        with tracer.start_as_current_span("build_prompt"):
            prompt = build_prompt(question, documents=searched_documents)

        answer, _ = await chat(prompt)
        return answer
