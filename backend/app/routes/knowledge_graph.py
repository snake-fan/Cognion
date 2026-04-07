from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ChatSession,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeUnit,
    KnowledgeUnitNodeLink,
    KnowledgeUnitNoteLink,
    Note,
    Paper,
)
from .common import (
    knowledge_graph_edge_to_dict,
    knowledge_graph_node_to_dict,
    knowledge_unit_to_dict,
    note_to_dict,
    paper_to_dict,
    session_to_dict,
)

router = APIRouter()


@router.get("/knowledge-graph")
def get_knowledge_graph(db: Session = Depends(get_db)) -> dict[str, object]:
    nodes = db.query(KnowledgeGraphNode).order_by(KnowledgeGraphNode.updated_at.desc(), KnowledgeGraphNode.id.asc()).all()
    edges = db.query(KnowledgeGraphEdge).order_by(KnowledgeGraphEdge.id.asc()).all()
    knowledge_units = db.query(KnowledgeUnit).order_by(KnowledgeUnit.updated_at.desc(), KnowledgeUnit.id.asc()).all()
    unit_note_links = db.query(KnowledgeUnitNoteLink).all()
    unit_node_links = db.query(KnowledgeUnitNodeLink).all()

    note_ids = sorted({link.note_id for link in unit_note_links})
    paper_ids_from_notes = (
        {paper_id for (paper_id,) in db.query(Note.paper_id).filter(Note.id.in_(note_ids)).distinct().all() if paper_id}
        if note_ids
        else set()
    )
    session_ids = (
        sorted(
            {
                session_id
                for (session_id,) in db.query(Note.session_id).filter(Note.id.in_(note_ids)).distinct().all()
                if session_id is not None
            }
        )
        if note_ids
        else []
    )

    notes = db.query(Note).filter(Note.id.in_(note_ids)).all() if note_ids else []
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids_from_notes)).all() if paper_ids_from_notes else []
    sessions = db.query(ChatSession).filter(ChatSession.id.in_(session_ids)).all() if session_ids else []

    note_to_units: dict[int, list[int]] = {}
    for link in unit_note_links:
        note_to_units.setdefault(link.note_id, []).append(link.knowledge_unit_id)

    node_to_units: dict[int, list[int]] = {}
    unit_to_nodes: dict[int, list[int]] = {}
    for link in unit_node_links:
        node_to_units.setdefault(link.node_id, []).append(link.knowledge_unit_id)
        unit_to_nodes.setdefault(link.knowledge_unit_id, []).append(link.node_id)

    unit_to_notes: dict[int, list[int]] = {}
    for link in unit_note_links:
        unit_to_notes.setdefault(link.knowledge_unit_id, []).append(link.note_id)

    return {
        "nodes": [
            {
                **knowledge_graph_node_to_dict(node),
                "knowledge_unit_ids": node_to_units.get(node.id, []),
            }
            for node in nodes
        ],
        "edges": [knowledge_graph_edge_to_dict(edge) for edge in edges],
        "knowledge_units": [
            {
                **knowledge_unit_to_dict(unit),
                "node_ids": unit_to_nodes.get(unit.id, []),
                "note_ids": unit_to_notes.get(unit.id, []),
            }
            for unit in knowledge_units
        ],
        "notes": [
            {
                **note_to_dict(note),
                "knowledge_unit_ids": note_to_units.get(note.id, []),
            }
            for note in notes
        ],
        "papers": [paper_to_dict(paper) for paper in papers],
        "sessions": [session_to_dict(session) for session in sessions],
    }
