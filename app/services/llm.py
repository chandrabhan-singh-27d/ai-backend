import os

from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")


async def chat(message: str) -> str:
    response = await client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content or ""
