from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class UnitType(str, Enum):
    CONCEPT = "concept"
    CLAIM = "claim"
    METHOD = "method"
    QUESTION = "question"
    DISTINCTION = "distinction"


class UserState(str, Enum):
    MENTIONED = "mentioned"
    EXPOSED = "exposed"
    CONFUSED = "confused"
    PARTIAL_UNDERSTANDING = "partial_understanding"
    UNDERSTOOD = "understood"
    MISALIGNED = "misaligned"


class CanonicalizationAction(str, Enum):
    MERGE = "merge"
    REUSE = "reuse"
    CREATE_NEW = "create_new"
    SOFT_LINK = "soft_link"


class RelationType(str, Enum):
    ASKS_ABOUT = "asks_about"
    RELATED_TO = "related_to"
    CONFUSED_WITH = "confused_with"
    PREREQUISITE_OF = "prerequisite_of"
    USED_FOR = "used_for"
    SAME_AS = "same_as"


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ModelCallParams(BaseModel):
    model: str | None = None
    temperature: float | None = None
    response_format: dict[str, Any] | None = None
    timeout_seconds: float | None = None
    max_tokens: int | None = None


class ModelInvocationResult(BaseModel):
    text: str
    raw_response: dict[str, Any] | None = None
    token_usage: TokenUsage | None = None
    latency_ms: int
    model: str | None = None
    error: str | None = None


class LLMInvocationLog(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trace_id: str
    session_id: str | None = None
    agent_name: str
    messages: list[ModelMessage]
    raw_response: dict[str, Any] | None = None
    pre_parse_text: str = ""
    token_usage: TokenUsage | None = None
    latency_ms: int = 0
    error: str | None = None


class ParseError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ParseResult(BaseModel):
    ok: bool
    data: Any | None = None
    extracted_text: str | None = None
    error: ParseError | None = None
    fallback_used: bool = False


class PaperMetadata(BaseModel):
    title: str
    authors: str
    research_topic: str
    journal: str
    publication_date: str
    summary: str


class CognitiveState(BaseModel):
    state: UserState
    confidence: float
    mental_model: str = ""


class DedupeHints(BaseModel):
    aliases: list[str] = Field(default_factory=list)
    semantic_fingerprint: list[str] = Field(default_factory=list)


class UnitRelationCandidate(BaseModel):
    target_unit_ref: str
    relation_type: RelationType


class StructuredNote(BaseModel):
    note_id: str
    title: str
    topic_key: str
    summary: str
    content: str
    cognitive_state: CognitiveState
    follow_up_questions: list[str] = Field(default_factory=list)
    dedupe_hints: DedupeHints = Field(default_factory=DedupeHints)


class StructuredNotesPayload(BaseModel):
    notes: list[StructuredNote] = Field(default_factory=list)


class ExtractedUnit(BaseModel):
    unit_id: str
    source_note_id: str
    type: UnitType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)
    local_relations: list[UnitRelationCandidate] = Field(default_factory=list)


class ExtractedUnitsPayload(BaseModel):
    units: list[ExtractedUnit] = Field(default_factory=list)


class RetrievedUnitCandidate(BaseModel):
    knowledge_unit_id: int | None = None
    canonical_key: str = ""
    unit_type: str = "concept"
    term: str = ""
    core_claim: str = ""
    summary: str = ""
    aliases: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    source: str = "global"


class CanonicalDecision(BaseModel):
    source_unit_id: str
    action: CanonicalizationAction
    target_unit_id: int | None = None
    target_canonical_key: str | None = None
    confidence: float = 0.0
    reason: str = ""


class CanonicalDecisionsPayload(BaseModel):
    decisions: list[CanonicalDecision] = Field(default_factory=list)


class RelationDecision(BaseModel):
    from_unit_ref: str
    relation_type: RelationType
    to_unit_ref: str
    confidence: float = 0.0


class RelationDecisionsPayload(BaseModel):
    relations: list[RelationDecision] = Field(default_factory=list)


class GraphPatchUnitOp(BaseModel):
    note_id: str
    source_unit_id: str
    action: CanonicalizationAction
    target_unit_id: int | None = None
    unit_type: UnitType = UnitType.CONCEPT
    canonical_name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)


class GraphPatchRelationOp(BaseModel):
    note_id: str
    from_unit_ref: str
    relation_type: RelationType
    to_unit_ref: str
    confidence: float = 0.0


class GraphPatch(BaseModel):
    units_to_create: list[GraphPatchUnitOp] = Field(default_factory=list)
    units_to_update: list[GraphPatchUnitOp] = Field(default_factory=list)
    units_to_merge: list[GraphPatchUnitOp] = Field(default_factory=list)
    units_to_link: list[GraphPatchUnitOp] = Field(default_factory=list)
    relations_to_create: list[GraphPatchRelationOp] = Field(default_factory=list)
    relations_to_update: list[GraphPatchRelationOp] = Field(default_factory=list)


class SessionNotesPipelineResult(BaseModel):
    notes: list[StructuredNote] = Field(default_factory=list)
    note_units: dict[str, list[ExtractedUnit]] = Field(default_factory=dict)
    canonicalization_decisions: dict[str, list[CanonicalDecision]] = Field(default_factory=dict)
    relation_decisions: dict[str, list[RelationDecision]] = Field(default_factory=dict)
    graph_patch: GraphPatch = Field(default_factory=GraphPatch)
