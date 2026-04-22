from __future__ import annotations

from sqlalchemy.orm import Session

from ...agents.schemas import (
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
    StructuredNote,
)
from ...db import AgentRun, GraphUpdateLog, Note, NoteUnitCandidate, UnitCanonicalizationDecision, UnitRelationDecision
from .common import _clean_text, _normalize_key


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
