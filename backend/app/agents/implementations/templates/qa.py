from ...schemas import ModelMessageContent


def build_qa_system_template() -> str:
    return "你是一个学术论文阅读助手，擅长基于给定上下文做准确、克制、可验证的回答。"


def _build_qa_text_prompt(question: str, quote: str, pdf_filename: str | None, pdf_context: str) -> str:
    context_section = (
        f"""
[论文上下文（节选）]
{pdf_context}
""".strip()
        if pdf_context
        else """
[论文上下文（节选）]
（无可用内容）
""".strip()
    )

    return f"""
你是一个学术论文阅读助手，请基于用户问题、引用片段和论文上下文作答。

[用户问题]
{question}

[用户引用片段]
{quote or '（用户未提供引用）'}

[论文文件]
{pdf_filename or '（未上传）'}

{context_section}

要求：
1. 先直接回答问题。
2. 明确指出回答与引用片段的关系。
3. 如果信息不足，明确说明还缺少什么。
""".strip()


def _build_qa_file_prompt(question: str, quote: str, pdf_filename: str | None) -> str:
    return f"""
你是一个学术论文阅读助手，请基于用户问题、引用片段和随消息附上的 PDF 文件作答。

[用户问题]
{question}

[用户引用片段]
{quote or '（用户未提供引用）'}

[论文文件]
{pdf_filename or '（未上传）'}

要求：
1. 先直接回答问题。
2. 明确指出回答与引用片段的关系。
3. 如果信息不足，明确说明还缺少什么。
""".strip()


def build_qa_user_template(
    question: str,
    quote: str,
    pdf_filename: str | None,
    pdf_context: str,
    pdf_file_url: str = "",
) -> ModelMessageContent:
    if pdf_file_url:
        return [
            {"type": "text", "text": _build_qa_file_prompt(question, quote, pdf_filename)},
            {"type": "input_file", "file_url": pdf_file_url},
        ]

    return _build_qa_text_prompt(question, quote, pdf_filename, pdf_context)
