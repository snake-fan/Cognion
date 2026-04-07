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


class GraphNodeType(str, Enum):
    CONCEPT = "Concept"
    CLAIM = "Claim"
    METHOD = "Method"
    QUESTION = "Question"


class GraphEdgeRelation(str, Enum):
    RELATED_TO = "RELATED_TO"
    EXPLAINS = "EXPLAINS"
    CONTRASTS_WITH = "CONTRASTS_WITH"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    RAISES = "RAISES"
    SUPPORTS = "SUPPORTS"


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


class EvidenceItem(BaseModel):
    source: Literal["user", "assistant"]
    quote: str


class GraphNodeSuggestion(BaseModel):
    node_type: GraphNodeType
    name: str


class GraphEdgeSuggestion(BaseModel):
    from_: str = Field(alias="from")
    relation: GraphEdgeRelation
    to: str


class GraphSuggestions(BaseModel):
    nodes: list[GraphNodeSuggestion] = Field(default_factory=list)
    edges: list[GraphEdgeSuggestion] = Field(default_factory=list)


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
    evidence: list[EvidenceItem] = Field(default_factory=list)
    graph_suggestions: GraphSuggestions = Field(default_factory=GraphSuggestions)
    open_questions: list[str] = Field(default_factory=list)
    dedupe_hints: DedupeHints = Field(default_factory=DedupeHints)


class SessionNotesPayload(BaseModel):
    notes: list[SessionNote] = Field(default_factory=list)
