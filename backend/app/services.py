import os
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4
from io import BytesIO

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pypdf import PdfReader

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1")
PDF_STORAGE_DIR = os.getenv("PDF_STORAGE_DIR", str(Path(__file__).resolve().parents[1] / "storage" / "papers"))



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


def _extract_json_block(raw_text: str) -> str:
    fenced_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw_text)
    if fenced_match:
        return fenced_match.group(1)

    brace_match = re.search(r"(\{[\s\S]*\})", raw_text)
    if brace_match:
        return brace_match.group(1)

    return raw_text


def _fallback_metadata(pdf_filename: str | None) -> dict[str, str]:
    display_title = Path(pdf_filename or "未命名论文").stem
    return {
        "title": display_title or "未命名论文",
        "authors": "未知",
        "research_topic": "未标注",
        "journal": "未知",
        "publication_date": "未知",
        "summary": "",
    }


async def extract_paper_metadata(pdf_bytes: bytes, pdf_filename: str | None) -> dict[str, str]:
    pdf_context = extract_pdf_text(pdf_bytes, max_chars=14000)

    if not OPENAI_API_KEY:
        return _fallback_metadata(pdf_filename)

    prompt = f"""
请从下面论文内容中抽取结构化元信息，并且只返回 JSON 对象。

JSON 字段必须包含：
- title
- authors
- research_topic
- journal
- publication_date
- summary

要求：
1. 不要返回 markdown，不要返回解释，只能返回 JSON。
2. 如果无法确定字段，使用“未知”或“未标注”。
3. `summary` 控制在 120 字以内。

[论文文件名]
{pdf_filename or '未知'}

[论文上下文节选]
{pdf_context or '无可用内容'}
""".strip()

    raw_response = await call_model(prompt)

    try:
        json_text = _extract_json_block(raw_response)
        parsed = json.loads(json_text)
        return {
            "title": str(parsed.get("title") or "未命名论文"),
            "authors": str(parsed.get("authors") or "未知"),
            "research_topic": str(parsed.get("research_topic") or "未标注"),
            "journal": str(parsed.get("journal") or "未知"),
            "publication_date": str(parsed.get("publication_date") or "未知"),
            "summary": str(parsed.get("summary") or ""),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return _fallback_metadata(pdf_filename)


def _safe_segment(name: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return sanitized or "untitled"


def persist_uploaded_pdf(
    pdf_bytes: bytes,
    original_filename: str | None,
    folder_segments: list[str] | None = None,
) -> str:
    storage_dir = Path(PDF_STORAGE_DIR)
    if folder_segments:
        for segment in folder_segments:
            storage_dir = storage_dir / _safe_segment(segment)
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(original_filename or "paper.pdf").name
    extension = Path(safe_name).suffix.lower() or ".pdf"
    stored_name = f"{uuid4().hex}{extension}"
    target_path = storage_dir / stored_name
    target_path.write_bytes(pdf_bytes)
    return str(target_path.resolve())


def move_pdf_file_to_segments(existing_file_path: str, folder_segments: list[str] | None = None) -> str:
    source_path = Path(existing_file_path)
    if not source_path.exists():
        return existing_file_path

    target_dir = Path(PDF_STORAGE_DIR)
    if folder_segments:
        for segment in folder_segments:
            target_dir = target_dir / _safe_segment(segment)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    shutil.move(str(source_path), str(target_path))
    return str(target_path.resolve())


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
