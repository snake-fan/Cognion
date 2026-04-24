import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.agents.parsers import (
    parse_canonical_decisions,
    parse_extracted_units,
    parse_relation_decisions,
    parse_structured_notes,
)
from backend.app.agents.schemas import (
    CanonicalDecision,
    CanonicalizationAction,
    ExtractedUnit,
    RelationDecision,
    RelationType,
    StructuredNote,
)
from backend.app.db.models import Base, ChatSession, KnowledgeGraphEdge, KnowledgeUnit, KnowledgeUnitNoteLink, Note, Paper
from backend.app.services.knowledge_graph import (
    apply_graph_patch,
    build_graph_patch,
    retrieve_candidate_units_for_canonicalization,
)


class SessionNotesPipelineTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSession()
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
        session = ChatSession(id=1, paper_id="paper-1", name="S1")
        self.db.add(paper)
        self.db.add(session)
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def test_parse_structured_notes(self):
        raw = """
        {
          "notes": [
            {
              "note_id": "temp_001",
              "title": "Attention-用户对作用有部分理解",
              "topic_key": "attention-role",
              "summary": "用户知道 attention 用于聚焦信息，但还没有完全理解其机制。",
              "cognitive_state": {
                "state": "partial_understanding",
                "confidence": 0.8,
                "mental_model": "用户知道 attention 用于聚焦信息，但对内部计算还没有清晰模型。"
              },
              "follow_up_questions": ["权重是如何算出来的？"],
              "dedupe_hints": {"aliases": ["注意力机制"], "semantic_fingerprint": ["focus", "weights", "tokens"]},
              "content": "# Attention-用户对作用有部分理解\\n\\n## 用户当前是怎么理解这个问题的\\n用户知道 attention 用于聚焦信息。\\n\\n## 分析与推进\\n这个理解还停留在作用层，尚未进入机制层。\\n\\n## 后续可以继续追问\\n- 权重是如何算出来的？"
            }
          ]
        }
        """
        parsed = parse_structured_notes(raw, max_points=3)
        self.assertTrue(parsed.ok)
        self.assertEqual(len(parsed.data), 1)
        note = parsed.data[0]
        self.assertEqual(note.note_id, "temp_001")
        self.assertIn("用户当前是怎么理解这个问题的", note.content)
        self.assertNotIn("关键证据", note.content)
        self.assertNotIn("evidence", note.model_dump(mode="json"))

    def test_parse_extracted_units(self):
        raw = """
        {
          "units": [
            {
              "unit_id": "temp_001_unit_001",
              "type": "concept",
              "canonical_name": "attention",
              "aliases": ["注意力机制"],
              "description": "用于给不同 token 分配关注权重",
              "keywords": ["weights", "token"],
              "slots": {"object": "token"},
              "local_relations": [{"target_unit_ref": "temp_001_unit_002", "relation_type": "used_for", "evidence": "同 note 中说明"}],
              "evidence": [{"source": "note", "quote": "关注重要词"}]
            }
          ]
        }
        """
        parsed = parse_extracted_units(raw, source_note_id="temp_001")
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.data[0].source_note_id, "temp_001")
        self.assertEqual(parsed.data[0].local_relations[0].relation_type.value, "used_for")
        self.assertNotIn("evidence", parsed.data[0].model_dump(mode="json"))

    def test_parse_canonical_and_relation_decisions(self):
        canonical_raw = """
        {"decisions":[{"source_unit_id":"u1","action":"merge","target_unit_id":7,"target_canonical_key":"attention","confidence":0.9,"reason":"same","evidence":["same term"]}]}
        """
        relation_raw = """
        {"relations":[{"from_unit_ref":"u1","relation_type":"related_to","to_unit_ref":"history:7","confidence":0.6,"evidence":["co-mentioned"]}]}
        """
        canonical = parse_canonical_decisions(canonical_raw)
        relation = parse_relation_decisions(relation_raw)
        self.assertTrue(canonical.ok)
        self.assertTrue(relation.ok)
        self.assertEqual(canonical.data[0].action.value, "merge")
        self.assertEqual(relation.data[0].to_unit_ref, "history:7")
        self.assertNotIn("evidence", canonical.data[0].model_dump(mode="json"))
        self.assertNotIn("evidence", relation.data[0].model_dump(mode="json"))

    @patch(
        "backend.app.services.knowledge_graph.matching._rerank_similarity_candidates",
        side_effect=lambda *, candidate_groups, **kwargs: candidate_groups,
    )
    def test_retrieve_candidates_prefers_same_paper(self, _mock_rerank):
        same_paper = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="attention",
            unit_type="concept",
            term="attention",
            core_claim="focus on tokens",
            summary="attention summary",
            aliases=["注意力机制"],
            related_terms=["weights"],
            slots={},
        )
        other_paper = KnowledgeUnit(
            paper_id="paper-2",
            canonical_key="attention-alt",
            unit_type="concept",
            term="attention",
            core_claim="focus on tokens",
            summary="attention summary",
            aliases=["注意力机制"],
            related_terms=["weights"],
            slots={},
        )
        self.db.add_all([same_paper, other_paper])
        self.db.flush()
        units = [
            ExtractedUnit(
                unit_id="u1",
                source_note_id="n1",
                type="concept",
                canonical_name="attention",
                aliases=["注意力机制"],
                description="focus on tokens",
                keywords=["weights"],
            )
        ]
        candidates = retrieve_candidate_units_for_canonicalization(
            self.db,
            units,
            paper_id="paper-1",
            session_id=1,
        )
        self.assertGreaterEqual(candidates[0]["score"], candidates[1]["score"])
        self.assertEqual(candidates[0]["source"], "same_paper")

    def test_build_and_apply_graph_patch(self):
        note = StructuredNote.model_validate(
            {
                "note_id": "temp_001",
                "title": "Attention-note",
                "topic_key": "attention-note",
                "summary": "summary",
                "content": "# Attention-note",
                "cognitive_state": {
                    "state": "partial_understanding",
                    "confidence": 0.7,
                    "mental_model": "用户知道它会聚焦重要信息。",
                },
                "follow_up_questions": [],
                "dedupe_hints": {"aliases": [], "semantic_fingerprint": []},
            }
        )
        persisted_note = Note(
            note_id="temp_001",
            title="Attention-note",
            topic_key="attention-note",
            summary="summary",
            content="# Attention-note",
            dedupe_hints={},
            paper_id="paper-1",
            session_id=1,
            folder_id=None,
            file_path="/tmp/note.md",
        )
        self.db.add(persisted_note)
        self.db.flush()

        patch, provenance = build_graph_patch(
            notes=[note],
            note_units={
                "temp_001": [
                    ExtractedUnit(
                        unit_id="u1",
                        source_note_id="temp_001",
                        type="concept",
                        canonical_name="attention",
                        aliases=["注意力机制"],
                        description="focus on tokens",
                        keywords=["weights"],
                    )
                ]
            },
            canonicalization_decisions={
                "temp_001": [
                    CanonicalDecision(
                        source_unit_id="u1",
                        action=CanonicalizationAction.CREATE_NEW,
                        confidence=0.8,
                        reason="new",
                    )
                ]
            },
            relation_decisions={
                "temp_001": [
                    RelationDecision(
                        from_unit_ref="u1",
                        relation_type=RelationType.SAME_AS,
                        to_unit_ref="u1",
                        confidence=0.4,
                    )
                ]
            },
        )
        self.assertTrue(provenance)
        results = apply_graph_patch(self.db, graph_patch=patch, notes_by_ref={"temp_001": persisted_note})
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["knowledge_unit_ids"])
        self.assertNotIn("node_ids", results[0])
        self.assertEqual(self.db.query(KnowledgeUnitNoteLink).count(), 1)
        edge = self.db.query(KnowledgeGraphEdge).one()
        self.assertEqual(edge.from_unit_id, results[0]["knowledge_unit_ids"][0])
        self.assertEqual(edge.to_unit_id, results[0]["knowledge_unit_ids"][0])

    @patch("backend.app.services.knowledge_graph.apply._merge_existing_knowledge_unit_with_llm", return_value=None)
    def test_merge_updates_existing_unit_with_new_information(self, _mock_merge):
        note = StructuredNote.model_validate(
            {
                "note_id": "temp_002",
                "title": "Attention-merge",
                "topic_key": "attention-merge",
                "summary": "new summary",
                "content": "# Attention-merge",
                "cognitive_state": {
                    "state": "partial_understanding",
                    "confidence": 0.7,
                    "mental_model": "用户开始把 attention 和新的计算过程联系起来。",
                },
                "follow_up_questions": [],
                "dedupe_hints": {"aliases": [], "semantic_fingerprint": []},
            }
        )
        persisted_note = Note(
            note_id="temp_002",
            title="Attention-merge",
            topic_key="attention-merge",
            summary="new summary",
            content="# Attention-merge",
            dedupe_hints={},
            paper_id="paper-1",
            session_id=1,
            folder_id=None,
            file_path="/tmp/note-merge.md",
        )
        existing = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="attention",
            unit_type="concept",
            term="attention",
            core_claim="old focus",
            summary="old summary",
            aliases=["注意力机制"],
            related_terms=["weights", "self-attention"],
            slots={"scope": "token"},
        )
        self.db.add_all([persisted_note, existing])
        self.db.flush()

        patch, _ = build_graph_patch(
            notes=[note],
            note_units={
                "temp_002": [
                    ExtractedUnit(
                        unit_id="u_merge",
                        source_note_id="temp_002",
                        type="concept",
                        canonical_name="attention",
                        aliases=["scaled dot-product attention"],
                        description="new computation",
                        keywords=["softmax"],
                        slots={"equation": "QK^T"},
                    )
                ]
            },
            canonicalization_decisions={
                "temp_002": [
                    CanonicalDecision(
                        source_unit_id="u_merge",
                        action=CanonicalizationAction.MERGE,
                        target_unit_id=existing.id,
                        target_canonical_key="attention",
                        confidence=0.9,
                        reason="same unit",
                    )
                ]
            },
            relation_decisions={},
        )

        results = apply_graph_patch(self.db, graph_patch=patch, notes_by_ref={"temp_002": persisted_note})
        self.db.refresh(existing)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["knowledge_unit_ids"], [existing.id])
        self.assertNotIn("node_ids", results[0])
        self.assertEqual(self.db.query(KnowledgeUnit).count(), 1)
        self.assertIn("old focus", existing.core_claim)
        self.assertIn("new computation", existing.core_claim)
        self.assertIn("old summary", existing.summary)
        self.assertIn("new summary", existing.summary)
        self.assertIn("scaled dot-product attention", existing.aliases)
        self.assertIn("softmax", existing.related_terms)
        self.assertEqual(existing.slots["scope"], "token")
        self.assertEqual(existing.slots["equation"], "QK^T")

    @patch("backend.app.services.knowledge_graph.apply._merge_existing_knowledge_unit_with_llm")
    def test_merge_uses_llm_structured_output_when_available(self, mock_merge):
        mock_merge.return_value = {
            "unit_type": "concept",
            "term": "scaled dot-product attention",
            "canonical_key": "scaled-dot-product-attention",
            "core_claim": "attention computes similarity scores and normalizes them",
            "summary": "merged summary",
            "aliases": ["attention", "注意力机制"],
            "related_terms": ["weights", "softmax", "self-attention", "transformer"],
            "slots": {"equation": "softmax(QK^T / sqrt(d))"},
        }
        note = StructuredNote.model_validate(
            {
                "note_id": "temp_004",
                "title": "Attention-llm-merge",
                "topic_key": "attention-llm-merge",
                "summary": "incoming summary",
                "content": "# Attention-llm-merge",
                "cognitive_state": {
                    "state": "partial_understanding",
                    "confidence": 0.7,
                    "mental_model": "用户正在把 attention 理解为一种相似度比较过程。",
                },
                "follow_up_questions": [],
                "dedupe_hints": {"aliases": [], "semantic_fingerprint": []},
            }
        )
        persisted_note = Note(
            note_id="temp_004",
            title="Attention-llm-merge",
            topic_key="attention-llm-merge",
            summary="incoming summary",
            content="# Attention-llm-merge",
            dedupe_hints={},
            paper_id="paper-1",
            session_id=1,
            folder_id=None,
            file_path="/tmp/note-llm-merge.md",
        )
        existing = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="attention",
            unit_type="concept",
            term="attention",
            core_claim="old focus",
            summary="old summary",
            aliases=["注意力机制"],
            related_terms=["weights", "self-attention"],
            slots={},
        )
        self.db.add_all([persisted_note, existing])
        self.db.flush()

        patch_payload, _ = build_graph_patch(
            notes=[note],
            note_units={
                "temp_004": [
                    ExtractedUnit(
                        unit_id="u_llm_merge",
                        source_note_id="temp_004",
                        type="concept",
                        canonical_name="attention",
                        aliases=["scaled dot-product attention"],
                        description="incoming claim",
                        keywords=["softmax"],
                    )
                ]
            },
            canonicalization_decisions={
                "temp_004": [
                    CanonicalDecision(
                        source_unit_id="u_llm_merge",
                        action=CanonicalizationAction.MERGE,
                        target_unit_id=existing.id,
                        target_canonical_key="attention",
                        confidence=0.95,
                        reason="same unit",
                    )
                ]
            },
            relation_decisions={},
        )

        apply_graph_patch(self.db, graph_patch=patch_payload, notes_by_ref={"temp_004": persisted_note})
        self.db.refresh(existing)

        self.assertEqual(existing.term, "scaled dot-product attention")
        self.assertEqual(existing.canonical_key, "scaled-dot-product-attention")
        self.assertEqual(existing.core_claim, "attention computes similarity scores and normalizes them")
        self.assertEqual(existing.summary, "merged summary")
        self.assertEqual(existing.slots["equation"], "softmax(QK^T / sqrt(d))")

    def test_reuse_keeps_existing_unit_unchanged(self):
        note = StructuredNote.model_validate(
            {
                "note_id": "temp_003",
                "title": "Attention-reuse",
                "topic_key": "attention-reuse",
                "summary": "reuse summary",
                "content": "# Attention-reuse",
                "cognitive_state": {
                    "state": "partial_understanding",
                    "confidence": 0.7,
                    "mental_model": "用户这次只是再次提到 attention，没有新增稳定理解。",
                },
                "follow_up_questions": [],
                "dedupe_hints": {"aliases": [], "semantic_fingerprint": []},
            }
        )
        persisted_note = Note(
            note_id="temp_003",
            title="Attention-reuse",
            topic_key="attention-reuse",
            summary="reuse summary",
            content="# Attention-reuse",
            dedupe_hints={},
            paper_id="paper-1",
            session_id=1,
            folder_id=None,
            file_path="/tmp/note-reuse.md",
        )
        existing = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="attention",
            unit_type="concept",
            term="attention",
            core_claim="stable claim",
            summary="stable summary",
            aliases=["注意力机制"],
            related_terms=["weights", "self-attention"],
            slots={"scope": "token"},
        )
        self.db.add_all([persisted_note, existing])
        self.db.flush()

        patch, _ = build_graph_patch(
            notes=[note],
            note_units={
                "temp_003": [
                    ExtractedUnit(
                        unit_id="u_reuse",
                        source_note_id="temp_003",
                        type="concept",
                        canonical_name="attention",
                        aliases=["should be dropped"],
                        description="ignored new claim",
                        keywords=["softmax"],
                        slots={"equation": "QK^T"},
                    )
                ]
            },
            canonicalization_decisions={
                "temp_003": [
                    CanonicalDecision(
                        source_unit_id="u_reuse",
                        action=CanonicalizationAction.REUSE,
                        target_unit_id=existing.id,
                        target_canonical_key="attention",
                        confidence=0.9,
                        reason="fully covered",
                    )
                ]
            },
            relation_decisions={},
        )

        results = apply_graph_patch(self.db, graph_patch=patch, notes_by_ref={"temp_003": persisted_note})
        self.db.refresh(existing)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["knowledge_unit_ids"], [existing.id])
        self.assertNotIn("node_ids", results[0])
        self.assertEqual(self.db.query(KnowledgeUnit).count(), 1)
        self.assertEqual(existing.core_claim, "stable claim")
        self.assertEqual(existing.summary, "stable summary")
        self.assertEqual(existing.aliases, ["注意力机制"])
        self.assertEqual(existing.related_terms, ["weights", "self-attention"])
        self.assertEqual(existing.slots, {"scope": "token"})


if __name__ == "__main__":
    unittest.main()
