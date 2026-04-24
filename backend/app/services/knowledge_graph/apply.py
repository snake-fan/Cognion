from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from ...agents.model_adapter import ModelAdapterError
from ...agents.schemas import (
    CanonicalizationAction,
    GraphPatch,
    GraphPatchRelationOp,
    GraphPatchUnitOp,
    ModelCallParams,
    ModelMessage,
)
from ...db import (
    KnowledgeUnit,
    Note,
)
from ..config import OPENAI_MERGE_MODEL
from .common import (
    _clean_text,
    _get_merge_adapter,
    _merge_distinct_texts,
    _merge_unique_strings,
    _normalize_key,
    _normalize_text,
    _sanitize_related_terms,
    _sanitize_slots,
)
from .store import _create_new_knowledge_unit, _ensure_note_link, _upsert_graph_edge


def _resolve_unit_reference(db: Session, unit_ref: str, resolved_units: dict[str, KnowledgeUnit]) -> KnowledgeUnit | None:
    if unit_ref.startswith("history:"):
        try:
            history_id = int(unit_ref.split(":", 1)[1])
        except (TypeError, ValueError):
            return None
        return db.query(KnowledgeUnit).filter(KnowledgeUnit.id == history_id).first()
    return resolved_units.get(unit_ref)


def _get_note_by_ref(note_refs: dict[str, Note], note_id: str) -> Note | None:
    return note_refs.get(note_id)


def _knowledge_unit_from_patch_payload(payload: dict[str, object]) -> dict[str, object]:
    unit_type = _clean_text(payload.get("type")) or "concept"
    canonical_name = _clean_text(payload.get("canonical_name"))
    description = _clean_text(payload.get("description"))
    aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else []
    keywords = payload.get("keywords") if isinstance(payload.get("keywords"), list) else []
    slots = payload.get("slots") if isinstance(payload.get("slots"), dict) else {}
    return {
        "unit_type": unit_type,
        "term": canonical_name,
        "core_claim": description,
        "aliases": aliases,
        "related_terms": keywords,
        "slots": slots,
    }


def _serialize_existing_knowledge_unit_for_merge(existing: KnowledgeUnit) -> dict[str, object]:
    return {
        "unit_type": existing.unit_type,
        "term": existing.term,
        "canonical_key": existing.canonical_key,
        "core_claim": existing.core_claim,
        "summary": existing.summary,
        "aliases": existing.aliases if isinstance(existing.aliases, list) else [],
        "related_terms": existing.related_terms if isinstance(existing.related_terms, list) else [],
        "slots": existing.slots if isinstance(existing.slots, dict) else {},
    }


def _sanitize_llm_merged_unit(
    *,
    existing: KnowledgeUnit,
    note_payload: dict[str, object],
    merged_unit: dict[str, object],
) -> dict[str, object]:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}

    incoming_term = _clean_text(knowledge_unit.get("term"))
    incoming_core_claim = _clean_text(knowledge_unit.get("core_claim"))
    incoming_summary = _clean_text(note_payload.get("summary"))
    incoming_aliases = knowledge_unit.get("aliases") if isinstance(knowledge_unit.get("aliases"), list) else []
    incoming_related_terms = (
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else []
    )
    incoming_slots = knowledge_unit.get("slots") if isinstance(knowledge_unit.get("slots"), dict) else {}

    term = _clean_text(merged_unit.get("term")) or existing.term or incoming_term
    canonical_key = _clean_text(merged_unit.get("canonical_key")) or existing.canonical_key or _normalize_key(note_payload.get("topic_key") or term)
    unit_type = _clean_text(merged_unit.get("unit_type")) or existing.unit_type or (_clean_text(knowledge_unit.get("unit_type")) or "concept")

    aliases = _merge_unique_strings(
        existing.aliases if isinstance(existing.aliases, list) else [],
        merged_unit.get("aliases") if isinstance(merged_unit.get("aliases"), list) else [],
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        incoming_aliases,
        [incoming_term] if incoming_term and _normalize_text(incoming_term) != _normalize_text(term) else [],
        limit=32,
    )
    related_terms = _sanitize_related_terms(
        existing.related_terms if isinstance(existing.related_terms, list) else [],
        merged_unit.get("related_terms") if isinstance(merged_unit.get("related_terms"), list) else [],
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        incoming_related_terms,
        limit=32,
    )
    slots = dict(existing.slots) if isinstance(existing.slots, dict) else {}
    llm_slots = merged_unit.get("slots") if isinstance(merged_unit.get("slots"), dict) else {}
    for key, value in {**incoming_slots, **llm_slots}.items():
        if value in (None, "", [], {}):
            continue
        slots[_clean_text(key)] = value
    core_claim = _clean_text(merged_unit.get("core_claim")) or _merge_distinct_texts(existing.core_claim, incoming_core_claim)
    summary = _clean_text(merged_unit.get("summary")) or _merge_distinct_texts(existing.summary, incoming_summary)

    return {
        "unit_type": unit_type,
        "term": term,
        "canonical_key": canonical_key,
        "core_claim": core_claim,
        "summary": summary,
        "aliases": aliases,
        "related_terms": related_terms,
        "slots": _sanitize_slots(slots),
    }


def _merge_existing_knowledge_unit_with_llm(
    *,
    existing: KnowledgeUnit,
    note_payload: dict[str, object],
) -> dict[str, object] | None:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}
    existing_unit = _serialize_existing_knowledge_unit_for_merge(existing)
    incoming_unit = {
        "unit_type": _clean_text(knowledge_unit.get("unit_type")) or "concept",
        "term": _clean_text(knowledge_unit.get("term")),
        "canonical_key": _normalize_key(note_payload.get("topic_key") or knowledge_unit.get("term")),
        "core_claim": _clean_text(knowledge_unit.get("core_claim")),
        "summary": _clean_text(note_payload.get("summary")),
        "aliases": _merge_unique_strings(
            dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
            knowledge_unit.get("aliases") if isinstance(knowledge_unit.get("aliases"), list) else [],
            [knowledge_unit.get("term")],
            limit=32,
        ),
        "related_terms": _sanitize_related_terms(
            dedupe_hints.get("semantic_fingerprint")
            if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
            else [],
            knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
            limit=32,
        ),
        "slots": _sanitize_slots(knowledge_unit.get("slots")),
    }

    prompt_payload = {
        "task": "Merge the incoming unit into the existing canonical unit because they refer to the same underlying object.",
        "rules": [
            "Return JSON only.",
            "Do not invent facts not supported by either input.",
            "Prefer one clean merged core_claim and one clean merged summary instead of concatenating both verbatim.",
            "Keep the canonical identity stable unless the incoming term is clearly a better canonical label.",
            "Aliases and related_terms should be deduplicated lists.",
            "slots should be a merged object; keep useful old keys and add useful new keys.",
        ],
        "existing_unit": existing_unit,
        "incoming_unit": incoming_unit,
    }
    system_prompt = (
        "You are merging two structured representations of the same knowledge unit. "
        "Produce one canonical merged unit. "
        "Return JSON only with shape {\"merged_unit\": {...}}."
    )

    try:
        response = _get_merge_adapter().call_blocking(
            trace_id=uuid4().hex,
            session_id=None,
            agent_name="knowledge_unit_merge",
            messages=[
                ModelMessage(role="system", content=system_prompt),
                ModelMessage(role="user", content=json.dumps(prompt_payload, ensure_ascii=False)),
            ],
            params=ModelCallParams(
                model=OPENAI_MERGE_MODEL,
                temperature=0.0,
                response_format={"type": "json_object"},
                max_tokens=900,
                timeout_seconds=20,
            ),
        )
        payload = json.loads(response.text or "{}")
    except (ModelAdapterError, json.JSONDecodeError, TypeError, ValueError):
        return None

    merged_unit = payload.get("merged_unit") if isinstance(payload.get("merged_unit"), dict) else None
    if merged_unit is None:
        return None
    return _sanitize_llm_merged_unit(
        existing=existing,
        note_payload=note_payload,
        merged_unit=merged_unit,
    )


def _merge_into_existing_knowledge_unit_fallback(
    existing: KnowledgeUnit,
    note_payload: dict[str, object],
) -> None:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}

    incoming_term = _clean_text(knowledge_unit.get("term"))
    incoming_core_claim = _clean_text(knowledge_unit.get("core_claim"))
    incoming_summary = _clean_text(note_payload.get("summary"))
    incoming_aliases = _merge_unique_strings(
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        knowledge_unit.get("aliases") if isinstance(knowledge_unit.get("aliases"), list) else [],
        [incoming_term] if incoming_term and _normalize_text(incoming_term) != _normalize_text(existing.term) else [],
        limit=32,
    )
    incoming_related_terms = _sanitize_related_terms(
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
        limit=32,
    )

    existing.unit_type = existing.unit_type or (_clean_text(knowledge_unit.get("unit_type")) or "concept")
    existing.term = existing.term or incoming_term
    existing.core_claim = _merge_distinct_texts(existing.core_claim, incoming_core_claim)
    existing.summary = _merge_distinct_texts(existing.summary, incoming_summary)
    existing.canonical_key = existing.canonical_key or _normalize_key(note_payload.get("topic_key") or incoming_term)
    existing.aliases = _merge_unique_strings(existing.aliases if isinstance(existing.aliases, list) else [], incoming_aliases, limit=32)
    existing.related_terms = _sanitize_related_terms(
        existing.related_terms if isinstance(existing.related_terms, list) else [],
        incoming_related_terms,
        limit=32,
    )
    merged_slots = dict(existing.slots) if isinstance(existing.slots, dict) else {}
    incoming_slots = knowledge_unit.get("slots") if isinstance(knowledge_unit.get("slots"), dict) else {}
    for key, value in incoming_slots.items():
        if value in (None, "", [], {}):
            continue
        merged_slots[key] = value
    existing.slots = _sanitize_slots(merged_slots)


def _merge_into_existing_knowledge_unit(
    existing: KnowledgeUnit,
    note_payload: dict[str, object],
) -> None:
    merged = _merge_existing_knowledge_unit_with_llm(existing=existing, note_payload=note_payload)
    if merged is None:
        _merge_into_existing_knowledge_unit_fallback(existing, note_payload)
        return

    existing.unit_type = _clean_text(merged.get("unit_type")) or existing.unit_type
    existing.term = _clean_text(merged.get("term")) or existing.term
    existing.core_claim = _clean_text(merged.get("core_claim")) or existing.core_claim
    existing.summary = _clean_text(merged.get("summary")) or existing.summary
    existing.canonical_key = _clean_text(merged.get("canonical_key")) or existing.canonical_key
    existing.aliases = merged.get("aliases") if isinstance(merged.get("aliases"), list) else existing.aliases
    existing.related_terms = (
        merged.get("related_terms")
        if isinstance(merged.get("related_terms"), list)
        else existing.related_terms
    )
    existing.slots = (
        _sanitize_slots(merged.get("slots"))
        if isinstance(merged.get("slots"), dict)
        else existing.slots
    )


def _create_or_update_knowledge_unit_from_patch(
    db: Session,
    *,
    note: Note,
    op: GraphPatchUnitOp,
) -> KnowledgeUnit | None:
    payload = op.payload
    note_payload = {
        "topic_key": note.topic_key,
        "title": note.title,
        "summary": note.summary,
        "knowledge_unit": _knowledge_unit_from_patch_payload(payload),
        "dedupe_hints": {
            "aliases": payload.get("aliases") if isinstance(payload.get("aliases"), list) else [],
            "semantic_fingerprint": payload.get("keywords") if isinstance(payload.get("keywords"), list) else [],
        },
    }
    if op.action == CanonicalizationAction.CREATE_NEW:
        created = _create_new_knowledge_unit(db, note, note_payload)
        if created is not None:
            _ensure_note_link(db, created.id, note.id)
        return created
    if op.target_unit_id is None:
        return None

    existing = db.query(KnowledgeUnit).filter(KnowledgeUnit.id == op.target_unit_id).first()
    if existing is None:
        return None

    _ensure_note_link(db, existing.id, note.id)
    if op.action == CanonicalizationAction.MERGE:
        _merge_into_existing_knowledge_unit(existing, note_payload)
    db.flush()
    return existing


def _apply_relation_op(
    db: Session,
    *,
    note: Note,
    relation_op: GraphPatchRelationOp,
    resolved_units: dict[str, KnowledgeUnit],
) -> int | None:
    from_unit = _resolve_unit_reference(db, relation_op.from_unit_ref, resolved_units)
    to_unit = _resolve_unit_reference(db, relation_op.to_unit_ref, resolved_units)
    if from_unit is None or to_unit is None:
        return None
    edge = _upsert_graph_edge(
        db,
        note.paper_id,
        from_unit.id,
        relation_op.relation_type.value.upper(),
        to_unit.id,
        payload={"note_id": note.id, "source": "graph_patch"},
    )
    return edge.id


def apply_graph_patch(
    db: Session,
    *,
    graph_patch: GraphPatch | dict[str, object],
    notes_by_ref: dict[str, Note],
) -> list[dict[str, object]]:
    if isinstance(graph_patch, dict):
        graph_patch = GraphPatch.model_validate(graph_patch)
    resolved_units: dict[str, KnowledgeUnit] = {}
    results_by_note: dict[str, dict[str, object]] = {}

    unit_ops = [
        *graph_patch.units_to_create,
        *graph_patch.units_to_update,
        *graph_patch.units_to_merge,
        *graph_patch.units_to_link,
    ]
    for op in unit_ops:
        note = _get_note_by_ref(notes_by_ref, op.note_id)
        if note is None:
            continue
        knowledge_unit = _create_or_update_knowledge_unit_from_patch(db, note=note, op=op)
        if knowledge_unit is None:
            continue
        resolved_units[op.source_unit_id] = knowledge_unit
        result = results_by_note.setdefault(
            op.note_id,
            {"note_ref": op.note_id, "note_id": note.id, "knowledge_unit_ids": [], "edge_ids": [], "decision_refs": []},
        )
        if knowledge_unit.id not in result["knowledge_unit_ids"]:
            result["knowledge_unit_ids"].append(knowledge_unit.id)
        result["decision_refs"].append({"source_unit_id": op.source_unit_id, "action": op.action.value})

    for relation_op in graph_patch.relations_to_create:
        note = _get_note_by_ref(notes_by_ref, relation_op.note_id)
        if note is None:
            continue
        edge_id = _apply_relation_op(
            db,
            note=note,
            relation_op=relation_op,
            resolved_units=resolved_units,
        )
        if edge_id is None:
            continue
        result = results_by_note.setdefault(
            relation_op.note_id,
            {"note_ref": relation_op.note_id, "note_id": note.id, "knowledge_unit_ids": [], "edge_ids": [], "decision_refs": []},
        )
        if edge_id not in result["edge_ids"]:
            result["edge_ids"].append(edge_id)
        result["decision_refs"].append({"relation": relation_op.relation_type.value, "from": relation_op.from_unit_ref, "to": relation_op.to_unit_ref})

    return list(results_by_note.values())
