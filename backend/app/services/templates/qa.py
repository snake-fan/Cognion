def build_qa_system_template() -> str:
    return "你是一个学术论文阅读助手，擅长基于给定上下文做准确、克制、可验证的回答。"


def build_qa_user_template(question: str, quote: str, pdf_filename: str | None, pdf_context: str) -> str:
    return f"""
你是一个学术论文阅读助手，请基于用户问题、引用片段和论文上下文作答。

[用户问题]
{question}

[用户引用片段]
{quote or '（用户未提供引用）'}

[论文文件]
{pdf_filename or '（未上传）'}

[论文上下文（节选）]
{pdf_context or '（无可用内容）'}

要求：
1. 先直接回答问题。
2. 明确指出回答与引用片段的关系。
3. 如果信息不足，明确说明还缺少什么。
""".strip()
