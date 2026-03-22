import os
from io import BytesIO

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pypdf import PdfReader

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1")



def extract_pdf_text(pdf_bytes: bytes | None, max_chars: int = 12000) -> str:
    if not pdf_bytes:
        return ""

    reader = PdfReader(BytesIO(pdf_bytes))
    pages_text: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            pages_text.append(text.strip())
        if sum(len(chunk) for chunk in pages_text) >= max_chars:
            break

    all_text = "\n\n".join(pages_text)
    return all_text[:max_chars]


async def call_model(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return (
            "[本地占位回复] 检测到未配置 OPENAI_API_KEY。"
            "你提交的问题和引用已成功到达后端。"
            "请在 backend/.env 中配置 OPENAI_API_KEY 后即可切换到真实大模型回答。\n\n"
            f"Prompt Preview:\n{prompt[:800]}"
        )

    client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_URL)
    completion = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "你是一个学术论文阅读助手。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    if completion.choices and completion.choices[0].message:
        return completion.choices[0].message.content or ""

    return "模型未返回可解析内容。"


async def answer_with_context(
    question: str,
    quote: str,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
) -> str:
    pdf_context = extract_pdf_text(pdf_bytes)

    prompt = f"""
你是一个学术论文阅读助手，请基于用户问题、引用片段和论文上下文作答。

[用户问题]
{question}

[用户引用片段]
{quote or '（用户未提供引用）'}

[论文文件]
{pdf_filename or '（未上传）'}

[论文上下文（节选）]
{pdf_context or '（无可用内容）'}

要求：
1. 先直接回答问题。
2. 明确指出回答与引用片段的关系。
3. 如果信息不足，明确说明还缺少什么。
""".strip()

    return await call_model(prompt)
