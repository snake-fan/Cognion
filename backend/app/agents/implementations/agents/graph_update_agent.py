from __future__ import annotations

from time import perf_counter

from ...core.base import BaseAgent
from ...schemas import AgentDecisionLog, AgentExecutionLog, ParseResult
from ...state import NotesAgentState
from ....services.knowledge_graph import build_graph_patch


class GraphUpdateAgent(BaseAgent):
    name = "graph_update_agent"

    def build_messages(self, state: NotesAgentState):
        return []

    def parse_response(self, raw_text: str) -> ParseResult:
        return ParseResult(ok=True, data=None, extracted_text=raw_text)

    def apply_result(self, state: NotesAgentState, parsed: ParseResult) -> None:
        return None

    async def run(self, state: NotesAgentState) -> NotesAgentState:
        started = perf_counter()
        try:
            graph_patch, provenance_entries = build_graph_patch(
                notes=state.notes,
                note_units=state.note_units,
                canonicalization_decisions=state.canonicalization_decisions,
                relation_decisions=state.relation_decisions,
            )
            state.graph_patch = graph_patch
            state.add_provenance_entries(provenance_entries)
            state.provenance_log.append(
                AgentDecisionLog(
                    agent_name=self.name,
                    decision_type="graph_patch_built",
                    payload={"notes": len(state.notes)},
                )
            )
            state.final_result = {
                "notes": [note.model_dump(mode="json") for note in state.notes],
                "note_units": {
                    note_id: [unit.model_dump(mode="json") for unit in units]
                    for note_id, units in state.note_units.items()
                },
                "canonicalization_decisions": {
                    note_id: [decision.model_dump(mode="json") for decision in decisions]
                    for note_id, decisions in state.canonicalization_decisions.items()
                },
                "relation_decisions": {
                    note_id: [relation.model_dump(mode="json") for relation in relations]
                    for note_id, relations in state.relation_decisions.items()
                },
                "graph_patch": graph_patch.model_dump(mode="json"),
                "provenance_log": [entry.model_dump(mode="json") for entry in state.provenance_log],
            }
            success = True
            error_message = None
        except Exception as exc:
            state.add_error(self.name, exc)
            success = False
            error_message = str(exc)

        latency_ms = int((perf_counter() - started) * 1000)
        state.execution_logs.append(
            AgentExecutionLog(
                trace_id=state.trace_id,
                session_id=state.session_id,
                agent_name=self.name,
                step_name="run",
                success=success,
                latency_ms=latency_ms,
                error=error_message,
            )
        )
        return state
