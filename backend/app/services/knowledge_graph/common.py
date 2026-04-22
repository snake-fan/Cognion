from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from ...agents.model_adapter import OpenAIModelAdapter, default_log_sink

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
