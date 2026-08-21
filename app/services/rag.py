from typing import TypedDict

from app.services.embeddings import embed
from app.services.llm import chat
from app.services.vector_store import search


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


async def answer_question(question: str) -> str:
    query_embedding = embed([question])[0]
    searched_documents = search(query_embedding, top_k=3)
    prompt = build_prompt(question, documents=searched_documents)
    return await chat(prompt)
