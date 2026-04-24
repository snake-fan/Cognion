from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from ...agents.model_adapter import ModelAdapterError
from ...agents.schemas import ExtractedUnit, ModelCallParams, ModelMessage, RetrievedUnitCandidate
from ...db import KnowledgeUnit
from ..config import OPENAI_SIMILARITY_MODEL
from .common import (
    SIMILARITY_RERANK_LIMIT,
    _best_similarity,
    _clean_text,
    _get_similarity_adapter,
    _merge_unique_strings,
    _prepare_similarity_texts,
)


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


def serialize_knowledge_unit_candidate(unit: KnowledgeUnit, *, score: float = 0.0, source: str = "global") -> dict[str, object]:
    return RetrievedUnitCandidate(
        knowledge_unit_id=unit.id,
        canonical_key=unit.canonical_key,
        unit_type=unit.unit_type,
        term=unit.term,
        core_claim=unit.core_claim,
        summary=unit.summary,
        aliases=unit.aliases if isinstance(unit.aliases, list) else [],
        related_terms=unit.related_terms if isinstance(unit.related_terms, list) else [],
        slots=unit.slots if isinstance(unit.slots, dict) else {},
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
            existing.related_terms if isinstance(existing.related_terms, list) else [],
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
            candidate.get("related_terms") if isinstance(candidate.get("related_terms"), list) else [],
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
