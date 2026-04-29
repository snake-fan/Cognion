def build_canonicalization_system_template() -> str:
    return "你是 Canonicalization Agent，负责判断新抽出的 units 应该 merge、reuse 还是 create_new。"


def build_canonicalization_user_template(units_json: str, candidates_json: str) -> str:
    return f"""
你需要判断新抽出的 units 是否应与已有 unit 合并、复用，或直接新建。
这些 units 是短促的知识图谱锚点，不是完整解释文本；判断时优先看“用户未来会不会用同一个节点重新进入相关 note”。

[新 units]
{units_json}

[召回候选旧 units]
{candidates_json}

[你的职责]
- merge: 明确同一对象，应并入已有 unit，并把新旧信息合并到同一个 canonical unit
- reuse: 语义上可直接复用已有 unit，当前新生成 unit 视为冗余，不保留为新实体
- create_new: 没有合适旧 unit，应新建

[判定提示]
- merge: 当前新 unit 与某个旧 unit 指向同一术语、机制、问题焦点或关键区分，且新 unit 带来可吸收的别名、表述或轻微补充
- reuse: 当前新 unit 已被某个旧 unit 作为认知锚点覆盖，即使 wording 不同，也没有必要新增节点
- create_new: 候选里没有足够贴合的旧 unit，且该 unit 代表一个用户以后确实需要单独回到的认知锚点；此时 `target_unit_id` 和 `target_canonical_key` 必须为 null
- 如果只是主题相关、上下位关系、相邻概念或启发关系，不要 merge；但如果新 unit 只是旧 unit 的更啰嗦说法，应优先 reuse
- 对短标签型 unit，允许比完整命题更积极地 reuse/merge；不要因为描述细节不同就轻易 create_new

[限制]
- 只允许输出 `merge`、`reuse`、`create_new` 三种 action
- 不要输出 relation type 判断
- 不要输出 `soft_link` 或任何中间态
- create_new 的门槛要高：只有旧图谱没有可复用锚点时才新建
- 若不确定是 merge 还是 reuse，优先 reuse
- 若不确定是否值得新建，优先 reuse 最贴近的候选；没有候选时才 create_new

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
