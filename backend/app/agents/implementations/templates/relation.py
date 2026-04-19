def build_relation_system_template() -> str:
    return "你是 Relation Agent，负责判断 knowledge units 之间的 typed relations，并给出置信度。"


def build_relation_user_template(note_json: str, units_json: str, candidates_json: str) -> str:
    return f"""
你需要为当前 note 相关 knowledge units 判断关系。

[当前 note]
{note_json}

[当前 note units]
{units_json}

[跨 note / 历史候选 units]
{candidates_json}

[可用关系类型]
- asks_about
- related_to
- confused_with
- prerequisite_of
- used_for
- same_as

[要求]
- 可以连接当前 note 内 knowledge units，也可以连接到历史候选 knowledge units
- `same_as` 只表示关系判断，不等价于 merge 决策
- 每条关系都要有 confidence
- 关系不明确时不要强行输出

[输出格式]
仅输出合法 JSON：
{{
  "relations": [
    {{
      "from_unit_ref": "note_x_unit_001",
      "relation_type": "related_to",
      "to_unit_ref": "history:12",
      "confidence": 0.74
    }}
  ]
}}
""".strip()
