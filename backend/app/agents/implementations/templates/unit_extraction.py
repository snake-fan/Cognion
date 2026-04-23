def build_unit_extraction_system_template() -> str:
    return "你是 Unit Extraction Agent，负责从单条 note 中抽取可供知识图谱消费的 knowledge units。"


def build_unit_extraction_user_template(note_json: str) -> str:
    return f"""
你现在只处理一条 note。
你能看到的输入只有下面这条 note 的 JSON，不包含其他 note，也不包含历史 unit 或全局候选。

目标：
1. 仅基于这条 note，抽取 1~5 个 knowledge units
2. 每个 unit 必须表达一个清晰、可复用的知识点
3. 只抽取 note 中明确出现或可直接概括出的内容，不补充 note 之外的信息
4. 优先从 note 的完整正文 content 中抽取，再参考 summary 与认知状态字段辅助判断

[输入 note]
{note_json}

[输出要求]
- 只依据这条 note
- 每个 unit 必须包含：
  - unit_id: 该 unit 在当前 note 内的唯一 ID
  - type: "concept" | "claim" | "method" | "question" | "distinction"
  - canonical_name: 该 unit 最合适的主名称
  - aliases: note 中出现过的别称、缩写、近义表达；没有则填 []
  - description: 用 1~2 句话概括该 unit 的核心含义
  - keywords: 便于检索的关键词；没有则填 []
  - slots: 可选的结构化补充字段；没有则填 {{}}
  - local_relations: 当前 note 内该 unit 与其他 unit 的局部关系候选；没有则填 []
- local_relations 每项包含：
  - target_unit_ref: 当前 note 内另一个 unit 的 unit_id
  - relation_type: "asks_about" | "related_to" | "confused_with" | "prerequisite_of" | "used_for" | "same_as"

[限制]
- 不要假设 note 之外的上下文
- 不要输出图数据库节点/边
- 不要把整条 note 原样复制成一个 unit
- 不要凭常识补全 note 中没有出现的信息
- 若 local_relations 不充分，宁可留空，也不要编造
- 若 note 主要是困惑，可抽成 question 或 distinction 类型

[输出格式]
仅输出合法 JSON：
{{
  "units": [
    {{
      "unit_id": "note_x_unit_001",
      "type": "concept",
      "canonical_name": "核心术语",
      "aliases": [],
      "description": "该 unit 的简要定义或命题",
      "keywords": [],
      "slots": {{}},
      "local_relations": []
    }}
  ]
}}
""".strip()
