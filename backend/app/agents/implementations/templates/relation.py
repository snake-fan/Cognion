def build_relation_system_template() -> str:
    return "你是 Relation Agent，负责只保留少量明确、有解释价值的 knowledge unit 关系。"


def build_relation_user_template(note_json: str, units_json: str, candidates_json: str) -> str:
    return f"""
你需要为当前 note 相关 knowledge units 判断关系。
目标不是让图谱变密，而是只保留用户看见后会觉得“这条连接有意义”的强关系。

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
- 默认输出 0~2 条关系；没有强关系时输出空数组
- 优先输出 `confused_with`、`prerequisite_of`、`used_for`、`asks_about`、`same_as`
- 严格限制 `related_to`：只有当两个 unit 在当前 note 中形成明确推理、解释或对照关系，且没有更具体的关系类型可用时才使用
- 不要因为两个 unit 同属一个主题、同篇论文或同次 session 就连接
- 不要输出“看起来相关但无法解释方向”的边
- relation 的 confidence 必须体现关系强度；低于 0.7 的关系不要输出

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
