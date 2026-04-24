from __future__ import annotations

from sqlalchemy.orm import Session

from ...db import KnowledgeGraphEdge, KnowledgeUnit, KnowledgeUnitNoteLink, Note
from .common import (
    UNDIRECTED_EDGE_RELATIONS,
    _clean_text,
    _merge_unique_strings,
    _normalize_key,
    _sanitize_related_terms,
    _sanitize_slots,
)


def _canonicalize_edge_endpoints(from_unit_id: int, relation: str, to_unit_id: int) -> tuple[int, int]:
    if relation in UNDIRECTED_EDGE_RELATIONS and from_unit_id > to_unit_id:
        return to_unit_id, from_unit_id
    return from_unit_id, to_unit_id


def _ensure_note_link(db: Session, knowledge_unit_id: int, note_id: int) -> None:
    for pending in db.new:
        if (
            isinstance(pending, KnowledgeUnitNoteLink)
            and pending.knowledge_unit_id == knowledge_unit_id
            and pending.note_id == note_id
        ):
            return

    link = (
        db.query(KnowledgeUnitNoteLink)
        .filter(KnowledgeUnitNoteLink.knowledge_unit_id == knowledge_unit_id, KnowledgeUnitNoteLink.note_id == note_id)
        .first()
    )
    if link is None:
        db.add(KnowledgeUnitNoteLink(knowledge_unit_id=knowledge_unit_id, note_id=note_id))


def _create_new_knowledge_unit(db: Session, note: Note, note_payload: dict[str, object]) -> KnowledgeUnit | None:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    term = _clean_text(knowledge_unit.get("term"))
    unit_type = _clean_text(knowledge_unit.get("unit_type")) or "concept"
    if not term:
        return None

    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}
    aliases = _merge_unique_strings(
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        knowledge_unit.get("aliases") if isinstance(knowledge_unit.get("aliases"), list) else [],
    )
    related_terms = _sanitize_related_terms(
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
        [note_payload.get("topic_key"), term],
        limit=12,
    )

    created = KnowledgeUnit(
        paper_id=note.paper_id,
        canonical_key=_normalize_key(note_payload.get("topic_key") or term),
        unit_type=unit_type,
        term=term,
        core_claim=_clean_text(knowledge_unit.get("core_claim")),
        summary=_clean_text(note_payload.get("summary")),
        aliases=aliases,
        related_terms=related_terms,
        slots=_sanitize_slots(knowledge_unit.get("slots")),
    )
    db.add(created)
    db.flush()
    return created


def _upsert_graph_edge(
    db: Session,
    paper_id: str | None,
    from_unit_id: int,
    relation: str,
    to_unit_id: int,
    payload: dict[str, object] | None = None,
) -> KnowledgeGraphEdge:
    from_unit_id, to_unit_id = _canonicalize_edge_endpoints(from_unit_id, relation, to_unit_id)
    edge = (
        db.query(KnowledgeGraphEdge)
        .filter(
            KnowledgeGraphEdge.from_unit_id == from_unit_id,
            KnowledgeGraphEdge.relation == relation,
            KnowledgeGraphEdge.to_unit_id == to_unit_id,
        )
        .first()
    )
    if edge is None:
        edge = KnowledgeGraphEdge(
            paper_id=paper_id,
            from_unit_id=from_unit_id,
            relation=relation,
            to_unit_id=to_unit_id,
            payload={key: value for key, value in (payload or {}).items() if value not in (None, "", [], {})},
        )
        db.add(edge)
        db.flush()
        return edge

    if payload:
        next_payload = dict(edge.payload) if isinstance(edge.payload, dict) else {}
        next_payload.update({key: value for key, value in payload.items() if value not in (None, "", [], {})})
        edge.payload = next_payload
    return edge
