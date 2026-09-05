import logging
from typing import TypedDict

from app.services.embeddings import embed
from app.services.llm import chat
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
    query_embedding = embed([question])[0]
    store = store or get_store()
    searched_documents = store.search(query_embedding, top_k=3)
    logger.info(
        "rag_retrieval",
        extra={"extra_fields": {"question": question[:100], "doc_count": len(searched_documents)}},
    )
    prompt = build_prompt(question, documents=searched_documents)
    return await chat(prompt)
