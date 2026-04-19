from datetime import datetime

from sqlalchemy.orm import Session

from ..db import (
    ChatMessage,
    ChatSession,
    Folder,
    KnowledgeGraphEdge,
    KnowledgeUnit,
    Note,
    NoteFolder,
    Paper,
)


def paper_to_dict(paper: Paper) -> dict[str, str | int]:
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "research_topic": paper.research_topic,
        "journal": paper.journal,
        "publication_date": paper.publication_date,
        "original_filename": paper.original_filename,
        "file_path": paper.file_path,
        "summary": paper.summary,
        "created_at": paper.created_at.isoformat() if isinstance(paper.created_at, datetime) else "",
        "updated_at": paper.updated_at.isoformat() if isinstance(paper.updated_at, datetime) else "",
    }


def message_to_dict(message: ChatMessage) -> dict[str, str | int | None]:
    return {
        "id": message.id,
        "paper_id": message.paper_id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "quote": message.quote,
        "created_at": message.created_at.isoformat() if isinstance(message.created_at, datetime) else "",
    }


def session_to_dict(chat_session: ChatSession) -> dict[str, str | int]:
    return {
        "id": chat_session.id,
        "paper_id": chat_session.paper_id,
        "name": chat_session.name,
        "created_at": chat_session.created_at.isoformat() if isinstance(chat_session.created_at, datetime) else "",
        "updated_at": chat_session.updated_at.isoformat() if isinstance(chat_session.updated_at, datetime) else "",
    }


def ensure_default_session(db: Session, paper_id: str) -> ChatSession:
    existing = (
        db.query(ChatSession)
        .filter(ChatSession.paper_id == paper_id)
        .order_by(ChatSession.created_at.asc(), ChatSession.id.asc())
        .first()
    )
    if existing:
        return existing

    default_session = ChatSession(paper_id=paper_id, name="Session 1")
    db.add(default_session)
    db.commit()
    db.refresh(default_session)
    return default_session


def folder_to_dict(folder: Folder) -> dict[str, str | int | None]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at.isoformat() if isinstance(folder.created_at, datetime) else "",
        "updated_at": folder.updated_at.isoformat() if isinstance(folder.updated_at, datetime) else "",
    }


def build_folder_tree(
    folders: list[Folder],
    folder_ids_with_papers: set[int] | None = None,
) -> list[dict[str, object]]:
    occupied_folder_ids = folder_ids_with_papers or set()
    node_map: dict[int, dict[str, object]] = {}
    roots: list[dict[str, object]] = []

    for folder in folders:
        node_map[folder.id] = {
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_id,
            "children": [],
            "has_papers": folder.id in occupied_folder_ids,
        }

    for folder in folders:
        node = node_map[folder.id]
        parent_id = folder.parent_id
        if parent_id and parent_id in node_map:
            parent_node = node_map[parent_id]
            parent_children = parent_node["children"]
            if isinstance(parent_children, list):
                parent_children.append(node)
        else:
            roots.append(node)

    def mark_has_papers(node: dict[str, object]) -> bool:
        has_papers = bool(node.get("has_papers"))
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict) and mark_has_papers(child):
                    has_papers = True
        node["has_papers"] = has_papers
        return has_papers

    for root in roots:
        mark_has_papers(root)

    return roots


def collect_descendant_folder_ids(folder_id: int, folders: list[Folder]) -> set[int]:
    children_map: dict[int | None, list[int]] = {}
    for folder in folders:
        children_map.setdefault(folder.parent_id, []).append(folder.id)

    result: set[int] = set()
    stack = [folder_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children_map.get(current, []))

    return result


def folder_segments(db: Session, folder_id: int | None) -> list[str]:
    if folder_id is None:
        return []

    segments: list[str] = []
    current_id = folder_id
    while current_id is not None:
        folder = db.query(Folder).filter(Folder.id == current_id).first()
        if not folder:
            break
        segments.append(folder.name)
        current_id = folder.parent_id

    segments.reverse()
    return segments


def note_to_dict(note: Note) -> dict[str, object]:
    structured_data = note.structured_data if isinstance(note.structured_data, dict) else {}
    return {
        "id": note.id,
        "note_id": note.note_id,
        "title": note.title,
        "topic_key": note.topic_key,
        "summary": note.summary,
        "content": note.content,
        "structured_data": structured_data,
        "paper_id": note.paper_id,
        "session_id": note.session_id,
        "folder_id": note.folder_id,
        "file_path": note.file_path,
        "created_at": note.created_at.isoformat() if isinstance(note.created_at, datetime) else "",
        "updated_at": note.updated_at.isoformat() if isinstance(note.updated_at, datetime) else "",
    }


def note_folder_to_dict(folder: NoteFolder) -> dict[str, str | int | None]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at.isoformat() if isinstance(folder.created_at, datetime) else "",
        "updated_at": folder.updated_at.isoformat() if isinstance(folder.updated_at, datetime) else "",
    }


def build_note_folder_tree(
    folders: list[NoteFolder],
    folder_ids_with_notes: set[int] | None = None,
) -> list[dict[str, object]]:
    occupied_folder_ids = folder_ids_with_notes or set()
    node_map: dict[int, dict[str, object]] = {}
    roots: list[dict[str, object]] = []

    for folder in folders:
        node_map[folder.id] = {
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_id,
            "children": [],
            "has_notes": folder.id in occupied_folder_ids,
        }

    for folder in folders:
        node = node_map[folder.id]
        parent_id = folder.parent_id
        if parent_id and parent_id in node_map:
            parent_node = node_map[parent_id]
            parent_children = parent_node["children"]
            if isinstance(parent_children, list):
                parent_children.append(node)
        else:
            roots.append(node)

    def mark_has_notes(node: dict[str, object]) -> bool:
        has_notes = bool(node.get("has_notes"))
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict) and mark_has_notes(child):
                    has_notes = True
        node["has_notes"] = has_notes
        return has_notes

    for root in roots:
        mark_has_notes(root)

    return roots


def collect_descendant_note_folder_ids(folder_id: int, folders: list[NoteFolder]) -> set[int]:
    children_map: dict[int | None, list[int]] = {}
    for folder in folders:
        children_map.setdefault(folder.parent_id, []).append(folder.id)

    result: set[int] = set()
    stack = [folder_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children_map.get(current, []))

    return result


def note_folder_segments(db: Session, folder_id: int | None) -> list[str]:
    if folder_id is None:
        return []

    segments: list[str] = []
    current_id = folder_id
    while current_id is not None:
        folder = db.query(NoteFolder).filter(NoteFolder.id == current_id).first()
        if not folder:
            break
        segments.append(folder.name)
        current_id = folder.parent_id

    segments.reverse()
    return segments


def knowledge_unit_to_dict(unit: KnowledgeUnit) -> dict[str, object]:
    return {
        "id": unit.id,
        "paper_id": unit.paper_id,
        "canonical_key": unit.canonical_key,
        "unit_type": unit.unit_type,
        "term": unit.term,
        "core_claim": unit.core_claim,
        "summary": unit.summary,
        "aliases": unit.aliases if isinstance(unit.aliases, list) else [],
        "semantic_fingerprint": unit.semantic_fingerprint if isinstance(unit.semantic_fingerprint, list) else [],
        "payload": unit.payload if isinstance(unit.payload, dict) else {},
        "created_at": unit.created_at.isoformat() if isinstance(unit.created_at, datetime) else "",
        "updated_at": unit.updated_at.isoformat() if isinstance(unit.updated_at, datetime) else "",
    }


def knowledge_graph_edge_to_dict(edge: KnowledgeGraphEdge) -> dict[str, object]:
    return {
        "id": edge.id,
        "paper_id": edge.paper_id,
        "from_unit_id": edge.from_unit_id,
        "relation": edge.relation,
        "to_unit_id": edge.to_unit_id,
        "payload": edge.payload if isinstance(edge.payload, dict) else {},
        "created_at": edge.created_at.isoformat() if isinstance(edge.created_at, datetime) else "",
        "updated_at": edge.updated_at.isoformat() if isinstance(edge.updated_at, datetime) else "",
    }


def normalize_topic_key(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in normalized).strip("-")


def note_topic_key(note: Note) -> str:
    return normalize_topic_key(note.topic_key or note.title)


def sync_markdown_title(content: str, title: str) -> str:
    if not content:
        return content
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        lines[0] = f"# {title}"
        return "\n".join(lines)
    return content
