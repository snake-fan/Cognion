import unittest
from unittest.mock import patch

from backend.app.agents.schemas import (
    CanonicalDecision,
    CanonicalizationAction,
    ExtractedUnit,
    StructuredNote,
)
from backend.app.services.knowledge_graph import build_graph_patch, filter_existing_knowledge_units_for_note
from backend.test.fixtures.attention_notes_dataset import (
    ATTENTION_PAPER,
    ATTENTION_SESSION_MESSAGES,
    EXISTING_KNOWLEDGE_UNITS,
)


class AttentionNotesFixtureTests(unittest.TestCase):
    def test_fixture_has_attention_session_and_existing_units(self):
        self.assertEqual(ATTENTION_PAPER["paper_title"], "Attention Is All You Need")
        self.assertGreaterEqual(len(ATTENTION_SESSION_MESSAGES), 6)
        self.assertTrue(any("QK" in message["content"] for message in ATTENTION_SESSION_MESSAGES))
        self.assertGreaterEqual(len(EXISTING_KNOWLEDGE_UNITS), 3)

    @patch(
        "backend.app.services.knowledge_graph.matching._rerank_similarity_candidates",
        side_effect=lambda *, candidate_groups, **kwargs: candidate_groups,
    )
    def test_fixture_existing_units_are_retrievable_for_attention_units(self, _mock_rerank):
        incoming_units = [
            ExtractedUnit(
                unit_id="u_qkv",
                source_note_id="temp_attention_fixture",
                type="concept",
                canonical_name="Q/K 决定注意力权重，V 承载被聚合的信息",
                aliases=["scaled dot-product attention"],
                description="QK 得到权重，权重应用到 V，而不是 K。",
                keywords=["QK", "V", "softmax", "weighted sum"],
            ),
            ExtractedUnit(
                unit_id="u_multi_head",
                source_note_id="temp_attention_fixture",
                type="concept",
                canonical_name="multi-head attention",
                aliases=["多头注意力"],
                description="多组 QKV 并行计算 attention 后 concat。",
                keywords=["heads", "parallel", "concat"],
            ),
        ]

        candidates = filter_existing_knowledge_units_for_note(
            note_units=incoming_units,
            existing_knowledge_units=EXISTING_KNOWLEDGE_UNITS,
            paper_id=ATTENTION_PAPER["paper_id"],
            session_id=ATTENTION_PAPER["session_id"],
        )

        candidate_ids = {candidate["knowledge_unit_id"] for candidate in candidates}
        self.assertIn(101, candidate_ids)
        self.assertIn(102, candidate_ids)

    def test_build_graph_patch_covers_create_merge_and_reuse(self):
        note = StructuredNote.model_validate(
            {
                "note_id": "temp_attention_fixture",
                "title": "Attention/QKV-用户区分权重来源和被聚合对象",
                "topic_key": "attention-qkv-weights-on-v",
                "summary": "用户已经纠正 QK 后乘 K 的误解，开始区分 attention hidden state 与最终 token 预测。",
                "content": "# Attention/QKV-用户区分权重来源和被聚合对象",
                "cognitive_state": {
                    "state": "partial_understanding",
                    "confidence": 0.82,
                    "mental_model": "用户认为 Q/K 用来决定看哪里，V 承载真正被聚合的信息。",
                },
                "follow_up_questions": ["为什么 attention 输出不能直接预测 token？"],
                "dedupe_hints": {"aliases": ["QKV attention"], "semantic_fingerprint": ["QK", "V", "hidden state"]},
            }
        )
        units = [
            ExtractedUnit(
                unit_id="u_merge_qkv",
                source_note_id=note.note_id,
                type="concept",
                canonical_name="Attention 中 Q/K 决定权重，V 承载被聚合的内容",
                aliases=["scaled dot-product attention"],
                description="与现有 scaled-dot-product-attention 是同一机制，但补充了用户误解边界。",
                keywords=["QK", "V", "softmax"],
            ),
            ExtractedUnit(
                unit_id="u_reuse_multi_head",
                source_note_id=note.note_id,
                type="concept",
                canonical_name="Multi-Head Attention",
                aliases=["多头注意力"],
                description="完全落在现有 multi-head-attention unit 的覆盖范围内。",
                keywords=["heads", "parallel", "concat"],
            ),
            ExtractedUnit(
                unit_id="u_create_misconception",
                source_note_id=note.note_id,
                type="question",
                canonical_name="用户把 attention hidden state 与 token prediction 的边界混淆",
                aliases=[],
                description="这是面向用户认知状态的新问题，不应直接并入论文机制 unit。",
                keywords=["hidden state", "token prediction", "认知边界"],
            ),
        ]

        patch_payload = build_graph_patch(
            notes=[note],
            note_units={note.note_id: units},
            canonicalization_decisions={
                note.note_id: [
                    CanonicalDecision(
                        source_unit_id="u_merge_qkv",
                        action=CanonicalizationAction.MERGE,
                        target_unit_id=101,
                        target_canonical_key="scaled-dot-product-attention",
                        confidence=0.92,
                        reason="同一 attention 计算机制，需要吸收新的用户误解信息。",
                    ),
                    CanonicalDecision(
                        source_unit_id="u_reuse_multi_head",
                        action=CanonicalizationAction.REUSE,
                        target_unit_id=102,
                        target_canonical_key="multi-head-attention",
                        confidence=0.88,
                        reason="现有 unit 已完整覆盖该内容。",
                    ),
                    CanonicalDecision(
                        source_unit_id="u_create_misconception",
                        action=CanonicalizationAction.CREATE_NEW,
                        confidence=0.79,
                        reason="这是新的用户认知边界 unit。",
                    ),
                ]
            },
            relation_decisions={},
        )

        self.assertEqual(len(patch_payload.units_to_merge), 1)
        self.assertEqual(patch_payload.units_to_merge[0].target_unit_id, 101)
        self.assertEqual(len(patch_payload.units_to_link), 1)
        self.assertEqual(patch_payload.units_to_link[0].target_unit_id, 102)
        self.assertEqual(len(patch_payload.units_to_create), 1)
        self.assertEqual(patch_payload.units_to_create[0].source_unit_id, "u_create_misconception")


if __name__ == "__main__":
    unittest.main()
