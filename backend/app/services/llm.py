import json
import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_URL
from .mineru import extract_pdf_context_for_qa
from .pdf_storage import extract_pdf_text
from .templates import (
    build_metadata_system_template,
    build_metadata_user_template,
    build_qa_system_template,
    build_qa_user_template,
    build_session_notes_system_template,
    build_session_notes_user_template,
)

logger = logging.getLogger(__name__)


async def call_model(prompt: str, system_prompt: str) -> str:
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
                "content": system_prompt,
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


async def call_model_stream(prompt: str, system_prompt: str) -> AsyncGenerator[str, None]:
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
                "content": system_prompt,
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

    prompt = build_metadata_user_template(pdf_filename=pdf_filename, pdf_context=pdf_context)

    raw_response = await call_model(prompt, system_prompt=build_metadata_system_template())

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

    return await call_model(prompt, system_prompt=build_qa_system_template())


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

    async for token in call_model_stream(prompt, system_prompt=build_qa_system_template()):
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

    prompt = build_qa_user_template(
        question=question,
        quote=quote,
        pdf_filename=pdf_filename,
        pdf_context=pdf_context,
    )

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


VALID_UNIT_TYPES = {"concept", "claim", "method", "question", "distinction"}
VALID_FACET_TYPES = {"definition", "mechanism", "limitation", "comparison", "implication", "question"}
VALID_USER_STATES = {"mentioned", "exposed", "confused", "partial_understanding", "understood", "misaligned"}
VALID_SIGNAL_TYPES = {"understanding", "question", "confusion", "misconception", "distinction", "boundary_awareness"}
VALID_NODE_TYPES = {"Concept", "Claim", "Method", "Question"}
VALID_EDGE_RELATIONS = {"RELATED_TO", "EXPLAINS", "CONTRASTS_WITH", "PREREQUISITE_OF", "RAISES", "SUPPORTS"}
UNDIRECTED_EDGE_RELATIONS = {"RELATED_TO", "CONTRASTS_WITH"}


def _to_clean_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_edge_name(value: object) -> str:
    normalized = re.sub(r"\s+", " ", _to_clean_text(value).lower())
    return normalized


def _to_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    results: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _to_clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        results.append(text)
    return results


def _to_confidence(value: object, default: float = 0.5) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = default
    return max(0.0, min(1.0, confidence))


def _shorten_line(value: str, limit: int = 28) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact[:limit] if len(compact) > limit else compact


def _build_note_title(term: str, summary: str, fallback: str) -> str:
    base_term = _shorten_line(term or fallback or "关键问题", limit=18) or "关键问题"
    base_focus = _shorten_line(summary or fallback or "认知边界", limit=22) or "认知边界"
    title = f"{base_term}-{base_focus}"
    return title[:80]


def _normalize_facets(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    facets: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        facet_type = _to_clean_text(item.get("facet_type"))
        text = _to_clean_text(item.get("text"))
        if not text:
            continue
        if facet_type not in VALID_FACET_TYPES:
            facet_type = "question" if "?" in text or "？" in text else "definition"
        facets.append({"facet_type": facet_type, "text": text})
    return facets


def _normalize_user_signals(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    signals: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        signal_type = _to_clean_text(item.get("signal_type"))
        text = _to_clean_text(item.get("text"))
        if not text:
            continue
        if signal_type not in VALID_SIGNAL_TYPES:
            signal_type = "question" if "?" in text or "？" in text else "understanding"
        signals.append({"signal_type": signal_type, "text": text})
    return signals


def _normalize_evidence(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    evidence_items: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source = _to_clean_text(item.get("source"))
        quote = _to_clean_text(item.get("quote"))
        if not quote:
            continue
        evidence_items.append({"source": "user" if source == "user" else "assistant", "quote": quote})
    return evidence_items


def _normalize_graph_suggestions(value: object) -> dict[str, list[dict[str, str]]]:
    if not isinstance(value, dict):
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, str]] = []
    seen_node_keys: set[str] = set()
    raw_nodes = value.get("nodes")
    if isinstance(raw_nodes, list):
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            node_type = _to_clean_text(item.get("node_type"))
            name = _to_clean_text(item.get("name"))
            if not name:
                continue
            if node_type not in VALID_NODE_TYPES:
                node_type = "Question" if "?" in name or "？" in name else "Concept"
            node_key = f"{node_type}:{_normalize_edge_name(name)}"
            if node_key in seen_node_keys:
                continue
            seen_node_keys.add(node_key)
            nodes.append({"node_type": node_type, "name": name})

    edges: list[dict[str, str]] = []
    seen_edge_keys: set[str] = set()
    raw_edges = value.get("edges")
    if isinstance(raw_edges, list):
        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            from_name = _to_clean_text(item.get("from"))
            relation = _to_clean_text(item.get("relation"))
            to_name = _to_clean_text(item.get("to"))
            if not from_name or not to_name:
                continue
            if relation not in VALID_EDGE_RELATIONS:
                relation = "RELATED_TO"
            if relation in UNDIRECTED_EDGE_RELATIONS:
                left_name, right_name = sorted([from_name, to_name], key=_normalize_edge_name)
            else:
                left_name, right_name = from_name, to_name
            edge_key = f"{relation}:{_normalize_edge_name(left_name)}:{_normalize_edge_name(right_name)}"
            if edge_key in seen_edge_keys:
                continue
            seen_edge_keys.add(edge_key)
            edges.append({"from": left_name, "relation": relation, "to": right_name})

    return {"nodes": nodes, "edges": edges}


def _normalize_dedupe_hints(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {"aliases": [], "semantic_fingerprint": []}
    return {
        "aliases": _to_string_list(value.get("aliases")),
        "semantic_fingerprint": _to_string_list(value.get("semantic_fingerprint"))[:6],
    }


def _render_structured_note_markdown(note: dict[str, object]) -> str:
    title = _to_clean_text(note.get("title")) or "未命名笔记"
    summary = _to_clean_text(note.get("summary"))
    knowledge_unit = note.get("knowledge_unit") if isinstance(note.get("knowledge_unit"), dict) else {}
    user_model_signal = note.get("user_model_signal") if isinstance(note.get("user_model_signal"), dict) else {}
    evidence = note.get("evidence") if isinstance(note.get("evidence"), list) else []
    open_questions = note.get("open_questions") if isinstance(note.get("open_questions"), list) else []

    facet_labels = {
        "definition": "定义",
        "mechanism": "机制",
        "limitation": "局限",
        "comparison": "比较",
        "implication": "启发",
        "question": "问题",
    }
    state_labels = {
        "mentioned": "仅提及",
        "exposed": "已接触",
        "confused": "存在困惑",
        "partial_understanding": "部分理解",
        "understood": "基本理解",
        "misaligned": "理解偏差",
    }
    signal_labels = {
        "understanding": "理解",
        "question": "提问",
        "confusion": "困惑",
        "misconception": "误解",
        "distinction": "区分尝试",
        "boundary_awareness": "边界意识",
    }
    source_labels = {"user": "用户", "assistant": "助手"}

    lines = [f"# {title}", ""]
    if summary:
        lines.extend(["## 核心摘要", "", summary, ""])

    unit_type = _to_clean_text(knowledge_unit.get("unit_type"))
    term = _to_clean_text(knowledge_unit.get("term"))
    core_claim = _to_clean_text(knowledge_unit.get("core_claim"))
    if unit_type or term or core_claim:
        lines.extend(["## 知识单元", ""])
        if unit_type:
            lines.append(f"- 类型：{unit_type}")
        if term:
            lines.append(f"- 核心术语：{term}")
        if core_claim:
            lines.append(f"- 核心命题：{core_claim}")
        related_terms = _to_string_list(knowledge_unit.get("related_terms"))
        if related_terms:
            lines.append(f"- 相关术语：{' / '.join(related_terms)}")
        lines.append("")

    facets = _normalize_facets(knowledge_unit.get("facets"))
    if facets:
        lines.extend(["## 关键面向", ""])
        for facet in facets:
            label = facet_labels.get(facet["facet_type"], facet["facet_type"])
            lines.append(f"- {label}：{facet['text']}")
        lines.append("")

    state = _to_clean_text(user_model_signal.get("state"))
    confidence = _to_confidence(user_model_signal.get("confidence"), default=0.5)
    signals = _normalize_user_signals(user_model_signal.get("signals"))
    if state or signals:
        lines.extend(["## 用户当前状态", ""])
        if state:
            lines.append(f"- 状态：{state_labels.get(state, state)}")
        lines.append(f"- 判断信心：{confidence:.2f}")
        for signal in signals:
            label = signal_labels.get(signal["signal_type"], signal["signal_type"])
            lines.append(f"- {label}：{signal['text']}")
        lines.append("")

    normalized_evidence = _normalize_evidence(evidence)
    if normalized_evidence:
        lines.extend(["## 关键证据", ""])
        for item in normalized_evidence:
            lines.append(f"- {source_labels.get(item['source'], item['source'])}：{item['quote']}")
        lines.append("")

    normalized_open_questions = _to_string_list(open_questions)
    if normalized_open_questions:
        lines.extend(["## 待追踪问题", ""])
        for question in normalized_open_questions:
            lines.append(f"- {question}")
        lines.append("")

    return "\n".join(lines).strip()


def _normalize_note_payload(item: dict[str, object], index: int) -> dict[str, object] | None:
    raw_summary = _to_clean_text(item.get("summary"))
    raw_knowledge_unit = item.get("knowledge_unit") if isinstance(item.get("knowledge_unit"), dict) else {}
    raw_user_model_signal = item.get("user_model_signal") if isinstance(item.get("user_model_signal"), dict) else {}

    term = _to_clean_text(raw_knowledge_unit.get("term"))
    core_claim = _to_clean_text(raw_knowledge_unit.get("core_claim"))
    fallback_text = raw_summary or core_claim or term
    title = _to_clean_text(item.get("title")) or _build_note_title(term, raw_summary, fallback_text)
    topic_key = _normalize_topic_key(_to_clean_text(item.get("topic_key")) or title)
    if not title or not topic_key:
        return None

    unit_type = _to_clean_text(raw_knowledge_unit.get("unit_type"))
    if unit_type not in VALID_UNIT_TYPES:
        unit_type = "question" if "?" in fallback_text or "？" in fallback_text else "concept"

    summary = raw_summary or core_claim or f"用户在本次 Session 中围绕“{term or title}”暴露出值得跟踪的认知状态。"

    state = _to_clean_text(raw_user_model_signal.get("state"))
    if state not in VALID_USER_STATES:
        state = "confused" if unit_type == "question" else "mentioned"

    normalized_note = {
        "note_id": _to_clean_text(item.get("note_id")) or f"temp_{index:03d}",
        "title": title,
        "topic_key": topic_key,
        "summary": summary,
        "knowledge_unit": {
            "unit_type": unit_type,
            "term": term or title,
            "core_claim": core_claim or summary,
            "facets": _normalize_facets(raw_knowledge_unit.get("facets")),
            "related_terms": _to_string_list(raw_knowledge_unit.get("related_terms")),
        },
        "user_model_signal": {
            "state": state,
            "confidence": _to_confidence(raw_user_model_signal.get("confidence"), default=0.65 if state != "mentioned" else 0.5),
            "signals": _normalize_user_signals(raw_user_model_signal.get("signals")),
        },
        "evidence": _normalize_evidence(item.get("evidence")),
        "graph_suggestions": _normalize_graph_suggestions(item.get("graph_suggestions")),
        "open_questions": _to_string_list(item.get("open_questions")),
        "dedupe_hints": _normalize_dedupe_hints(item.get("dedupe_hints")),
    }
    normalized_note["content"] = _render_structured_note_markdown(normalized_note)
    return normalized_note


def _fallback_session_notes(messages: list[dict[str, str]]) -> list[dict[str, object]]:
    notes: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, message in enumerate(messages, start=1):
        if message.get("role") != "user":
            continue
        content = (message.get("content") or "").strip()
        if len(content) < 8:
            continue
        title_base = content.split("\n", 1)[0].strip()
        summary = f"用户在本次 Session 中明确提出了关于“{_shorten_line(title_base, 16) or '当前问题'}”的疑问，这反映出当前认知边界仍待澄清。"
        title = _build_note_title("关键问题", summary, title_base)
        topic_key = _normalize_topic_key(title)
        if not topic_key or topic_key in seen:
            continue
        seen.add(topic_key)
        note = _normalize_note_payload(
            {
                "note_id": f"temp_{index:03d}",
                "title": title,
                "topic_key": topic_key,
                "summary": summary,
                "knowledge_unit": {
                    "unit_type": "question",
                    "term": _shorten_line(title_base, 24) or "关键问题",
                    "core_claim": "用户提出了一个仍待澄清的问题，尚未形成稳定理解。",
                    "facets": [
                        {
                            "facet_type": "question",
                            "text": content,
                        }
                    ],
                    "related_terms": [],
                },
                "user_model_signal": {
                    "state": "confused",
                    "confidence": 0.72,
                    "signals": [
                        {
                            "signal_type": "question",
                            "text": "用户主动提问，说明这一点仍处于待理解状态。",
                        }
                    ],
                },
                "evidence": [{"source": "user", "quote": content}],
                "graph_suggestions": {
                    "nodes": [{"node_type": "Question", "name": _shorten_line(title_base, 24) or "关键问题"}],
                    "edges": [],
                },
                "open_questions": [content],
                "dedupe_hints": {
                    "aliases": [],
                    "semantic_fingerprint": _to_string_list([title_base, "user-question", "session-derived"])[:3],
                },
            },
            index=len(notes) + 1,
        )
        if note:
            notes.append(note)
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
) -> list[dict[str, object]]:
    messages_block = _build_session_messages_block(session_messages)
    if not messages_block:
        return []

    existing_keys_text = "\n".join(f"- {key}" for key in existing_topic_keys if key.strip()) or "- （无）"
    max_points_line = str(max_points) if isinstance(max_points, int) and max_points > 0 else "3"

    prompt = build_session_notes_user_template(
        paper_title=paper_title,
        paper_authors=paper_authors,
        paper_topic=paper_topic,
        existing_keys_text=existing_keys_text,
        messages_block=messages_block,
        max_points_line=max_points_line,
    )

    raw_response = await call_model(prompt, system_prompt=build_session_notes_system_template())
    parsed_notes: list[dict[str, object]] = []
    try:
        json_text = _extract_json_block(raw_response)
        payload = json.loads(json_text)
        raw_notes = payload.get("notes") if isinstance(payload, dict) else None
        if isinstance(raw_notes, list):
            for index, item in enumerate(raw_notes, start=1):
                if not isinstance(item, dict):
                    continue
                normalized = _normalize_note_payload(item, index=index)
                if normalized:
                    parsed_notes.append(normalized)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Failed to parse session note generation response as JSON")

    if not parsed_notes:
        parsed_notes = _fallback_session_notes(session_messages)

    if isinstance(max_points, int) and max_points > 0:
        parsed_notes = parsed_notes[:max_points]

    return parsed_notes
