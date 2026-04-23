import unittest

from backend.app.agents.parsers import (
    parse_canonical_decisions,
    parse_extracted_units,
    parse_relation_decisions,
    parse_structured_notes,
)


class SessionNotesParserTests(unittest.TestCase):
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
                "mental_model": "用户把 attention 理解成一种帮助模型关注重点信息的机制，但还说不清权重如何形成。"
              },
              "follow_up_questions": ["权重是如何算出来的？"],
              "dedupe_hints": {"aliases": ["注意力机制"], "semantic_fingerprint": ["focus", "weights", "tokens"]},
              "content": "# Attention-用户对作用有部分理解\\n\\n## 用户当前是怎么理解这个问题的\\n用户觉得 attention 的作用是关注重要词。\\n\\n## 分析与推进\\n这个理解抓住了用途，但还停留在功能层，缺少对权重如何形成的机制性认识。\\n\\n## 后续可以继续追问\\n- 权重是如何算出来的？"
            }
          ]
        }
        """
        parsed = parse_structured_notes(raw, max_points=3)
        self.assertTrue(parsed.ok)
        self.assertEqual(len(parsed.data), 1)
        self.assertEqual(parsed.data[0].note_id, "temp_001")
        self.assertIn("用户当前是怎么理解这个问题的", parsed.data[0].content)
        self.assertEqual(parsed.data[0].cognitive_state.mental_model[:2], "用户")
        self.assertNotIn("关键证据", parsed.data[0].content)
        self.assertNotIn("evidence", parsed.data[0].model_dump(mode="json"))

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
        self.assertEqual(len(parsed.data), 1)
        self.assertEqual(parsed.data[0].local_relations[0].relation_type.value, "used_for")
        self.assertNotIn("evidence", parsed.data[0].model_dump(mode="json"))

    def test_parse_canonical_decisions(self):
        raw = """
        {"decisions":[{"source_unit_id":"u1","action":"merge","target_unit_id":7,"target_canonical_key":"attention","confidence":0.9,"reason":"same","evidence":["same term"]}]}
        """
        parsed = parse_canonical_decisions(raw)
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.data[0].action.value, "merge")
        self.assertNotIn("evidence", parsed.data[0].model_dump(mode="json"))

    def test_parse_canonical_soft_link_falls_back_to_create_new(self):
        raw = """
        {"decisions":[{"source_unit_id":"u1","action":"soft_link","target_unit_id":7,"target_canonical_key":"attention","confidence":0.5,"reason":"related","evidence":["adjacent"]}]}
        """
        parsed = parse_canonical_decisions(raw)
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.data[0].action.value, "create_new")

    def test_parse_relation_decisions(self):
        raw = """
        {"relations":[{"from_unit_ref":"u1","relation_type":"related_to","to_unit_ref":"history:7","confidence":0.6,"evidence":["co-mentioned"]}]}
        """
        parsed = parse_relation_decisions(raw)
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.data[0].to_unit_ref, "history:7")
        self.assertNotIn("evidence", parsed.data[0].model_dump(mode="json"))


if __name__ == "__main__":
    unittest.main()
