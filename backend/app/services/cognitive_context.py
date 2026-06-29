from __future__ import annotations

from sqlalchemy.orm import Session

from ..db import KnowledgeUnit, KnowledgeUnitNoteLink, Note
from .knowledge_graph.common import _best_similarity, _merge_unique_strings, _prepare_similarity_texts


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _truncate(value: object, *, max_chars: int = 700) -> str:
    text = _clean_text(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _safe_list(value: object, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)][:limit]


def _note_scope(note: object, *, paper_id: str | None, session_id: int | None) -> str:
    if paper_id and session_id is not None and note.paper_id == paper_id and note.session_id == session_id:
        return "same_session"
    if paper_id and note.paper_id == paper_id:
        return "same_paper"
    return "global"


def _scope_boost(scope: str) -> float:
    if scope == "same_session":
        return 0.45
    if scope == "same_paper":
        return 0.25
    return 0.0


def _minimum_note_similarity(scope: str) -> float:
    if scope == "same_session":
        return 0.35
    if scope == "same_paper":
        return 0.35
    return 0.4


def _dedupe_hints(note: object) -> dict[str, object]:
    dedupe_hints = getattr(note, "dedupe_hints", {})
    return dedupe_hints if isinstance(dedupe_hints, dict) else {}


def _retrieval_description(note: object) -> str:
    return _clean_text(_dedupe_hints(note).get("retrieval_description"))


def _note_index_references(note: object) -> list[str]:
    dedupe_hints = _dedupe_hints(note)
    return _merge_unique_strings(
        [
            _retrieval_description(note),
            getattr(note, "title", ""),
            getattr(note, "topic_key", ""),
        ],
        dedupe_hints.get("aliases") if isinstance(dedupe_hints.get("aliases"), list) else [],
        dedupe_hints.get("semantic_fingerprint") if isinstance(dedupe_hints.get("semantic_fingerprint"), list) else [],
    )


def _note_candidate(note: Note, *, score: float, source_scope: str) -> dict[str, object]:
    return {
        "candidate_id": f"note:{note.id}",
        "kind": "note",
        "source_scope": source_scope,
        "score": round(score, 4),
        "note_id": note.id,
        "title": note.title,
        "topic_key": note.topic_key,
        "summary": note.summary,
        "retrieval_description": _retrieval_description(note),
        "content_excerpt": _truncate(note.content),
        "cognitive_state": note.cognitive_state if isinstance(note.cognitive_state, dict) else {},
        "follow_up_questions": _safe_list(note.follow_up_questions, limit=3),
        "paper_id": note.paper_id,
        "session_id": note.session_id,
    }


def _unit_references(unit: KnowledgeUnit) -> list[str]:
    return _merge_unique_strings(
        [unit.canonical_key, unit.term, unit.core_claim, unit.summary],
        unit.aliases if isinstance(unit.aliases, list) else [],
        unit.related_terms if isinstance(unit.related_terms, list) else [],
    )


def _unit_scope(unit: KnowledgeUnit, *, paper_id: str | None) -> str:
    if paper_id and unit.paper_id == paper_id:
        return "same_paper"
    return "global"


def _linked_note_summary(note: Note) -> dict[str, object]:
    return {
        "note_id": note.id,
        "title": note.title,
        "summary": note.summary,
        "cognitive_state": note.cognitive_state if isinstance(note.cognitive_state, dict) else {},
        "follow_up_questions": _safe_list(note.follow_up_questions, limit=2),
    }


def collect_cognitive_context_candidates(
    db: Session,
    *,
    question: str,
    quote: str,
    paper_id: str | None,
    session_id: int | None,
    limit: int = 18,
) -> list[dict[str, object]]:
    if not paper_id:
        return []

    query_texts = _prepare_similarity_texts([question, quote])
    if not query_texts:
        return []

    note_index_rows = (
        db.query(Note.id, Note.title, Note.topic_key, Note.dedupe_hints, Note.paper_id, Note.session_id)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .all()
    )
    note_index_matches: list[dict[str, object]] = []
    for note in note_index_rows:
        source_scope = _note_scope(note, paper_id=paper_id, session_id=session_id)
        references = _prepare_similarity_texts(_note_index_references(note))
        similarity = _best_similarity(query_texts, references)
        score = similarity + _scope_boost(source_scope)
        if similarity <= _minimum_note_similarity(source_scope):
            continue
        note_index_matches.append(
            {
                "note_id": note.id,
                "source_scope": source_scope,
                "score": score,
            }
        )

    note_index_matches.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    matched_note_ids = [int(item["note_id"]) for item in note_index_matches[:limit] if isinstance(item.get("note_id"), int)]
    matched_notes = db.query(Note).filter(Note.id.in_(matched_note_ids)).all() if matched_note_ids else []
    note_by_id = {note.id: note for note in matched_notes}
    note_match_by_id = {int(item["note_id"]): item for item in note_index_matches if isinstance(item.get("note_id"), int)}

    candidates: list[dict[str, object]] = []
    for note_id in matched_note_ids:
        note = note_by_id.get(note_id)
        match = note_match_by_id.get(note_id)
        if note is None or match is None:
            continue
        candidates.append(
            _note_candidate(
                note,
                score=float(match.get("score", 0.0)),
                source_scope=str(match.get("source_scope") or "global"),
            )
        )

    unit_links: dict[int, list[int]] = {}
    for link in db.query(KnowledgeUnitNoteLink).all():
        unit_links.setdefault(link.knowledge_unit_id, []).append(link.note_id)
    linked_note_cache: dict[int, Note] = {}

    def linked_note_summaries(note_ids: list[int]) -> list[dict[str, object]]:
        missing_note_ids = [note_id for note_id in note_ids if note_id not in linked_note_cache]
        if missing_note_ids:
            for note in db.query(Note).filter(Note.id.in_(missing_note_ids)).all():
                linked_note_cache[note.id] = note
        return [
            _linked_note_summary(linked_note_cache[note_id])
            for note_id in note_ids
            if note_id in linked_note_cache
        ]

    for unit in db.query(KnowledgeUnit).order_by(KnowledgeUnit.updated_at.desc(), KnowledgeUnit.id.asc()).all():
        source_scope = _unit_scope(unit, paper_id=paper_id)
        references = _prepare_similarity_texts(_unit_references(unit))
        similarity = _best_similarity(query_texts, references)
        score = similarity + _scope_boost(source_scope)
        if similarity <= 0:
            continue
        if similarity <= 0.16 and source_scope == "global":
            continue
        linked_notes = linked_note_summaries(unit_links.get(unit.id, []))
        candidates.append(
            {
                "candidate_id": f"knowledge_unit:{unit.id}",
                "kind": "knowledge_unit",
                "source_scope": source_scope,
                "score": round(score, 4),
                "knowledge_unit_id": unit.id,
                "term": unit.term,
                "canonical_key": unit.canonical_key,
                "unit_type": unit.unit_type,
                "core_claim": unit.core_claim,
                "summary": unit.summary,
                "aliases": _safe_list(unit.aliases),
                "related_terms": _safe_list(unit.related_terms),
                "paper_id": unit.paper_id,
                "linked_notes": linked_notes[:3],
            }
        )

    candidates.sort(
        key=lambda item: (
            float(item.get("score", 0.0)),
            1 if item.get("source_scope") == "same_session" else 0,
            1 if item.get("source_scope") == "same_paper" else 0,
        ),
        reverse=True,
    )
    return candidates[:limit]
