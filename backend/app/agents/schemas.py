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


class FacetType(str, Enum):
    DEFINITION = "definition"
    MECHANISM = "mechanism"
    LIMITATION = "limitation"
    COMPARISON = "comparison"
    IMPLICATION = "implication"
    QUESTION = "question"


class UserState(str, Enum):
    MENTIONED = "mentioned"
    EXPOSED = "exposed"
    CONFUSED = "confused"
    PARTIAL_UNDERSTANDING = "partial_understanding"
    UNDERSTOOD = "understood"
    MISALIGNED = "misaligned"


class UserSignalType(str, Enum):
    UNDERSTANDING = "understanding"
    QUESTION = "question"
    CONFUSION = "confusion"
    MISCONCEPTION = "misconception"
    DISTINCTION = "distinction"
    BOUNDARY_AWARENESS = "boundary_awareness"


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


class ModelInvocationRequest(BaseModel):
    trace_id: str
    session_id: str | None = None
    agent_name: str
    messages: list[ModelMessage]
    params: ModelCallParams = Field(default_factory=ModelCallParams)


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


class AgentExecutionLog(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trace_id: str
    session_id: str | None = None
    agent_name: str
    step_name: str
    success: bool
    latency_ms: int
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class QAResponse(BaseModel):
    answer: str


class KnowledgeFacet(BaseModel):
    facet_type: FacetType
    text: str


class KnowledgeUnit(BaseModel):
    unit_type: UnitType
    term: str
    core_claim: str
    facets: list[KnowledgeFacet] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)


class UserSignal(BaseModel):
    signal_type: UserSignalType
    text: str


class UserModelSignal(BaseModel):
    state: UserState
    confidence: float
    signals: list[UserSignal] = Field(default_factory=list)


class DedupeHints(BaseModel):
    aliases: list[str] = Field(default_factory=list)
    semantic_fingerprint: list[str] = Field(default_factory=list)


class SessionNote(BaseModel):
    note_id: str
    title: str
    topic_key: str
    summary: str
    content: str
    knowledge_unit: KnowledgeUnit
    user_model_signal: UserModelSignal
    open_questions: list[str] = Field(default_factory=list)
    dedupe_hints: DedupeHints = Field(default_factory=DedupeHints)


class SessionNotesPayload(BaseModel):
    notes: list[SessionNote] = Field(default_factory=list)


class UnitRelationCandidate(BaseModel):
    target_unit_ref: str
    relation_type: RelationType


class StructuredNote(BaseModel):
    note_id: str
    title: str
    topic_key: str
    summary: str
    content: str
    knowledge_unit: KnowledgeUnit
    user_model_signal: UserModelSignal
    open_questions: list[str] = Field(default_factory=list)
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
    semantic_fingerprint: list[str] = Field(default_factory=list)
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


class GraphPatchNoteRef(BaseModel):
    note_id: str
    topic_key: str = ""


class GraphPatchUnitOp(BaseModel):
    note_id: str
    source_unit_id: str
    action: CanonicalizationAction
    target_unit_id: int | None = None
    target_canonical_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class GraphPatchRelationOp(BaseModel):
    note_id: str
    from_unit_ref: str
    relation_type: RelationType
    to_unit_ref: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentDecisionLog(BaseModel):
    agent_name: str
    note_id: str | None = None
    decision_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class GraphPatch(BaseModel):
    notes_to_create: list[GraphPatchNoteRef] = Field(default_factory=list)
    notes_to_update: list[GraphPatchNoteRef] = Field(default_factory=list)
    units_to_create: list[GraphPatchUnitOp] = Field(default_factory=list)
    units_to_update: list[GraphPatchUnitOp] = Field(default_factory=list)
    units_to_merge: list[GraphPatchUnitOp] = Field(default_factory=list)
    units_to_link: list[GraphPatchUnitOp] = Field(default_factory=list)
    relations_to_create: list[GraphPatchRelationOp] = Field(default_factory=list)
    relations_to_update: list[GraphPatchRelationOp] = Field(default_factory=list)
    provenance_entries: list[AgentDecisionLog] = Field(default_factory=list)


class SessionNotesPipelineResult(BaseModel):
    notes: list[StructuredNote] = Field(default_factory=list)
    note_units: dict[str, list[ExtractedUnit]] = Field(default_factory=dict)
    canonicalization_decisions: dict[str, list[CanonicalDecision]] = Field(default_factory=dict)
    relation_decisions: dict[str, list[RelationDecision]] = Field(default_factory=dict)
    graph_patch: GraphPatch = Field(default_factory=GraphPatch)
    provenance_log: list[AgentDecisionLog] = Field(default_factory=list)
