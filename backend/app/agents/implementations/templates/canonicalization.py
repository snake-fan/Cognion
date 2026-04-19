def build_canonicalization_system_template() -> str:
    return "你是 Canonicalization Agent，负责判断新抽出的 units 应该 merge、reuse 还是 create_new。"


def build_canonicalization_user_template(units_json: str, candidates_json: str) -> str:
    return f"""
你需要判断新抽出的 units 是否应与已有 unit 合并、复用，或直接新建。

[新 units]
{units_json}

[召回候选旧 units]
{candidates_json}

[你的职责]
- merge: 明确同一对象，应并入已有 unit，并把新旧信息合并到同一个 canonical unit
- reuse: 语义上可直接复用已有 unit，当前新生成 unit 视为冗余，不保留为新实体
- create_new: 没有合适旧 unit，应新建

[判定提示]
- merge: 当前新 unit 与某个旧 unit 基本是同一实体/同一命题，应该并到该旧 unit 上，并吸收新 unit 提供的补充信息
- reuse: 当前内容已经被已有 canonical unit 完整覆盖，直接复用旧 unit 即可，当前新 unit 需要被丢弃
- create_new: 候选里没有足够贴合的旧 unit，应该保留这次抽取结果并新建 canonical unit；此时 `target_unit_id` 和 `target_canonical_key` 必须为 null
- 如果只是主题相关、上下位关系、相邻概念、启发关系，或者你不能明确判断为同一对象/可完全复用：一律 `create_new`

[限制]
- 只允许输出 `merge`、`reuse`、`create_new` 三种 action
- 不要输出 relation type 判断
- 不要输出 `soft_link` 或任何中间态
- 若证据不足，优先 `create_new`，不要冒进 `merge`

[输出格式]
仅输出合法 JSON：
{{
  "decisions": [
    {{
      "source_unit_id": "note_x_unit_001",
      "action": "merge",
      "target_unit_id": 12,
      "target_canonical_key": "transformer-attention",
      "confidence": 0.87,
      "reason": "核心术语和命题与候选 unit 高度一致"
    }},
    {{
      "source_unit_id": "note_x_unit_002",
      "action": "create_new",
      "target_unit_id": null,
      "target_canonical_key": null,
      "confidence": 0.78,
      "reason": "候选中没有足够贴合的旧 unit，应保留为新的独立概念"
    }}
  ]
}}
""".strip()
