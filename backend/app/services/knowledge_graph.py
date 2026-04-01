from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from ..models import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeUnit,
    KnowledgeUnitNodeLink,
    KnowledgeUnitNoteLink,
    Note,
)

UNIT_TO_NODE_TYPE = {
    "concept": "Concept",
    "claim": "Claim",
    "method": "Method",
    "question": "Question",
    "distinction": "Concept",
}
UNDIRECTED_EDGE_RELATIONS = {"RELATED_TO", "CONTRASTS_WITH"}


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_text(value: object) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", _clean_text(value).lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalize_key(value: object) -> str:
    return _normalize_text(value).replace(" ", "-")


def _merge_unique_strings(*groups: Iterable[object], limit: int = 24) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = _clean_text(item)
            key = _normalize_text(text)
            if not text or not key or key in seen:
                continue
            seen.add(key)
            results.append(text)
            if len(results) >= limit:
                return results
    return results


def _token_set(value: object) -> set[str]:
    normalized = _normalize_text(value)
    return {token for token in normalized.split(" ") if token}


def _similarity_score(left: object, right: object) -> float:
    left_norm = _normalize_text(left)
    right_norm = _normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0

    left_tokens = _token_set(left_norm)
    right_tokens = _token_set(right_norm)
    token_overlap = 0.0
    if left_tokens and right_tokens:
        token_overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    contains_bonus = 0.0
    if min(len(left_norm), len(right_norm)) >= 4 and (left_norm in right_norm or right_norm in left_norm):
        contains_bonus = 0.94

    sequence_ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    return max(token_overlap, contains_bonus, sequence_ratio)


def _best_similarity(candidates: Iterable[object], references: Iterable[object]) -> float:
    best = 0.0
    for candidate in candidates:
        for reference in references:
            best = max(best, _similarity_score(candidate, reference))
            if best >= 1.0:
                return best
    return best


def _knowledge_unit_candidates(note_payload: dict[str, object]) -> list[str]:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}
    return _merge_unique_strings(
        [
            note_payload.get("topic_key"),
            note_payload.get("title"),
            note_payload.get("summary"),
            knowledge_unit.get("term"),
            knowledge_unit.get("core_claim"),
        ],
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
    )


def _node_candidates(name: str, aliases: list[str] | None = None) -> list[str]:
    return _merge_unique_strings([name], aliases or [])


def _canonicalize_edge_endpoints(from_node_id: int, relation: str, to_node_id: int) -> tuple[int, int]:
    if relation in UNDIRECTED_EDGE_RELATIONS and from_node_id > to_node_id:
        return to_node_id, from_node_id
    return from_node_id, to_node_id


def _find_similar_knowledge_unit(db: Session, paper_id: str | None, note_payload: dict[str, object]) -> KnowledgeUnit | None:
    candidates = _knowledge_unit_candidates(note_payload)
    if not candidates:
        return None

    best_match = None
    best_score = 0.0
    for unit in db.query(KnowledgeUnit).all():
        references = _merge_unique_strings(
            [unit.canonical_key, unit.term, unit.core_claim, unit.summary],
            unit.aliases if isinstance(unit.aliases, list) else [],
            unit.semantic_fingerprint if isinstance(unit.semantic_fingerprint, list) else [],
        )
        score = _best_similarity(candidates, references)
        if score > best_score:
            best_score = score
            best_match = unit

    return best_match if best_score >= 0.88 else None


def _find_similar_node(
    db: Session,
    paper_id: str | None,
    name: str,
    aliases: list[str] | None = None,
    node_type: str | None = None,
) -> KnowledgeGraphNode | None:
    candidates = _node_candidates(name, aliases)
    if not candidates:
        return None

    query = db.query(KnowledgeGraphNode)
    if node_type:
        query = query.filter(KnowledgeGraphNode.node_type == node_type)

    best_match = None
    best_score = 0.0
    for node in query.all():
        references = _merge_unique_strings(
            [node.name, node.normalized_key],
            node.aliases if isinstance(node.aliases, list) else [],
        )
        score = _best_similarity(candidates, references)
        if score > best_score:
            best_score = score
            best_match = node

    return best_match if best_score >= 0.9 else None


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


def _ensure_unit_node_link(db: Session, knowledge_unit_id: int, node_id: int) -> None:
    for pending in db.new:
        if (
            isinstance(pending, KnowledgeUnitNodeLink)
            and pending.knowledge_unit_id == knowledge_unit_id
            and pending.node_id == node_id
        ):
            return

    link = (
        db.query(KnowledgeUnitNodeLink)
        .filter(KnowledgeUnitNodeLink.knowledge_unit_id == knowledge_unit_id, KnowledgeUnitNodeLink.node_id == node_id)
        .first()
    )
    if link is None:
        db.add(KnowledgeUnitNodeLink(knowledge_unit_id=knowledge_unit_id, node_id=node_id))


def _upsert_knowledge_unit(db: Session, note: Note, note_payload: dict[str, object]) -> KnowledgeUnit | None:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    term = _clean_text(knowledge_unit.get("term"))
    unit_type = _clean_text(knowledge_unit.get("unit_type")) or "concept"
    if not term:
        return None

    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}
    aliases = _merge_unique_strings(
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
    )
    semantic_fingerprint = _merge_unique_strings(
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        [note_payload.get("topic_key"), term],
        limit=12,
    )

    existing = _find_similar_knowledge_unit(db, note.paper_id, note_payload)
    if existing is None:
        existing = KnowledgeUnit(
            paper_id=note.paper_id,
            canonical_key=_normalize_key(note_payload.get("topic_key") or term),
            unit_type=unit_type,
            term=term,
            core_claim=_clean_text(knowledge_unit.get("core_claim")),
            summary=_clean_text(note_payload.get("summary")),
            aliases=aliases,
            semantic_fingerprint=semantic_fingerprint,
            payload={
                **knowledge_unit,
                "source_paper_ids": [note.paper_id] if note.paper_id else [],
            },
        )
        db.add(existing)
        db.flush()
        return existing

    existing.unit_type = existing.unit_type or unit_type
    if not existing.term:
        existing.term = term
    if not existing.core_claim:
        existing.core_claim = _clean_text(knowledge_unit.get("core_claim"))
    if not existing.summary:
        existing.summary = _clean_text(note_payload.get("summary"))
    existing.canonical_key = existing.canonical_key or _normalize_key(note_payload.get("topic_key") or term)
    existing.aliases = _merge_unique_strings(existing.aliases if isinstance(existing.aliases, list) else [], aliases)
    existing.semantic_fingerprint = _merge_unique_strings(
        existing.semantic_fingerprint if isinstance(existing.semantic_fingerprint, list) else [],
        semantic_fingerprint,
        limit=12,
    )
    next_payload = dict(existing.payload) if isinstance(existing.payload, dict) else {}
    if not next_payload:
        next_payload = dict(knowledge_unit)
    source_paper_ids = _merge_unique_strings(
        next_payload.get("source_paper_ids") if isinstance(next_payload.get("source_paper_ids"), list) else [],
        [note.paper_id] if note.paper_id else [],
        limit=32,
    )
    if source_paper_ids:
        next_payload["source_paper_ids"] = source_paper_ids
    existing.payload = next_payload
    return existing


def _upsert_graph_node(
    db: Session,
    paper_id: str | None,
    node_type: str,
    name: str,
    aliases: list[str] | None = None,
    payload: dict[str, object] | None = None,
) -> KnowledgeGraphNode | None:
    clean_name = _clean_text(name)
    if not clean_name:
        return None

    existing = _find_similar_node(db, paper_id, clean_name, aliases=aliases, node_type=node_type)
    merged_aliases = _merge_unique_strings(aliases or [], [clean_name], limit=16)
    if existing is None:
        existing = KnowledgeGraphNode(
            paper_id=paper_id,
            node_type=node_type,
            name=clean_name,
            normalized_key=_normalize_key(clean_name),
            aliases=merged_aliases,
            payload={
                **(payload or {}),
                "source_paper_ids": [paper_id] if paper_id else [],
            },
        )
        db.add(existing)
        db.flush()
        return existing

    existing.aliases = _merge_unique_strings(existing.aliases if isinstance(existing.aliases, list) else [], merged_aliases, limit=16)
    if len(clean_name) > len(existing.name):
        existing.name = clean_name
        existing.normalized_key = _normalize_key(clean_name)
    if payload:
        next_payload = dict(existing.payload) if isinstance(existing.payload, dict) else {}
        next_payload.update({key: value for key, value in payload.items() if value not in (None, "", [], {})})
        existing.payload = next_payload
    return existing


def _upsert_graph_edge(
    db: Session,
    paper_id: str | None,
    from_node_id: int,
    relation: str,
    to_node_id: int,
    payload: dict[str, object] | None = None,
) -> KnowledgeGraphEdge:
    from_node_id, to_node_id = _canonicalize_edge_endpoints(from_node_id, relation, to_node_id)
    edge = (
        db.query(KnowledgeGraphEdge)
        .filter(
            KnowledgeGraphEdge.from_node_id == from_node_id,
            KnowledgeGraphEdge.relation == relation,
            KnowledgeGraphEdge.to_node_id == to_node_id,
        )
        .first()
    )
    if edge is None:
        edge = KnowledgeGraphEdge(
            paper_id=paper_id,
            from_node_id=from_node_id,
            relation=relation,
            to_node_id=to_node_id,
            payload={
                **(payload or {}),
                "source_paper_ids": [paper_id] if paper_id else [],
            },
        )
        db.add(edge)
        db.flush()
        return edge

    if payload:
        next_payload = dict(edge.payload) if isinstance(edge.payload, dict) else {}
        next_payload.update({key: value for key, value in payload.items() if value not in (None, "", [], {})})
        source_paper_ids = _merge_unique_strings(
            next_payload.get("source_paper_ids") if isinstance(next_payload.get("source_paper_ids"), list) else [],
            [paper_id] if paper_id else [],
            limit=32,
        )
        if source_paper_ids:
            next_payload["source_paper_ids"] = source_paper_ids
        edge.payload = next_payload
    return edge


def sync_note_to_knowledge_graph(db: Session, note: Note) -> dict[str, object]:
    note_payload = note.structured_data if isinstance(note.structured_data, dict) else {}
    if not note_payload:
        return {"knowledge_unit_id": None, "node_ids": [], "edge_ids": []}

    knowledge_unit = _upsert_knowledge_unit(db, note, note_payload)
    if knowledge_unit is None:
        return {"knowledge_unit_id": None, "node_ids": [], "edge_ids": []}

    _ensure_note_link(db, knowledge_unit.id, note.id)

    knowledge_payload = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    primary_term = _clean_text(knowledge_payload.get("term")) or _clean_text(note_payload.get("title"))
    primary_node_type = UNIT_TO_NODE_TYPE.get(_clean_text(knowledge_payload.get("unit_type")), "Concept")
    primary_aliases = _merge_unique_strings(
        knowledge_payload.get("related_terms") if isinstance(knowledge_payload.get("related_terms"), list) else [],
        [knowledge_unit.term],
    )
    primary_node = _upsert_graph_node(
        db,
        note.paper_id,
        primary_node_type,
        primary_term,
        aliases=primary_aliases,
        payload={"source": "knowledge_unit", "knowledge_unit_id": knowledge_unit.id},
    )

    node_ids: list[int] = []
    node_name_map: dict[str, KnowledgeGraphNode] = {}
    if primary_node is not None:
        _ensure_unit_node_link(db, knowledge_unit.id, primary_node.id)
        node_ids.append(primary_node.id)
        node_name_map[_normalize_text(primary_node.name)] = primary_node

    graph_suggestions = (
        note_payload.get("graph_suggestions") if isinstance(note_payload.get("graph_suggestions"), dict) else {}
    )
    raw_nodes = graph_suggestions.get("nodes") if isinstance(graph_suggestions.get("nodes"), list) else []
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue
        node_type = _clean_text(raw_node.get("node_type")) or "Concept"
        name = _clean_text(raw_node.get("name"))
        if not name:
            continue
        matched_node = _upsert_graph_node(
            db,
            note.paper_id,
            node_type,
            name,
            aliases=[knowledge_unit.term] if knowledge_unit.term else [],
            payload={"source": "graph_suggestion", "knowledge_unit_id": knowledge_unit.id},
        )
        if matched_node is None:
            continue
        _ensure_unit_node_link(db, knowledge_unit.id, matched_node.id)
        node_name_map[_normalize_text(name)] = matched_node
        if matched_node.id not in node_ids:
            node_ids.append(matched_node.id)

    edge_ids: list[int] = []
    raw_edges = graph_suggestions.get("edges") if isinstance(graph_suggestions.get("edges"), list) else []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            continue
        from_name = _clean_text(raw_edge.get("from"))
        to_name = _clean_text(raw_edge.get("to"))
        relation = _clean_text(raw_edge.get("relation")) or "RELATED_TO"
        if not from_name or not to_name:
            continue

        from_node = node_name_map.get(_normalize_text(from_name)) or _upsert_graph_node(
            db,
            note.paper_id,
            "Concept",
            from_name,
            payload={"source": "edge_autocreate", "knowledge_unit_id": knowledge_unit.id},
        )
        to_node = node_name_map.get(_normalize_text(to_name)) or _upsert_graph_node(
            db,
            note.paper_id,
            "Concept",
            to_name,
            payload={"source": "edge_autocreate", "knowledge_unit_id": knowledge_unit.id},
        )
        if from_node is None or to_node is None:
            continue

        node_name_map[_normalize_text(from_name)] = from_node
        node_name_map[_normalize_text(to_name)] = to_node
        _ensure_unit_node_link(db, knowledge_unit.id, from_node.id)
        _ensure_unit_node_link(db, knowledge_unit.id, to_node.id)

        if from_node.id not in node_ids:
            node_ids.append(from_node.id)
        if to_node.id not in node_ids:
            node_ids.append(to_node.id)

        edge = _upsert_graph_edge(
            db,
            note.paper_id,
            from_node.id,
            relation,
            to_node.id,
            payload={"knowledge_unit_id": knowledge_unit.id, "note_id": note.id},
        )
        if edge.id not in edge_ids:
            edge_ids.append(edge.id)

    return {
        "knowledge_unit_id": knowledge_unit.id,
        "node_ids": node_ids,
        "edge_ids": edge_ids,
    }
