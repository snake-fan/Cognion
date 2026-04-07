from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .schemas import (
    DedupeHints,
    EvidenceItem,
    FacetType,
    GraphEdgeRelation,
    GraphNodeType,
    GraphSuggestions,
    KnowledgeFacet,
    KnowledgeUnit,
    PaperMetadata,
    ParseError,
    ParseResult,
    SessionNote,
    SessionNotesPayload,
    UserModelSignal,
    UserSignal,
    UserSignalType,
    UserState,
    UnitType,
)

UNDIRECTED_EDGE_RELATIONS = {
    GraphEdgeRelation.RELATED_TO.value,
    GraphEdgeRelation.CONTRASTS_WITH.value,
}


def extract_fenced_json(raw_text: str) -> str | None:
    fenced_match = re.search(r"```json\s*([\[{][\s\S]*?[\]}])\s*```", raw_text)
    if fenced_match:
        return fenced_match.group(1)
    return None


def extract_bare_json(raw_text: str) -> str | None:
    start_candidates = [index for index in (raw_text.find("{"), raw_text.find("[")) if index >= 0]
    if not start_candidates:
        return None

    start = min(start_candidates)
    stack: list[str] = []
    in_string = False
    escape = False
    for index in range(start, len(raw_text)):
        char = raw_text[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "[{":
            stack.append(char)
        elif char in "]}":
            if not stack:
                continue
            opening = stack.pop()
            if (opening, char) not in {("{", "}"), ("[", "]")}:
                return None
            if not stack:
                return raw_text[start : index + 1]

    return None


def extract_json_text(raw_text: str) -> str:
    return extract_fenced_json(raw_text) or extract_bare_json(raw_text) or raw_text


def deserialize_json(json_text: str) -> ParseResult:
    try:
        return ParseResult(ok=True, data=json.loads(json_text), extracted_text=json_text)
    except json.JSONDecodeError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="json_decode_error", message=str(exc)),
        )


def _to_clean_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_topic_key(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized


def _to_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _to_clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _to_confidence(value: object, default: float = 0.5) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = default
    return max(0.0, min(1.0, confidence))


def _normalize_unit_type(value: str, fallback_text: str) -> UnitType:
    if value in {item.value for item in UnitType}:
        return UnitType(value)
    if "?" in fallback_text or "？" in fallback_text:
        return UnitType.QUESTION
    return UnitType.CONCEPT


def _normalize_facet_type(value: str, text: str) -> FacetType:
    if value in {item.value for item in FacetType}:
        return FacetType(value)
    if "?" in text or "？" in text:
        return FacetType.QUESTION
    return FacetType.DEFINITION


def _normalize_signal_type(value: str, text: str) -> UserSignalType:
    if value in {item.value for item in UserSignalType}:
        return UserSignalType(value)
    if "?" in text or "？" in text:
        return UserSignalType.QUESTION
    return UserSignalType.UNDERSTANDING


def _normalize_state(value: str, unit_type: UnitType) -> UserState:
    if value in {item.value for item in UserState}:
        return UserState(value)
    if unit_type == UnitType.QUESTION:
        return UserState.CONFUSED
    return UserState.MENTIONED


def _normalize_graph_suggestions(value: object) -> GraphSuggestions:
    if not isinstance(value, dict):
        return GraphSuggestions()

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
            if node_type not in {item.value for item in GraphNodeType}:
                node_type = GraphNodeType.QUESTION.value if ("?" in name or "？" in name) else GraphNodeType.CONCEPT.value
            node_key = f"{node_type}:{name.lower()}"
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
            if relation not in {item.value for item in GraphEdgeRelation}:
                relation = GraphEdgeRelation.RELATED_TO.value

            if relation in UNDIRECTED_EDGE_RELATIONS:
                left_name, right_name = sorted([from_name, to_name], key=lambda x: x.lower())
            else:
                left_name, right_name = from_name, to_name

            edge_key = f"{relation}:{left_name.lower()}:{right_name.lower()}"
            if edge_key in seen_edge_keys:
                continue
            seen_edge_keys.add(edge_key)
            edges.append({"from": left_name, "relation": relation, "to": right_name})

    return GraphSuggestions.model_validate({"nodes": nodes, "edges": edges})


def render_structured_note_markdown(note: SessionNote) -> str:
    facet_labels = {
        FacetType.DEFINITION.value: "定义",
        FacetType.MECHANISM.value: "机制",
        FacetType.LIMITATION.value: "局限",
        FacetType.COMPARISON.value: "比较",
        FacetType.IMPLICATION.value: "启发",
        FacetType.QUESTION.value: "问题",
    }
    state_labels = {
        UserState.MENTIONED.value: "仅提及",
        UserState.EXPOSED.value: "已接触",
        UserState.CONFUSED.value: "存在困惑",
        UserState.PARTIAL_UNDERSTANDING.value: "部分理解",
        UserState.UNDERSTOOD.value: "基本理解",
        UserState.MISALIGNED.value: "理解偏差",
    }
    signal_labels = {
        UserSignalType.UNDERSTANDING.value: "理解",
        UserSignalType.QUESTION.value: "提问",
        UserSignalType.CONFUSION.value: "困惑",
        UserSignalType.MISCONCEPTION.value: "误解",
        UserSignalType.DISTINCTION.value: "区分尝试",
        UserSignalType.BOUNDARY_AWARENESS.value: "边界意识",
    }
    source_labels = {"user": "用户", "assistant": "助手"}

    lines = [f"# {note.title}", ""]
    if note.summary:
        lines.extend(["## 核心摘要", "", note.summary, ""])

    lines.extend(["## 知识单元", ""])
    lines.append(f"- 类型：{note.knowledge_unit.unit_type.value}")
    lines.append(f"- 核心术语：{note.knowledge_unit.term}")
    lines.append(f"- 核心命题：{note.knowledge_unit.core_claim}")
    if note.knowledge_unit.related_terms:
        lines.append(f"- 相关术语：{' / '.join(note.knowledge_unit.related_terms)}")
    lines.append("")

    if note.knowledge_unit.facets:
        lines.extend(["## 关键面向", ""])
        for facet in note.knowledge_unit.facets:
            label = facet_labels.get(facet.facet_type.value, facet.facet_type.value)
            lines.append(f"- {label}：{facet.text}")
        lines.append("")

    lines.extend(["## 用户当前状态", ""])
    lines.append(f"- 状态：{state_labels.get(note.user_model_signal.state.value, note.user_model_signal.state.value)}")
    lines.append(f"- 判断信心：{note.user_model_signal.confidence:.2f}")
    for signal in note.user_model_signal.signals:
        label = signal_labels.get(signal.signal_type.value, signal.signal_type.value)
        lines.append(f"- {label}：{signal.text}")
    lines.append("")

    if note.evidence:
        lines.extend(["## 关键证据", ""])
        for evidence in note.evidence:
            lines.append(f"- {source_labels.get(evidence.source, evidence.source)}：{evidence.quote}")
        lines.append("")

    if note.open_questions:
        lines.extend(["## 待追踪问题", ""])
        for question in note.open_questions:
            lines.append(f"- {question}")
        lines.append("")

    return "\n".join(lines).strip()


def parse_metadata(raw_text: str, pdf_filename: str | None = None) -> ParseResult:
    json_text = extract_json_text(raw_text)
    deserialize_result = deserialize_json(json_text)
    if not deserialize_result.ok:
        fallback_title = (pdf_filename or "未命名论文").rsplit(".", 1)[0]
        fallback = PaperMetadata(
            title=fallback_title or "未命名论文",
            authors="未知",
            research_topic="未标注",
            journal="未知",
            publication_date="未知",
            summary="",
        )
        return ParseResult(ok=True, data=fallback, extracted_text=json_text, fallback_used=True, error=deserialize_result.error)

    payload = deserialize_result.data if isinstance(deserialize_result.data, dict) else {}
    try:
        metadata = PaperMetadata(
            title=_to_clean_text(payload.get("title")) or "未命名论文",
            authors=_to_clean_text(payload.get("authors")) or "未知",
            research_topic=_to_clean_text(payload.get("research_topic")) or "未标注",
            journal=_to_clean_text(payload.get("journal")) or "未知",
            publication_date=_to_clean_text(payload.get("publication_date")) or "未知",
            summary=_to_clean_text(payload.get("summary")),
        )
        return ParseResult(ok=True, data=metadata, extracted_text=json_text)
    except ValidationError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="metadata_schema_error", message="metadata schema validation failed", details={"errors": exc.errors()}),
        )


def parse_qa(raw_text: str) -> ParseResult:
    answer = _to_clean_text(raw_text)
    if not answer:
        return ParseResult(
            ok=False,
            data="模型未返回可解析内容。",
            extracted_text=raw_text,
            error=ParseError(code="empty_answer", message="empty answer from model"),
            fallback_used=True,
        )
    return ParseResult(ok=True, data=answer, extracted_text=raw_text)


def normalize_session_note(item: dict[str, Any], index: int) -> SessionNote | None:
    raw_summary = _to_clean_text(item.get("summary"))
    raw_knowledge_unit = item.get("knowledge_unit") if isinstance(item.get("knowledge_unit"), dict) else {}
    raw_user_model_signal = item.get("user_model_signal") if isinstance(item.get("user_model_signal"), dict) else {}

    term = _to_clean_text(raw_knowledge_unit.get("term"))
    core_claim = _to_clean_text(raw_knowledge_unit.get("core_claim"))
    fallback_text = raw_summary or core_claim or term
    title = _to_clean_text(item.get("title")) or (term or f"关键问题-{index}")
    topic_key = _normalize_topic_key(_to_clean_text(item.get("topic_key")) or title)
    if not title or not topic_key:
        return None

    unit_type = _normalize_unit_type(_to_clean_text(raw_knowledge_unit.get("unit_type")), fallback_text)
    summary = raw_summary or core_claim or f"用户在本次 Session 中围绕“{term or title}”暴露出值得跟踪的认知状态。"

    facets: list[KnowledgeFacet] = []
    if isinstance(raw_knowledge_unit.get("facets"), list):
        for raw_facet in raw_knowledge_unit.get("facets"):
            if not isinstance(raw_facet, dict):
                continue
            text = _to_clean_text(raw_facet.get("text"))
            if not text:
                continue
            facets.append(
                KnowledgeFacet(
                    facet_type=_normalize_facet_type(_to_clean_text(raw_facet.get("facet_type")), text),
                    text=text,
                )
            )

    signals: list[UserSignal] = []
    if isinstance(raw_user_model_signal.get("signals"), list):
        for raw_signal in raw_user_model_signal.get("signals"):
            if not isinstance(raw_signal, dict):
                continue
            text = _to_clean_text(raw_signal.get("text"))
            if not text:
                continue
            signals.append(
                UserSignal(
                    signal_type=_normalize_signal_type(_to_clean_text(raw_signal.get("signal_type")), text),
                    text=text,
                )
            )

    evidence_items: list[EvidenceItem] = []
    if isinstance(item.get("evidence"), list):
        for evidence in item.get("evidence"):
            if not isinstance(evidence, dict):
                continue
            quote = _to_clean_text(evidence.get("quote"))
            if not quote:
                continue
            source = "user" if _to_clean_text(evidence.get("source")) == "user" else "assistant"
            evidence_items.append(EvidenceItem(source=source, quote=quote))

    dedupe_hints = item.get("dedupe_hints") if isinstance(item.get("dedupe_hints"), dict) else {}

    note = SessionNote(
        note_id=_to_clean_text(item.get("note_id")) or f"temp_{index:03d}",
        title=title,
        topic_key=topic_key,
        summary=summary,
        content="",
        knowledge_unit=KnowledgeUnit(
            unit_type=unit_type,
            term=term or title,
            core_claim=core_claim or summary,
            facets=facets,
            related_terms=_to_string_list(raw_knowledge_unit.get("related_terms")),
        ),
        user_model_signal=UserModelSignal(
            state=_normalize_state(_to_clean_text(raw_user_model_signal.get("state")), unit_type),
            confidence=_to_confidence(raw_user_model_signal.get("confidence"), default=0.65),
            signals=signals,
        ),
        evidence=evidence_items,
        graph_suggestions=_normalize_graph_suggestions(item.get("graph_suggestions")),
        open_questions=_to_string_list(item.get("open_questions")),
        dedupe_hints=DedupeHints(
            aliases=_to_string_list(dedupe_hints.get("aliases")),
            semantic_fingerprint=_to_string_list(dedupe_hints.get("semantic_fingerprint"))[:6],
        ),
    )
    note.content = render_structured_note_markdown(note)
    return note


def parse_session_notes(raw_text: str, max_points: int | None = None) -> ParseResult:
    json_text = extract_json_text(raw_text)
    deserialize_result = deserialize_json(json_text)
    if not deserialize_result.ok:
        return ParseResult(ok=True, data=[], extracted_text=json_text, fallback_used=True, error=deserialize_result.error)

    payload = deserialize_result.data if isinstance(deserialize_result.data, dict) else {}
    raw_notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    notes: list[SessionNote] = []
    for index, raw_note in enumerate(raw_notes, start=1):
        if not isinstance(raw_note, dict):
            continue
        normalized = normalize_session_note(raw_note, index=index)
        if normalized:
            notes.append(normalized)

    if isinstance(max_points, int) and max_points > 0:
        notes = notes[:max_points]

    try:
        validated = SessionNotesPayload(notes=notes)
    except ValidationError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="session_notes_schema_error", message="session notes validation failed", details={"errors": exc.errors()}),
        )

    return ParseResult(ok=True, data=validated.notes, extracted_text=json_text)
