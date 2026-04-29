def build_unit_extraction_system_template() -> str:
    return "你是 Unit Extraction Agent，负责从单条 note 中抽取少量、短促、有连接价值的知识图谱锚点。"


def build_unit_extraction_user_template(note_json: str) -> str:
    return f"""
你现在只处理一条 note。
你能看到的输入只有下面这条 note 的 JSON，不包含其他 note，也不包含历史 unit 或全局候选。

目标：
1. 仅基于这条 note，抽取 0~2 个 knowledge units；没有清晰锚点时输出空数组
2. 每个 unit 必须是用户未来重新进入这条 note 的认知锚点，而不是对 note 的二次摘要
3. 只抽取 note 中明确出现或可直接概括出的内容，不补充 note 之外的信息
4. 优先从 note 的完整正文 content 中抽取，再参考 summary 与认知状态字段辅助判断

[抽取优先级]
只抽取以下三类高价值 unit：
- concept: 用户以后会反复遇到的核心术语、机制或对象
- distinction: 用户正在区分的两个概念、方法、结论或误解
- question: 真正值得继续追踪的认知卡点

`claim` 和 `method` 只有在它们是这条 note 的唯一核心锚点时才使用。

[输入 note]
{note_json}

[输出要求]
- 只依据这条 note
- 每个 unit 必须包含：
  - unit_id: 该 unit 在当前 note 内的唯一 ID
  - type: "concept" | "claim" | "method" | "question" | "distinction"
  - canonical_name: 该 unit 最合适的主名称；必须短、准、有力，优先 2~8 个中文字符或 1~4 个英文词
  - aliases: note 中出现过的别称、缩写、近义表达；没有则填 []
  - description: 一句极短说明，只写这个节点为什么值得存在；不要写成定义或解释段落
  - keywords: 便于检索的短关键词，最多 5 个；没有则填 []
  - slots: 仅保留真正有助于消歧的结构化补充字段；没有则填 {{}}
  - local_relations: 只有当前 note 内存在强关系时才输出；没有则填 []
- local_relations 每项包含：
  - target_unit_ref: 当前 note 内另一个 unit 的 unit_id
  - relation_type: "asks_about" | "related_to" | "confused_with" | "prerequisite_of" | "used_for" | "same_as"

[限制]
- 不要假设 note 之外的上下文
- 不要输出图数据库节点/边
- 不要把整条 note 原样复制成一个 unit
- 不要凭常识补全 note 中没有出现的信息
- 不要抽取背景词、宽泛学科名、完整句子、冗长命题或只出现一次且没有连接价值的细节
- 不要为了凑数量而拆出多个近义 unit；宁可只保留 1 个最有价值的锚点
- canonical_name 不要写成“如何/为什么/什么是...”这种长问题句；question 类型也要压缩成短问题焦点
- description 不要超过 30 个中文字符，除非英文术语导致自然变长
- 若 local_relations 不充分，宁可留空，也不要编造
- 若 note 主要是困惑，只抽 1 个 question 或 distinction 类型的核心卡点

[输出格式]
仅输出合法 JSON：
{{
  "units": [
    {{
      "unit_id": "note_x_unit_001",
      "type": "concept",
      "canonical_name": "核心锚点",
      "aliases": [],
      "description": "这个节点存在的理由",
      "keywords": [],
      "slots": {{}},
      "local_relations": []
    }}
  ]
}}
""".strip()
