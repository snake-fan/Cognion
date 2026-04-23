from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .schemas import (
    CanonicalDecision,
    CanonicalDecisionsPayload,
    CanonicalizationAction,
    CognitiveState,
    DedupeHints,
    ExtractedUnit,
    ExtractedUnitsPayload,
    PaperMetadata,
    ParseError,
    ParseResult,
    RelationDecision,
    RelationDecisionsPayload,
    RelationType,
    StructuredNote,
    StructuredNotesPayload,
    UnitRelationCandidate,
    UserState,
    UnitType,
)

UNDIRECTED_EDGE_RELATIONS = {
    "RELATED_TO",
    "CONTRASTS_WITH",
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


def _normalize_state(value: str, *texts: str) -> UserState:
    if value in {item.value for item in UserState}:
        return UserState(value)
    combined = " ".join(texts)
    if "?" in combined or "？" in combined:
        return UserState.CONFUSED
    return UserState.MENTIONED


def _extract_summary_from_markdown(content: str) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("- ", "* ", "> ")):
            continue
        if re.match(r"^\d+\.\s", line):
            continue
        return line if len(line) <= 120 else f"{line[:117].rstrip()}..."
    return ""


def _ensure_markdown_title(content: str, title: str) -> str:
    text = content.strip()
    if not text:
        return ""
    if re.match(r"^#\s+", text):
        return text
    return f"# {title}\n\n{text}"


def render_structured_note_markdown(note: StructuredNote) -> str:
    state_labels = {
        UserState.MENTIONED.value: "仅提及",
        UserState.EXPOSED.value: "已接触",
        UserState.CONFUSED.value: "存在困惑",
        UserState.PARTIAL_UNDERSTANDING.value: "部分理解",
        UserState.UNDERSTOOD.value: "基本理解",
        UserState.MISALIGNED.value: "理解偏差",
    }
    lines = [f"# {note.title}", ""]
    if note.summary:
        lines.extend(["## 这条笔记在记录什么", "", note.summary, ""])

    lines.extend(["## 用户当前是怎么理解这个问题的", ""])
    lines.append(f"- 认知状态：{state_labels.get(note.cognitive_state.state.value, note.cognitive_state.state.value)}")
    lines.append(f"- 判断信心：{note.cognitive_state.confidence:.2f}")
    lines.append("")
    if note.cognitive_state.mental_model:
        lines.append(note.cognitive_state.mental_model)
        lines.append("")

    if note.follow_up_questions:
        lines.extend(["## 后续可以继续追问的问题", ""])
        for question in note.follow_up_questions:
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


def normalize_structured_note(item: dict[str, Any], index: int) -> StructuredNote | None:
    raw_summary = _to_clean_text(item.get("summary"))
    raw_content = _to_clean_text(item.get("content"))
    raw_cognitive_state = item.get("cognitive_state") if isinstance(item.get("cognitive_state"), dict) else {}
    title = _to_clean_text(item.get("title")) or f"认知笔记-{index}"
    topic_key = _normalize_topic_key(_to_clean_text(item.get("topic_key")) or title)
    if not title or not topic_key:
        return None

    follow_up_questions = _to_string_list(item.get("follow_up_questions") or item.get("open_questions"))
    mental_model = _to_clean_text(raw_cognitive_state.get("mental_model"))
    content = _ensure_markdown_title(raw_content, title)
    summary = raw_summary or _extract_summary_from_markdown(content) or mental_model or title

    dedupe_hints = item.get("dedupe_hints") if isinstance(item.get("dedupe_hints"), dict) else {}

    note = StructuredNote(
        note_id=_to_clean_text(item.get("note_id")) or f"temp_{index:03d}",
        title=title,
        topic_key=topic_key,
        summary=summary,
        content="",
        cognitive_state=CognitiveState(
            state=_normalize_state(
                _to_clean_text(raw_cognitive_state.get("state")),
                mental_model,
                summary,
                " ".join(follow_up_questions),
                content,
            ),
            confidence=_to_confidence(raw_cognitive_state.get("confidence"), default=0.65),
            mental_model=mental_model or summary,
        ),
        follow_up_questions=follow_up_questions,
        dedupe_hints=DedupeHints(
            aliases=_to_string_list(dedupe_hints.get("aliases")),
            semantic_fingerprint=_to_string_list(dedupe_hints.get("semantic_fingerprint"))[:6],
        ),
    )
    note.content = content or render_structured_note_markdown(note)
    return note


def parse_structured_notes(raw_text: str, max_points: int | None = None) -> ParseResult:
    json_text = extract_json_text(raw_text)
    deserialize_result = deserialize_json(json_text)
    if not deserialize_result.ok:
        return ParseResult(ok=True, data=[], extracted_text=json_text, fallback_used=True, error=deserialize_result.error)

    payload = deserialize_result.data if isinstance(deserialize_result.data, dict) else {}
    raw_notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    notes: list[StructuredNote] = []
    for index, raw_note in enumerate(raw_notes, start=1):
        if not isinstance(raw_note, dict):
            continue
        normalized = normalize_structured_note(raw_note, index=index)
        if normalized is not None:
            notes.append(normalized)

    if isinstance(max_points, int) and max_points > 0:
        notes = notes[:max_points]

    try:
        validated = StructuredNotesPayload(notes=notes)
    except ValidationError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="structured_notes_schema_error", message="structured notes validation failed", details={"errors": exc.errors()}),
        )

    return ParseResult(ok=True, data=validated.notes, extracted_text=json_text)


def _normalize_relation_type(value: str, fallback: str = "") -> RelationType:
    if value in {item.value for item in RelationType}:
        return RelationType(value)
    text = f"{value} {fallback}".lower()
    if "confus" in text or "混淆" in text:
        return RelationType.CONFUSED_WITH
    if "prereq" in text or "前置" in text:
        return RelationType.PREREQUISITE_OF
    if "use" in text or "用于" in text:
        return RelationType.USED_FOR
    if "same" in text or "同一" in text:
        return RelationType.SAME_AS
    if "ask" in text or "问题" in text:
        return RelationType.ASKS_ABOUT
    return RelationType.RELATED_TO


def _normalize_canonical_action(value: str) -> CanonicalizationAction:
    if value in {item.value for item in CanonicalizationAction}:
        if value == CanonicalizationAction.SOFT_LINK.value:
            return CanonicalizationAction.CREATE_NEW
        return CanonicalizationAction(value)
    text = value.lower()
    if "merge" in text:
        return CanonicalizationAction.MERGE
    if "reuse" in text:
        return CanonicalizationAction.REUSE
    return CanonicalizationAction.CREATE_NEW


def parse_extracted_units(raw_text: str, source_note_id: str) -> ParseResult:
    json_text = extract_json_text(raw_text)
    deserialize_result = deserialize_json(json_text)
    if not deserialize_result.ok:
        return ParseResult(ok=True, data=[], extracted_text=json_text, fallback_used=True, error=deserialize_result.error)

    payload = deserialize_result.data if isinstance(deserialize_result.data, dict) else {}
    raw_units = payload.get("units") if isinstance(payload.get("units"), list) else []
    units: list[ExtractedUnit] = []
    seen: set[str] = set()
    for index, raw_unit in enumerate(raw_units, start=1):
        if not isinstance(raw_unit, dict):
            continue
        canonical_name = _to_clean_text(raw_unit.get("canonical_name") or raw_unit.get("term"))
        if not canonical_name:
            continue
        unit_key = _normalize_topic_key(canonical_name)
        if unit_key in seen:
            continue
        seen.add(unit_key)

        local_relations: list[UnitRelationCandidate] = []
        raw_relations = raw_unit.get("local_relations")
        if isinstance(raw_relations, list):
            for raw_relation in raw_relations:
                if not isinstance(raw_relation, dict):
                    continue
                target_ref = _to_clean_text(raw_relation.get("target_unit_ref") or raw_relation.get("to_unit_ref"))
                if not target_ref:
                    continue
                local_relations.append(
                    UnitRelationCandidate(
                        target_unit_ref=target_ref,
                        relation_type=_normalize_relation_type(_to_clean_text(raw_relation.get("relation_type"))),
                    )
                )

        units.append(
            ExtractedUnit(
                unit_id=_to_clean_text(raw_unit.get("unit_id")) or f"{source_note_id}_unit_{index:03d}",
                source_note_id=source_note_id,
                type=_normalize_unit_type(_to_clean_text(raw_unit.get("type")), canonical_name),
                canonical_name=canonical_name,
                aliases=_to_string_list(raw_unit.get("aliases")),
                description=_to_clean_text(raw_unit.get("description")),
                keywords=_to_string_list(raw_unit.get("keywords")),
                slots=raw_unit.get("slots") if isinstance(raw_unit.get("slots"), dict) else {},
                local_relations=local_relations,
            )
        )

    try:
        validated = ExtractedUnitsPayload(units=units)
    except ValidationError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="extracted_units_schema_error", message="extracted units validation failed", details={"errors": exc.errors()}),
        )

    return ParseResult(ok=True, data=validated.units, extracted_text=json_text)


def parse_canonical_decisions(raw_text: str) -> ParseResult:
    json_text = extract_json_text(raw_text)
    deserialize_result = deserialize_json(json_text)
    if not deserialize_result.ok:
        return ParseResult(ok=True, data=[], extracted_text=json_text, fallback_used=True, error=deserialize_result.error)

    payload = deserialize_result.data if isinstance(deserialize_result.data, dict) else {}
    raw_decisions = payload.get("decisions") if isinstance(payload.get("decisions"), list) else []
    decisions: list[CanonicalDecision] = []
    for raw_decision in raw_decisions:
        if not isinstance(raw_decision, dict):
            continue
        source_unit_id = _to_clean_text(raw_decision.get("source_unit_id"))
        if not source_unit_id:
            continue
        decisions.append(
            CanonicalDecision(
                source_unit_id=source_unit_id,
                action=_normalize_canonical_action(_to_clean_text(raw_decision.get("action"))),
                target_unit_id=int(raw_decision["target_unit_id"]) if isinstance(raw_decision.get("target_unit_id"), int) else None,
                target_canonical_key=_to_clean_text(raw_decision.get("target_canonical_key")) or None,
                confidence=_to_confidence(raw_decision.get("confidence"), default=0.55),
                reason=_to_clean_text(raw_decision.get("reason")),
            )
        )

    try:
        validated = CanonicalDecisionsPayload(decisions=decisions)
    except ValidationError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="canonical_decisions_schema_error", message="canonical decisions validation failed", details={"errors": exc.errors()}),
        )

    return ParseResult(ok=True, data=validated.decisions, extracted_text=json_text)


def parse_relation_decisions(raw_text: str) -> ParseResult:
    json_text = extract_json_text(raw_text)
    deserialize_result = deserialize_json(json_text)
    if not deserialize_result.ok:
        return ParseResult(ok=True, data=[], extracted_text=json_text, fallback_used=True, error=deserialize_result.error)

    payload = deserialize_result.data if isinstance(deserialize_result.data, dict) else {}
    raw_relations = payload.get("relations") if isinstance(payload.get("relations"), list) else []
    relations: list[RelationDecision] = []
    seen: set[str] = set()
    for raw_relation in raw_relations:
        if not isinstance(raw_relation, dict):
            continue
        from_unit_ref = _to_clean_text(raw_relation.get("from_unit_ref"))
        to_unit_ref = _to_clean_text(raw_relation.get("to_unit_ref"))
        if not from_unit_ref or not to_unit_ref:
            continue
        relation_type = _normalize_relation_type(_to_clean_text(raw_relation.get("relation_type")))
        key = f"{from_unit_ref}:{relation_type.value}:{to_unit_ref}"
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            RelationDecision(
                from_unit_ref=from_unit_ref,
                relation_type=relation_type,
                to_unit_ref=to_unit_ref,
                confidence=_to_confidence(raw_relation.get("confidence"), default=0.55),
            )
        )

    try:
        validated = RelationDecisionsPayload(relations=relations)
    except ValidationError as exc:
        return ParseResult(
            ok=False,
            extracted_text=json_text,
            error=ParseError(code="relation_decisions_schema_error", message="relation decisions validation failed", details={"errors": exc.errors()}),
        )

    return ParseResult(ok=True, data=validated.relations, extracted_text=json_text)
