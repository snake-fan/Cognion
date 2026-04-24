import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, ChatSession, KnowledgeGraphEdge, KnowledgeUnit, KnowledgeUnitNoteLink, Note, Paper
from backend.app.routes.knowledge_graph import get_knowledge_graph


class KnowledgeGraphRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.TestingSession = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSession()

        paper = Paper(
            id="paper-1",
            title="Paper",
            authors="Author",
            research_topic="Topic",
            journal="Journal",
            publication_date="2025",
            original_filename="paper.pdf",
            file_path="/tmp/paper.pdf",
        )
        chat_session = ChatSession(id=1, paper_id="paper-1", name="Session 1")
        note = Note(
            note_id="note-1",
            title="Attention Note",
            topic_key="attention-note",
            summary="summary",
            content="# Attention Note",
            dedupe_hints={},
            paper_id="paper-1",
            session_id=1,
            folder_id=None,
            file_path="/tmp/note.md",
        )
        unit_a = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="attention",
            unit_type="concept",
            term="attention",
            core_claim="focus",
            summary="attention summary",
            aliases=["注意力机制"],
            related_terms=["weights"],
            slots={},
        )
        unit_b = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="self-attention",
            unit_type="method",
            term="self-attention",
            core_claim="attend to sequence",
            summary="self-attention summary",
            aliases=[],
            related_terms=["sequence"],
            slots={},
        )
        self.db.add_all([paper, chat_session, note, unit_a, unit_b])
        self.db.flush()
        self.db.add(KnowledgeUnitNoteLink(knowledge_unit_id=unit_a.id, note_id=note.id))
        self.db.add(
            KnowledgeGraphEdge(
                paper_id="paper-1",
                from_unit_id=unit_a.id,
                relation="RELATED_TO",
                to_unit_id=unit_b.id,
                payload={"source": "test"},
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_knowledge_graph_returns_units_and_unit_edges(self):
        payload = get_knowledge_graph(self.db)

        self.assertIn("units", payload)
        self.assertNotIn("nodes", payload)
        self.assertEqual(len(payload["units"]), 2)
        unit_map = {unit["term"]: unit for unit in payload["units"]}
        self.assertEqual(unit_map["attention"]["note_ids"], [1])
        self.assertEqual(payload["edges"][0]["from_unit_id"], unit_map["attention"]["id"])
        self.assertEqual(payload["edges"][0]["to_unit_id"], unit_map["self-attention"]["id"])
        self.assertNotIn("knowledge_units", payload)


if __name__ == "__main__":
    unittest.main()
