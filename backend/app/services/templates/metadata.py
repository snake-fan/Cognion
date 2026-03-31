def build_metadata_system_template() -> str:
    return "你是论文元信息抽取助手。你只返回严格 JSON，不输出解释、代码块或额外文本。"


def build_metadata_user_template(pdf_filename: str | None, pdf_context: str) -> str:
    return f"""
请从下面论文内容中抽取结构化元信息，并且只返回 JSON 对象。

JSON 字段必须包含：
- title
- authors
- research_topic
- journal
- publication_date
- summary

要求：
1. 不要返回 markdown，不要返回解释，只能返回 JSON。
2. 如果无法确定字段，使用“未知”或“未标注”。
3. `summary` 控制在 120 字以内。

[论文文件名]
{pdf_filename or '未知'}

[论文上下文节选]
{pdf_context or '无可用内容'}
""".strip()
