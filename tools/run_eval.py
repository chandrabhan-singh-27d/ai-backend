import asyncio
import json
import os
import sys
from pathlib import Path
from statistics import mean
from typing import TypedDict, cast

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.services.embeddings import embed
from app.services.rag import answer_question
from app.services.vector_store import add, search

load_dotenv()

TOOLS_DIR = Path(__file__).parent
JUDGE_MODEL = "qwen/qwen3.6-27b"

judge_client = AsyncOpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)


class CorpusDoc(TypedDict):
    id: str
    text: str


class EvalCase(TypedDict):
    id: str
    question: str
    answerable: bool
    expected_doc_ids: list[str]
    expected_facts: list[str]


class JudgeVerdict(BaseModel):
    score: int = Field(ge=1, le=5)
    reasoning: str


class CaseResult(BaseModel):
    case_id: str
    retrieval_pass: bool
    retrieved_ids: list[str]
    answer: str
    verdict: JudgeVerdict


def seed_store() -> None:
    corpus: list[CorpusDoc] = json.loads((TOOLS_DIR / "corpus.json").read_text())
    embeddings = embed([doc["text"] for doc in corpus])
    for doc, emb in zip(corpus, embeddings, strict=True):
        add(doc_id=doc["id"], text=doc["text"], embedding=emb)


def parse_verdict(content: str) -> JudgeVerdict:
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    start = content.find("{")
    data: object = json.JSONDecoder().raw_decode(content[start:])[0]
    if isinstance(data, list):
        items = cast("list[object]", data)
        for item in items:
            if isinstance(item, dict):
                return JudgeVerdict.model_validate(item)
        raise ValueError("judge returned an array without any verdict object")
    return JudgeVerdict.model_validate(data)


async def judge_answer(
    question: str,
    context: str,
    case: EvalCase,
    answer: str,
) -> JudgeVerdict:
    if case["answerable"]:
        task = (
            "You are grading a RAG pipeline's ANSWER.\n"
            "Grade how well the answer conveys the EXPECTED FACTS, using only "
            "the CONTEXT as ground truth.\n"
            "Rubric:\n"
            "5 = fully supported by context and conveys every expected fact\n"
            "4 = supported by context, minor omission or imprecision\n"
            "3 = partially correct or vague, some support in context\n"
            "2 = mostly unsupported by context or misses key facts\n"
            "1 = contradicts the context or fabricates information\n"
            "EXPECTED FACTS (each should be conveyed, any phrasing):\n"
            + "\n".join(f"- {fact}" for fact in case["expected_facts"])
        )
    else:
        task = (
            "You are grading a RAG pipeline's ANSWER to a question that CANNOT "
            "be answered from the CONTEXT.\n"
            "Correct behavior is to decline and say it lacks the information.\n"
            "Rubric:\n"
            "5 = clearly declines, states the context lacks the answer\n"
            "4 = declines but with excessive hedging or irrelevant filler\n"
            "3 = hedges while still speculating partially\n"
            "2 = mostly fabricated answer\n"
            "1 = confidently answers with invented specifics\n"
        )

    prompt = (
        f"{task}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER: {answer}\n\n"
        "You may reason step by step first, but your reply must END with a "
        'single JSON object (not an array) with key "score" (an integer from 1 '
        'to 5) and key "reasoning" (one short sentence). '
        'Example: {"score": 4, "reasoning": "Supported by context but omitted one detail."}'
    )

    response = await judge_client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    content = response.choices[0].message.content or "{}"
    return parse_verdict(content)


async def run_case(case: EvalCase) -> CaseResult:
    query_embedding = embed([case["question"]])[0]
    retrieved = search(query_embedding, top_k=3)
    retrieved_ids = [r["id"] for r in retrieved]

    retrieval_pass = all(
        doc_id in retrieved_ids for doc_id in case["expected_doc_ids"]
    )

    context = "\n\n".join(r["text"] for r in retrieved)
    answer = await answer_question(case["question"])
    verdict = await judge_answer(case["question"], context, case, answer)

    return CaseResult(
        case_id=case["id"],
        retrieval_pass=retrieval_pass,
        retrieved_ids=retrieved_ids,
        answer=answer,
        verdict=verdict,
    )


def print_report(results: list[CaseResult]) -> bool:
    print("=" * 78)
    print("RAG EVAL REPORT")
    print("=" * 78)

    for result in results:
        retr = "ok" if result.retrieval_pass else "MISS"
        print(f"\n{result.case_id}  [retrieval:{retr}]  [judge:{result.verdict.score}/5]")
        print(f"  retrieved : {', '.join(result.retrieved_ids)}")
        print(f"  reasoning : {result.verdict.reasoning}")
        preview = result.answer[:150].replace("\n", " ")
        print(f"  answer    : {preview}{'...' if len(result.answer) > 150 else ''}")

    scores = [r.verdict.score for r in results]
    avg_score = mean(scores)
    all_retrieval = all(r.retrieval_pass for r in results)
    no_hard_fail = min(scores) >= 3
    suite_pass = all_retrieval and no_hard_fail and avg_score >= 4.0

    print("\n" + "=" * 78)
    print(f"cases          : {len(results)}")
    print(f"retrieval hits : {sum(r.retrieval_pass for r in results)}/{len(results)}")
    print(f"avg score      : {avg_score:.2f} / 5.00")
    print(f"min score      : {min(scores)}/5")
    print(f"suite verdict  : {'PASS' if suite_pass else 'FAIL'}")
    print("=" * 78)

    return suite_pass


async def main() -> None:
    seed_store()
    cases: list[EvalCase] = json.loads((TOOLS_DIR / "eval_cases.json").read_text())

    results: list[CaseResult] = []
    for case in cases:
        print(f"running {case['id']}...", flush=True)
        results.append(await run_case(case))

    passed = print_report(results)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
