import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, ChatSession, KnowledgeUnit, KnowledgeUnitNoteLink, Note, Paper
from backend.app.agents.implementations.orchestrators.conversation import ConversationOrchestrator
from backend.app.agents.model_adapter import ModelAdapterError
from backend.app.agents.state import ConversationAgentState
from backend.app.services.cognitive_context import collect_cognitive_context_candidates


class CognitiveContextCandidateTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.TestingSession = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSession()

        paper = Paper(
            id="paper-1",
            title="Attention Is All You Need",
            authors="Author",
            research_topic="Attention",
            journal="Journal",
            publication_date="2017",
            original_filename="paper.pdf",
            file_path="/tmp/paper.pdf",
        )
        session = ChatSession(id=1, paper_id="paper-1", name="Session 1")
        note = Note(
            note_id="note-qkv",
            title="Attention/QKV-用户区分权重来源和被聚合对象",
            topic_key="attention-qkv-weights-on-v",
            summary="用户已经纠正 QK 后乘 K 的误解，开始区分 V 承载被聚合的信息。",
            content="# Attention/QKV\n\nQK 得到权重，权重应用到 V。",
            cognitive_state={
                "state": "partial_understanding",
                "confidence": 0.82,
                "mental_model": "用户认为 Q/K 用来决定看哪里，V 承载真正被聚合的信息。",
            },
            follow_up_questions=["为什么 attention 输出不能直接预测 token？"],
            dedupe_hints={
                "aliases": ["QKV attention"],
                "semantic_fingerprint": ["QK", "V", "weights"],
                "retrieval_description": "当用户询问 QK 后为什么乘 V、混淆 K 与 V 的作用，或讨论 attention 权重应用对象时，应召回这条 note。",
            },
            paper_id="paper-1",
            session_id=1,
            file_path="/tmp/note.md",
        )
        unrelated = Note(
            note_id="note-other",
            title="Optimization",
            topic_key="optimization",
            summary="用户讨论优化器。",
            content="# Optimization",
            cognitive_state={},
            follow_up_questions=[],
            dedupe_hints={},
            paper_id=None,
            session_id=None,
            file_path="/tmp/other.md",
        )
        content_only = Note(
            note_id="note-content-only",
            title="Unrelated Index",
            topic_key="unrelated-index",
            summary="这条 note 的索引描述不相关。",
            content="# Unrelated\n\nQK 算出来后为什么是乘 V，而不是乘 K？",
            cognitive_state={},
            follow_up_questions=[],
            dedupe_hints={
                "retrieval_description": "当用户询问优化器动量或学习率调度时，应召回这条 note。",
                "semantic_fingerprint": ["optimizer", "learning rate"],
            },
            paper_id="paper-1",
            session_id=1,
            file_path="/tmp/content-only.md",
        )
        unit = KnowledgeUnit(
            paper_id="paper-1",
            canonical_key="scaled-dot-product-attention",
            unit_type="method",
            term="Scaled Dot-Product Attention",
            core_claim="QK 产生 attention 权重，V 承载被加权聚合的信息。",
            summary="scaled dot-product attention 的 Q、K、V 分工。",
            aliases=["QKV attention"],
            related_terms=["softmax", "attention weights"],
            slots={},
        )
        self.db.add_all([paper, session, note, unrelated, content_only, unit])
        self.db.flush()
        self.db.add(KnowledgeUnitNoteLink(knowledge_unit_id=unit.id, note_id=note.id))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_collects_durable_notes_and_knowledge_units_for_current_question(self):
        candidates = collect_cognitive_context_candidates(
            self.db,
            question="QK 算出来后为什么是乘 V，而不是乘 K？",
            quote="attention weights",
            paper_id="paper-1",
            session_id=1,
        )

        candidate_ids = {candidate["candidate_id"] for candidate in candidates}
        self.assertIn("note:1", candidate_ids)
        self.assertTrue(any(str(candidate["candidate_id"]).startswith("knowledge_unit:") for candidate in candidates))
        note_candidate = next(candidate for candidate in candidates if candidate["candidate_id"] == "note:1")
        self.assertEqual(note_candidate["source_scope"], "same_session")
        self.assertIn("混淆 K 与 V", note_candidate["retrieval_description"])
        self.assertNotIn("note:3", candidate_ids)
        unit_candidate = next(candidate for candidate in candidates if str(candidate["candidate_id"]).startswith("knowledge_unit:"))
        self.assertEqual(unit_candidate["source_scope"], "same_paper")
        self.assertEqual(unit_candidate["linked_notes"][0]["note_id"], 1)


class FailingSelectionAdapter:
    async def call(self, **_kwargs):
        raise ModelAdapterError("selection unavailable")


class CognitiveContextSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_selection_failure_degrades_to_empty_brief(self):
        orchestrator = ConversationOrchestrator(adapter=FailingSelectionAdapter())
        state = ConversationAgentState(
            user_input="Explain V",
            retrieval_context={
                "quote": "",
                "pdf_filename": "paper.pdf",
                "cognitive_context_candidates": [{"candidate_id": "note:1", "kind": "note"}],
            },
        )

        await orchestrator._select_cognitive_context(state)

        self.assertEqual(
            state.retrieval_context["cognitive_context_brief"],
            {
                "answer_strategy": "",
                "relevant_mental_models": [],
                "misunderstandings_to_correct": [],
                "knowledge_to_connect": [],
                "follow_up_questions": [],
                "source_refs": [],
            },
        )
        self.assertTrue(any(error["agent"] == "cognitive_context_agent" for error in state.errors))


if __name__ == "__main__":
    unittest.main()
