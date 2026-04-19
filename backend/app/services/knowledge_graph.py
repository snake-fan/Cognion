from __future__ import annotations

import json
import re
from uuid import uuid4
from collections.abc import Iterable
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from ..agents.model_adapter import ModelAdapterError, OpenAIModelAdapter, default_log_sink
from ..agents.schemas import ModelCallParams, ModelMessage
from ..db import (
    AgentRun,
    GraphUpdateLog,
    KnowledgeGraphEdge,
    KnowledgeUnit,
    KnowledgeUnitNoteLink,
    Note,
    NoteUnitCandidate,
    UnitCanonicalizationDecision,
    UnitRelationDecision,
)
from ..agents.schemas import (
    AgentDecisionLog,
    CanonicalDecision,
    CanonicalizationAction,
    ExtractedUnit,
    GraphPatch,
    GraphPatchNoteRef,
    GraphPatchRelationOp,
    GraphPatchUnitOp,
    RelationDecision,
    RelationType,
    RetrievedUnitCandidate,
    StructuredNote,
)
from .config import OPENAI_MERGE_MODEL, OPENAI_SIMILARITY_MODEL

UNDIRECTED_EDGE_RELATIONS = {"RELATED_TO", "CONTRASTS_WITH"}
SIMILARITY_RERANK_LIMIT = 8
SIMILARITY_MODEL_SCORE_THRESHOLD = 0.78
SIMILARITY_MODEL_SAME_PAPER_THRESHOLD = 0.72
_similarity_adapter: OpenAIModelAdapter | None = None
_merge_adapter: OpenAIModelAdapter | None = None


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


def _merge_distinct_texts(*values: object) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        key = _normalize_text(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return "\n".join(parts)


def _token_set(value: object) -> set[str]:
    normalized = _normalize_text(value)
    return {token for token in normalized.split(" ") if token}


def _heuristic_similarity_score(left: object, right: object) -> float:
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
            best = max(best, _heuristic_similarity_score(candidate, reference))
            if best >= 1.0:
                return best
    return best


def _get_similarity_adapter() -> OpenAIModelAdapter:
    global _similarity_adapter
    if _similarity_adapter is None:
        _similarity_adapter = OpenAIModelAdapter(log_sink=default_log_sink())
    return _similarity_adapter


def _get_merge_adapter() -> OpenAIModelAdapter:
    global _merge_adapter
    if _merge_adapter is None:
        _merge_adapter = OpenAIModelAdapter(log_sink=default_log_sink())
    return _merge_adapter


def _truncate_similarity_text(value: object, *, max_chars: int = 160) -> str:
    text = _clean_text(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _prepare_similarity_texts(values: Iterable[object]) -> list[str]:
    return [_truncate_similarity_text(item) for item in _merge_unique_strings(values, limit=2000)]


def _model_score_candidates(
    *,
    query_texts: list[str],
    candidate_groups: list[dict[str, object]],
    agent_name: str,
) -> dict[str, float]:
    if not query_texts or not candidate_groups:
        return {}

    prompt_payload = {
        "query_texts": query_texts,
        "candidate_groups": [
            {
                "id": str(group["id"]),
                "texts": group["texts"],
                "heuristic_score": round(float(group.get("heuristic_score", 0.0)), 4),
            }
            for group in candidate_groups
        ],
    }
    system_prompt = (
        "You are a strict entity-matching grader for a knowledge graph. "
        "Judge whether the query texts and each candidate group refer to the same underlying concept/entity. "
        "Use semantic equivalence, abbreviations, aliases, paraphrases, and domain wording. "
        "Do not reward broad topical relatedness. "
        "Return JSON only with the shape "
        '{"scores":[{"id":"candidate-id","score":0.0,"reason":"short reason"}]}. '
        "Each score must be between 0 and 1, where 1 means the same entity and 0 means clearly different."
    )
    user_prompt = (
        "Score every candidate group.\n"
        "A high score requires that the query and candidate could be merged or reused as the same canonical unit.\n"
        "A medium score means maybe related but not safe to merge.\n"
        "A low score means different concepts.\n\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False)}"
    )

    try:
        response = _get_similarity_adapter().call_blocking(
            trace_id=uuid4().hex,
            session_id=None,
            agent_name=agent_name,
            messages=[
                ModelMessage(role="system", content=system_prompt),
                ModelMessage(role="user", content=user_prompt),
            ],
            params=ModelCallParams(
                model=OPENAI_SIMILARITY_MODEL,
                temperature=0.0,
                response_format={"type": "json_object"},
                max_tokens=600,
                timeout_seconds=20,
            ),
        )
        payload = json.loads(response.text or "{}")
    except (ModelAdapterError, json.JSONDecodeError, TypeError, ValueError):
        return {}

    results: dict[str, float] = {}
    for item in payload.get("scores", []):
        if not isinstance(item, dict):
            continue
        candidate_id = _clean_text(item.get("id"))
        if not candidate_id:
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        results[candidate_id] = max(0.0, min(1.0, score))
    return results


def _rerank_similarity_candidates(
    *,
    query_texts: list[str],
    candidate_groups: list[dict[str, object]],
    rerank_limit: int = SIMILARITY_RERANK_LIMIT,
    agent_name: str,
) -> list[dict[str, object]]:
    if not query_texts or not candidate_groups:
        return []

    ranked = sorted(candidate_groups, key=lambda item: float(item.get("heuristic_score", 0.0)), reverse=True)
    shortlisted = [item for item in ranked[:rerank_limit] if float(item.get("heuristic_score", 0.0)) > 0]
    if not shortlisted:
        return ranked

    model_scores = _model_score_candidates(
        query_texts=query_texts,
        candidate_groups=shortlisted,
        agent_name=agent_name,
    )
    if not model_scores:
        for item in ranked:
            item["score"] = float(item.get("heuristic_score", 0.0))
        return ranked

    for item in ranked:
        candidate_id = str(item["id"])
        item["score"] = model_scores.get(candidate_id, float(item.get("heuristic_score", 0.0)))
    ranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return ranked


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
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
    )
    semantic_fingerprint = _merge_unique_strings(
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
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
        semantic_fingerprint=semantic_fingerprint,
        payload=_sanitize_knowledge_unit_payload(
            knowledge_unit,
            source_paper_ids=[note.paper_id] if note.paper_id else [],
        ),
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


def serialize_knowledge_unit_candidate(unit: KnowledgeUnit, *, score: float = 0.0, source: str = "global") -> dict[str, object]:
    return RetrievedUnitCandidate(
        knowledge_unit_id=unit.id,
        canonical_key=unit.canonical_key,
        unit_type=unit.unit_type,
        term=unit.term,
        core_claim=unit.core_claim,
        summary=unit.summary,
        aliases=unit.aliases if isinstance(unit.aliases, list) else [],
        semantic_fingerprint=unit.semantic_fingerprint if isinstance(unit.semantic_fingerprint, list) else [],
        score=score,
        source=source,
    ).model_dump(mode="json")


def retrieve_candidate_units_for_canonicalization(
    db: Session,
    note_units: list[ExtractedUnit],
    *,
    paper_id: str | None,
    session_id: int | None,
    limit: int = 8,
) -> list[dict[str, object]]:
    del session_id
    unit_candidates: list[str] = []
    for unit in note_units:
        unit_candidates.append(unit.canonical_name)
        unit_candidates.extend(unit.aliases)
        unit_candidates.extend(unit.keywords)
        unit_candidates.append(unit.description)
    query_texts = _prepare_similarity_texts(unit_candidates)
    if not query_texts:
        return []

    scored: list[dict[str, object]] = []
    for existing in db.query(KnowledgeUnit).all():
        references = _merge_unique_strings(
            [existing.canonical_key, existing.term, existing.core_claim, existing.summary],
            existing.aliases if isinstance(existing.aliases, list) else [],
            existing.semantic_fingerprint if isinstance(existing.semantic_fingerprint, list) else [],
        )
        heuristic_score = _best_similarity(query_texts, references)
        if heuristic_score <= 0:
            continue
        source = "global"
        if paper_id and existing.paper_id == paper_id:
            heuristic_score += 0.03
            source = "same_paper"
        scored.append(
            {
                "id": str(existing.id),
                "entity": existing,
                "texts": _prepare_similarity_texts(references),
                "heuristic_score": heuristic_score,
                "source": source,
            }
        )

    reranked = _rerank_similarity_candidates(
        query_texts=query_texts,
        candidate_groups=scored,
        agent_name="canonicalization_similarity",
    )
    return [
        serialize_knowledge_unit_candidate(
            item["entity"],
            score=round(float(item.get("score", item.get("heuristic_score", 0.0))), 4),
            source=str(item.get("source", "global")),
        )
        for item in reranked[:limit]
    ]


def filter_existing_knowledge_units_for_note(
    *,
    note_units: list[ExtractedUnit],
    existing_knowledge_units: list[dict[str, object]],
    limit: int = 8,
) -> list[dict[str, object]]:
    unit_candidates: list[str] = []
    for unit in note_units:
        unit_candidates.append(unit.canonical_name)
        unit_candidates.extend(unit.aliases)
        unit_candidates.extend(unit.keywords)
        unit_candidates.append(unit.description)
    query_texts = _prepare_similarity_texts(unit_candidates)
    if not query_texts:
        return []

    scored_candidates: list[dict[str, object]] = []
    for index, candidate in enumerate(existing_knowledge_units, start=1):
        if not isinstance(candidate, dict):
            continue
        references = _merge_unique_strings(
            [
                candidate.get("canonical_key"),
                candidate.get("term"),
                candidate.get("core_claim"),
                candidate.get("summary"),
            ],
            candidate.get("aliases") if isinstance(candidate.get("aliases"), list) else [],
            candidate.get("semantic_fingerprint") if isinstance(candidate.get("semantic_fingerprint"), list) else [],
        )
        heuristic_score = _best_similarity(query_texts, references)
        if heuristic_score <= 0:
            continue
        scored_candidates.append(
            {
                "id": str(candidate.get("knowledge_unit_id") or candidate.get("id") or candidate.get("canonical_key") or index),
                "payload": dict(candidate),
                "texts": _prepare_similarity_texts(references),
                "heuristic_score": heuristic_score,
            }
        )

    reranked = _rerank_similarity_candidates(
        query_texts=query_texts,
        candidate_groups=scored_candidates,
        agent_name="retrieved_unit_similarity",
        rerank_limit=limit,
    )
    results: list[dict[str, object]] = []
    for item in reranked[:limit]:
        payload = dict(item["payload"])
        payload["score"] = round(float(item.get("score", item.get("heuristic_score", 0.0))), 4)
        results.append(payload)
    return results


def build_graph_patch(
    *,
    notes: list[StructuredNote],
    note_units: dict[str, list[ExtractedUnit]],
    canonicalization_decisions: dict[str, list[CanonicalDecision]],
    relation_decisions: dict[str, list[RelationDecision]],
) -> tuple[GraphPatch, list[AgentDecisionLog]]:
    patch = GraphPatch()
    provenance_entries: list[AgentDecisionLog] = []
    note_ids = {note.note_id for note in notes}

    for note in notes:
        patch.notes_to_create.append(GraphPatchNoteRef(note_id=note.note_id, topic_key=note.topic_key))
        provenance_entries.append(
            AgentDecisionLog(
                agent_name="graph_update_agent",
                note_id=note.note_id,
                decision_type="note_registered",
                payload={"topic_key": note.topic_key},
            )
        )

    for note_id, units in note_units.items():
        decisions_by_unit = {
            decision.source_unit_id: decision for decision in canonicalization_decisions.get(note_id, [])
        }
        for unit in units:
            decision = decisions_by_unit.get(unit.unit_id)
            action = decision.action if decision is not None else CanonicalizationAction.CREATE_NEW
            target_unit_id = decision.target_unit_id if decision is not None else None
            target_canonical_key = decision.target_canonical_key if decision is not None else None
            if action == CanonicalizationAction.SOFT_LINK:
                action = CanonicalizationAction.CREATE_NEW
                target_unit_id = None
                target_canonical_key = None
            op = GraphPatchUnitOp(
                note_id=note_id,
                source_unit_id=unit.unit_id,
                action=action,
                target_unit_id=target_unit_id,
                target_canonical_key=target_canonical_key,
                payload=unit.model_dump(mode="json"),
            )
            if action == CanonicalizationAction.MERGE:
                patch.units_to_merge.append(op)
            elif action == CanonicalizationAction.REUSE:
                patch.units_to_link.append(op)
            else:
                patch.units_to_create.append(op)
            provenance_entries.append(
                AgentDecisionLog(
                    agent_name="graph_update_agent",
                    note_id=note_id,
                    decision_type="unit_op",
                    payload=op.model_dump(mode="json"),
                )
            )

    for note_id, relations in relation_decisions.items():
        if note_id not in note_ids:
            continue
        for relation in relations:
            op = GraphPatchRelationOp(
                note_id=note_id,
                from_unit_ref=relation.from_unit_ref,
                relation_type=relation.relation_type,
                to_unit_ref=relation.to_unit_ref,
                payload=relation.model_dump(mode="json"),
            )
            patch.relations_to_create.append(op)
            provenance_entries.append(
                AgentDecisionLog(
                    agent_name="graph_update_agent",
                    note_id=note_id,
                    decision_type="relation_op",
                    payload=op.model_dump(mode="json"),
                )
            )

    patch.provenance_entries = provenance_entries
    return patch, provenance_entries


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


def _sanitize_knowledge_unit_payload(
    payload: dict[str, object] | None,
    *,
    source_paper_ids: list[str] | None = None,
) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    sanitized: dict[str, object] = {}

    related_terms = source.get("related_terms")
    if isinstance(related_terms, list):
        sanitized["related_terms"] = related_terms

    slots = source.get("slots")
    if isinstance(slots, dict):
        sanitized["slots"] = slots

    merged_source_paper_ids = _merge_unique_strings(
        source.get("source_paper_ids") if isinstance(source.get("source_paper_ids"), list) else [],
        source_paper_ids or [],
        limit=32,
    )
    if merged_source_paper_ids:
        sanitized["source_paper_ids"] = merged_source_paper_ids

    return sanitized


def _knowledge_unit_from_patch_payload(note: Note, payload: dict[str, object]) -> dict[str, object]:
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
        "related_terms": _merge_unique_strings(aliases, keywords),
        "slots": slots,
        "source_paper_ids": [note.paper_id] if note.paper_id else [],
    }


def _serialize_existing_knowledge_unit_for_merge(existing: KnowledgeUnit) -> dict[str, object]:
    payload = existing.payload if isinstance(existing.payload, dict) else {}
    return {
        "unit_type": existing.unit_type,
        "term": existing.term,
        "canonical_key": existing.canonical_key,
        "core_claim": existing.core_claim,
        "summary": existing.summary,
        "aliases": existing.aliases if isinstance(existing.aliases, list) else [],
        "semantic_fingerprint": existing.semantic_fingerprint if isinstance(existing.semantic_fingerprint, list) else [],
        "related_terms": payload.get("related_terms") if isinstance(payload.get("related_terms"), list) else [],
        "slots": payload.get("slots") if isinstance(payload.get("slots"), dict) else {},
        "source_paper_ids": payload.get("source_paper_ids") if isinstance(payload.get("source_paper_ids"), list) else [],
    }


def _sanitize_llm_merged_unit(
    *,
    existing: KnowledgeUnit,
    note: Note,
    note_payload: dict[str, object],
    merged_unit: dict[str, object],
) -> dict[str, object]:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}
    existing_payload = existing.payload if isinstance(existing.payload, dict) else {}

    incoming_term = _clean_text(knowledge_unit.get("term"))
    incoming_core_claim = _clean_text(knowledge_unit.get("core_claim"))
    incoming_summary = _clean_text(note_payload.get("summary"))
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
        [incoming_term] if incoming_term and _normalize_text(incoming_term) != _normalize_text(term) else [],
        limit=32,
    )
    semantic_fingerprint = _merge_unique_strings(
        existing.semantic_fingerprint if isinstance(existing.semantic_fingerprint, list) else [],
        merged_unit.get("semantic_fingerprint") if isinstance(merged_unit.get("semantic_fingerprint"), list) else [],
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        [note_payload.get("topic_key"), incoming_term],
        limit=24,
    )
    related_terms = _merge_unique_strings(
        existing_payload.get("related_terms") if isinstance(existing_payload.get("related_terms"), list) else [],
        merged_unit.get("related_terms") if isinstance(merged_unit.get("related_terms"), list) else [],
        incoming_related_terms,
        limit=32,
    )
    slots = dict(existing_payload.get("slots")) if isinstance(existing_payload.get("slots"), dict) else {}
    llm_slots = merged_unit.get("slots") if isinstance(merged_unit.get("slots"), dict) else {}
    for key, value in {**incoming_slots, **llm_slots}.items():
        if value in (None, "", [], {}):
            continue
        slots[_clean_text(key)] = value
    source_paper_ids = _merge_unique_strings(
        existing_payload.get("source_paper_ids") if isinstance(existing_payload.get("source_paper_ids"), list) else [],
        merged_unit.get("source_paper_ids") if isinstance(merged_unit.get("source_paper_ids"), list) else [],
        [note.paper_id] if note.paper_id else [],
        limit=32,
    )
    core_claim = _clean_text(merged_unit.get("core_claim")) or _merge_distinct_texts(existing.core_claim, incoming_core_claim)
    summary = _clean_text(merged_unit.get("summary")) or _merge_distinct_texts(existing.summary, incoming_summary)

    return {
        "unit_type": unit_type,
        "term": term,
        "canonical_key": canonical_key,
        "core_claim": core_claim,
        "summary": summary,
        "aliases": aliases,
        "semantic_fingerprint": semantic_fingerprint,
        "payload": {
            **existing_payload,
            "related_terms": related_terms,
            "slots": slots,
            "source_paper_ids": source_paper_ids,
        },
    }


def _merge_existing_knowledge_unit_with_llm(
    *,
    existing: KnowledgeUnit,
    note: Note,
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
            [knowledge_unit.get("term")],
            limit=32,
        ),
        "semantic_fingerprint": _merge_unique_strings(
            dedupe_hints.get("semantic_fingerprint")
            if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
            else [],
            [note_payload.get("topic_key"), knowledge_unit.get("term")],
            limit=24,
        ),
        "related_terms": knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
        "slots": knowledge_unit.get("slots") if isinstance(knowledge_unit.get("slots"), dict) else {},
        "source_paper_ids": [note.paper_id] if note.paper_id else [],
    }

    prompt_payload = {
        "task": "Merge the incoming unit into the existing canonical unit because they refer to the same underlying object.",
        "rules": [
            "Return JSON only.",
            "Do not invent facts not supported by either input.",
            "Prefer one clean merged core_claim and one clean merged summary instead of concatenating both verbatim.",
            "Keep the canonical identity stable unless the incoming term is clearly a better canonical label.",
            "Aliases, semantic_fingerprint, related_terms, source_paper_ids should be deduplicated lists.",
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
        note=note,
        note_payload=note_payload,
        merged_unit=merged_unit,
    )


def _merge_into_existing_knowledge_unit_fallback(
    existing: KnowledgeUnit,
    note: Note,
    note_payload: dict[str, object],
) -> None:
    knowledge_unit = note_payload.get("knowledge_unit") if isinstance(note_payload.get("knowledge_unit"), dict) else {}
    dedupe_hints = note_payload.get("dedupe_hints") if isinstance(note_payload.get("dedupe_hints"), dict) else {}

    incoming_term = _clean_text(knowledge_unit.get("term"))
    incoming_core_claim = _clean_text(knowledge_unit.get("core_claim"))
    incoming_summary = _clean_text(note_payload.get("summary"))
    incoming_aliases = _merge_unique_strings(
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else [],
        [incoming_term] if incoming_term and _normalize_text(incoming_term) != _normalize_text(existing.term) else [],
        limit=32,
    )
    incoming_fingerprint = _merge_unique_strings(
        dedupe_hints.get("semantic_fingerprint")
        if isinstance(dedupe_hints.get("semantic_fingerprint"), list)
        else [],
        [note_payload.get("topic_key"), incoming_term],
        limit=24,
    )

    existing.unit_type = existing.unit_type or (_clean_text(knowledge_unit.get("unit_type")) or "concept")
    existing.term = existing.term or incoming_term
    existing.core_claim = _merge_distinct_texts(existing.core_claim, incoming_core_claim)
    existing.summary = _merge_distinct_texts(existing.summary, incoming_summary)
    existing.canonical_key = existing.canonical_key or _normalize_key(note_payload.get("topic_key") or incoming_term)
    existing.aliases = _merge_unique_strings(existing.aliases if isinstance(existing.aliases, list) else [], incoming_aliases, limit=32)
    existing.semantic_fingerprint = _merge_unique_strings(
        existing.semantic_fingerprint if isinstance(existing.semantic_fingerprint, list) else [],
        incoming_fingerprint,
        limit=24,
    )

    next_payload = dict(existing.payload) if isinstance(existing.payload, dict) else {}
    incoming_related_terms = (
        knowledge_unit.get("related_terms") if isinstance(knowledge_unit.get("related_terms"), list) else []
    )
    merged_related_terms = _merge_unique_strings(
        next_payload.get("related_terms") if isinstance(next_payload.get("related_terms"), list) else [],
        incoming_related_terms,
        limit=32,
    )
    if merged_related_terms:
        next_payload["related_terms"] = merged_related_terms

    merged_slots = dict(next_payload.get("slots")) if isinstance(next_payload.get("slots"), dict) else {}
    incoming_slots = knowledge_unit.get("slots") if isinstance(knowledge_unit.get("slots"), dict) else {}
    for key, value in incoming_slots.items():
        if value in (None, "", [], {}):
            continue
        merged_slots[key] = value
    if merged_slots:
        next_payload["slots"] = merged_slots

    source_paper_ids = _merge_unique_strings(
        next_payload.get("source_paper_ids") if isinstance(next_payload.get("source_paper_ids"), list) else [],
        [note.paper_id] if note.paper_id else [],
        limit=32,
    )
    if source_paper_ids:
        next_payload["source_paper_ids"] = source_paper_ids
    existing.payload = _sanitize_knowledge_unit_payload(next_payload)


def _merge_into_existing_knowledge_unit(
    existing: KnowledgeUnit,
    note: Note,
    note_payload: dict[str, object],
) -> None:
    merged = _merge_existing_knowledge_unit_with_llm(existing=existing, note=note, note_payload=note_payload)
    if merged is None:
        _merge_into_existing_knowledge_unit_fallback(existing, note, note_payload)
        return

    existing.unit_type = _clean_text(merged.get("unit_type")) or existing.unit_type
    existing.term = _clean_text(merged.get("term")) or existing.term
    existing.core_claim = _clean_text(merged.get("core_claim")) or existing.core_claim
    existing.summary = _clean_text(merged.get("summary")) or existing.summary
    existing.canonical_key = _clean_text(merged.get("canonical_key")) or existing.canonical_key
    existing.aliases = merged.get("aliases") if isinstance(merged.get("aliases"), list) else existing.aliases
    existing.semantic_fingerprint = (
        merged.get("semantic_fingerprint")
        if isinstance(merged.get("semantic_fingerprint"), list)
        else existing.semantic_fingerprint
    )
    existing.payload = (
        _sanitize_knowledge_unit_payload(merged.get("payload"))
        if isinstance(merged.get("payload"), dict)
        else existing.payload
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
        "knowledge_unit": _knowledge_unit_from_patch_payload(note, payload),
        "dedupe_hints": {
            "aliases": payload.get("aliases") if isinstance(payload.get("aliases"), list) else [],
            "semantic_fingerprint": payload.get("keywords") if isinstance(payload.get("keywords"), list) else [],
        },
    }
    # The creation process and link addition process are performed separately.
    if op.action == CanonicalizationAction.CREATE_NEW:
        # Creation Process
        created = _create_new_knowledge_unit(db, note, note_payload)
        if created is not None:
            # Link Addition Process
            _ensure_note_link(db, created.id, note.id)
        return created
    if op.target_unit_id is None:
        return None

    existing = db.query(KnowledgeUnit).filter(KnowledgeUnit.id == op.target_unit_id).first()
    if existing is None:
        return None

    _ensure_note_link(db, existing.id, note.id)
    if op.action == CanonicalizationAction.MERGE:
        _merge_into_existing_knowledge_unit(existing, note, note_payload)
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


def persist_pipeline_audit_records(
    db: Session,
    *,
    trace_id: str,
    paper_id: str | None,
    session_id: int | None,
    pipeline_payload: dict[str, object],
    notes_by_ref: dict[str, Note],
) -> int:
    run = AgentRun(
        trace_id=trace_id,
        paper_id=paper_id,
        session_id=session_id,
        payload=pipeline_payload,
        status="completed",
    )
    db.add(run)
    db.flush()

    note_units = pipeline_payload.get("note_units") if isinstance(pipeline_payload.get("note_units"), dict) else {}
    for note_ref, units in note_units.items():
        note = notes_by_ref.get(note_ref)
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            db.add(
                NoteUnitCandidate(
                    agent_run_id=run.id,
                    note_ref=note_ref,
                    note_id=note.id if note is not None else None,
                    unit_ref=_clean_text(unit.get("unit_id")),
                    candidate_key=_normalize_key(unit.get("canonical_name")),
                    payload=unit,
                )
            )

    canonicalization = pipeline_payload.get("canonicalization_decisions") if isinstance(pipeline_payload.get("canonicalization_decisions"), dict) else {}
    for note_ref, decisions in canonicalization.items():
        note = notes_by_ref.get(note_ref)
        if not isinstance(decisions, list):
            continue
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            db.add(
                UnitCanonicalizationDecision(
                    agent_run_id=run.id,
                    note_ref=note_ref,
                    note_id=note.id if note is not None else None,
                    source_unit_ref=_clean_text(decision.get("source_unit_id")),
                    action=_clean_text(decision.get("action")) or "create_new",
                    target_unit_id=decision.get("target_unit_id") if isinstance(decision.get("target_unit_id"), int) else None,
                    target_canonical_key=_clean_text(decision.get("target_canonical_key")),
                    confidence=float(decision.get("confidence") or 0),
                    payload=decision,
                )
            )

    relation_decisions = pipeline_payload.get("relation_decisions") if isinstance(pipeline_payload.get("relation_decisions"), dict) else {}
    for note_ref, decisions in relation_decisions.items():
        note = notes_by_ref.get(note_ref)
        if not isinstance(decisions, list):
            continue
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            db.add(
                UnitRelationDecision(
                    agent_run_id=run.id,
                    note_ref=note_ref,
                    note_id=note.id if note is not None else None,
                    from_unit_ref=_clean_text(decision.get("from_unit_ref")),
                    relation_type=_clean_text(decision.get("relation_type")) or RelationType.RELATED_TO.value,
                    to_unit_ref=_clean_text(decision.get("to_unit_ref")),
                    confidence=float(decision.get("confidence") or 0),
                    payload=decision,
                )
            )

    graph_logs = pipeline_payload.get("graph_sync_results") if isinstance(pipeline_payload.get("graph_sync_results"), list) else []
    for item in graph_logs:
        if not isinstance(item, dict):
            continue
        note_ref = _clean_text(item.get("note_ref"))
        note = notes_by_ref.get(note_ref)
        db.add(
            GraphUpdateLog(
                agent_run_id=run.id,
                note_ref=note_ref,
                note_id=note.id if note is not None else None,
                status="applied",
                payload=item,
                error="",
            )
        )

    return run.id
