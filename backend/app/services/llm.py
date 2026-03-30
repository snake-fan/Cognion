import json
import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_URL
from .mineru import extract_pdf_context_for_qa
from .pdf_storage import extract_pdf_text

logger = logging.getLogger(__name__)


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


async def call_model_stream(prompt: str) -> AsyncGenerator[str, None]:
    if not OPENAI_API_KEY:
        fallback = (
            "[本地占位回复] 检测到未配置 OPENAI_API_KEY。"
            "你提交的问题和引用已成功到达后端。"
            "请在 backend/.env 中配置 OPENAI_API_KEY 后即可切换到真实大模型回答。\n\n"
            f"Prompt Preview:\n{prompt[:800]}"
        )
        yield fallback
        return

    client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_URL)
    stream = await client.chat.completions.create(
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
        stream=True,
    )

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = delta.content if delta else None
        if isinstance(text, str) and text:
            yield text


def _extract_json_block(raw_text: str) -> str:
    import re

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


async def answer_with_context(
    question: str,
    quote: str,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    local_pdf_path: str | None = None,
) -> str:
    prompt = await _build_qa_prompt(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
        local_pdf_path=local_pdf_path,
    )

    return await call_model(prompt)


async def answer_with_context_stream(
    question: str,
    quote: str,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    local_pdf_path: str | None = None,
) -> AsyncGenerator[str, None]:
    prompt = await _build_qa_prompt(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
        local_pdf_path=local_pdf_path,
    )

    async for token in call_model_stream(prompt):
        yield token


async def _build_qa_prompt(
    question: str,
    quote: str,
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    local_pdf_path: str | None,
) -> str:
    pdf_context = await extract_pdf_context_for_qa(
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
        local_pdf_path=local_pdf_path,
    )

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

    return prompt


def _normalize_topic_key(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized


def _build_session_messages_block(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = "用户" if message.get("role") == "user" else "助手"
        quote = (message.get("quote") or "").strip()
        content = (message.get("content") or "").strip()
        if quote:
            lines.append(f"[{role}引用]\n{quote}")
        if content:
            lines.append(f"[{role}]\n{content}")
    return "\n\n".join(lines).strip()


def _fallback_session_notes(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    seen: set[str] = set()
    for message in messages:
        if message.get("role") != "user":
            continue
        content = (message.get("content") or "").strip()
        if len(content) < 8:
            continue
        title_base = content.split("\n", 1)[0].strip()
        title = f"关键问题-{' '.join(title_base.split())[:18]}"
        topic_key = _normalize_topic_key(title)
        if not topic_key or topic_key in seen:
            continue
        seen.add(topic_key)
        notes.append(
            {
                "title": title,
                "content": f"## 讨论背景\n\n{content}\n\n## 当前理解\n\n该知识点来自当前 Session 对话提炼，建议结合论文原文继续验证。",
                "topic_key": topic_key,
            }
        )
        if len(notes) >= 3:
            break
    return notes


async def generate_notes_from_session(
    paper_title: str,
    paper_authors: str,
    paper_topic: str,
    session_messages: list[dict[str, str]],
    existing_topic_keys: list[str],
    max_points: int | None = None,
) -> list[dict[str, str]]:
    messages_block = _build_session_messages_block(session_messages)
    if not messages_block:
        return []

    existing_keys_text = "\n".join(f"- {key}" for key in existing_topic_keys if key.strip()) or "- （无）"
    max_points_line = str(max_points) if isinstance(max_points, int) and max_points > 0 else "自动"

    prompt = f"""
你是学术论文阅读助手。请根据同一篇论文的单个 Session 对话，产出知识点笔记。

[论文信息]
标题: {paper_title or '未知'}
作者: {paper_authors or '未知'}
研究主题: {paper_topic or '未知'}

[该 Session 既有知识点 topic_key（用于去重）]
{existing_keys_text}

[Session 对话记录]
{messages_block}

[任务要求]
1. 可以输出多条笔记，每条只讲一个知识点，一定要切合实际，不要瞎编，宁缺毋滥。
2. 标题必须是“术语+结论”风格，简洁明确。
3. 内容用 Markdown,包含：知识点定义、用户当前理解、证据与局限，一定要凸显用户的理解，而不只是大模型的回答。
4. 避免产出与既有 topic_key 重复或语义高度重复的知识点。
5. 生成条数: 不超过 {max_points_line}，如果没有满足要求的对话内容可以不生成。

[输出格式]
仅输出 JSON 对象，不要 markdown，不要额外解释：
{{
  "notes": [
    {{
      "title": "术语-结论",
      "content": "# ...",
      "topic_key": "term-conclusion"
    }}
  ]
}}
""".strip()

    raw_response = await call_model(prompt)
    parsed_notes: list[dict[str, str]] = []
    try:
        json_text = _extract_json_block(raw_response)
        payload = json.loads(json_text)
        raw_notes = payload.get("notes") if isinstance(payload, dict) else None
        if isinstance(raw_notes, list):
            for item in raw_notes:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                content = str(item.get("content") or "").strip()
                topic_key = str(item.get("topic_key") or "").strip() or _normalize_topic_key(title)
                if not title or not content:
                    continue
                parsed_notes.append(
                    {
                        "title": title,
                        "content": content,
                        "topic_key": _normalize_topic_key(topic_key) or _normalize_topic_key(title),
                    }
                )
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Failed to parse session note generation response as JSON")

    if not parsed_notes:
        parsed_notes = _fallback_session_notes(session_messages)

    return parsed_notes
