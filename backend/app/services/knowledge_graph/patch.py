from __future__ import annotations

from ...agents.schemas import (
    CanonicalDecision,
    CanonicalizationAction,
    ExtractedUnit,
    GraphPatch,
    GraphPatchRelationOp,
    GraphPatchUnitOp,
    RelationDecision,
    StructuredNote,
)


def build_graph_patch(
    *,
    notes: list[StructuredNote],
    note_units: dict[str, list[ExtractedUnit]],
    canonicalization_decisions: dict[str, list[CanonicalDecision]],
    relation_decisions: dict[str, list[RelationDecision]],
) -> GraphPatch:
    patch = GraphPatch()
    note_ids = {note.note_id for note in notes}

    for note_id, units in note_units.items():
        decisions_by_unit = {
            decision.source_unit_id: decision for decision in canonicalization_decisions.get(note_id, [])
        }
        for unit in units:
            decision = decisions_by_unit.get(unit.unit_id)
            action = decision.action if decision is not None else CanonicalizationAction.CREATE_NEW
            target_unit_id = decision.target_unit_id if decision is not None else None
            if action == CanonicalizationAction.SOFT_LINK:
                action = CanonicalizationAction.CREATE_NEW
                target_unit_id = None
            op = GraphPatchUnitOp(
                note_id=note_id,
                source_unit_id=unit.unit_id,
                action=action,
                target_unit_id=target_unit_id,
                unit_type=unit.type,
                canonical_name=unit.canonical_name,
                description=unit.description,
                aliases=list(unit.aliases),
                keywords=list(unit.keywords),
                slots=dict(unit.slots),
            )
            if action == CanonicalizationAction.MERGE:
                patch.units_to_merge.append(op)
            elif action == CanonicalizationAction.REUSE:
                patch.units_to_link.append(op)
            else:
                patch.units_to_create.append(op)

    for note_id, relations in relation_decisions.items():
        if note_id not in note_ids:
            continue
        for relation in relations:
            op = GraphPatchRelationOp(
                note_id=note_id,
                from_unit_ref=relation.from_unit_ref,
                relation_type=relation.relation_type,
                to_unit_ref=relation.to_unit_ref,
                confidence=relation.confidence,
            )
            patch.relations_to_create.append(op)

    return patch
