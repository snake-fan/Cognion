from ...schemas import ModelMessageContent


def build_qa_system_template() -> str:
    return """
# Purpose
你是学术论文阅读助手，负责基于当前问题、引用片段、论文上下文和对话上下文，给出准确、克制、可验证的回答。

# Upstream Context Handling
- 当前用户问题是最高优先级。
- 用户引用片段和论文上下文 / 随消息附上的 PDF 文件是论文证据来源。
- Conversation History 只用于保持当前会话连续性。
- Cognitive Context Brief 只用于调整回答策略；不要把 brief 当作论文证据。
- 当上下文之间冲突时，以当前问题、引用片段和论文证据为准，并明确说明不确定处。

# Responsibility Boundary
- 你负责回答当前论文阅读问题，说明回答与引用片段的关系，并指出信息不足处。
- 你不负责重新选择 Cognitive Context，不把历史笔记当论文事实，不编造论文中没有依据的内容。
- 除非用户明确要求，不输出整篇论文摘要或泛泛背景讲解。

# Reasoning Protocol
- 先识别用户真正要解决的问题和引用片段的作用。
- 再核对论文证据、Conversation History 和 Cognitive Context Brief 对回答策略的影响。
- 最后组织一个直接、可追溯、有必要边界说明的回答。

# Deliverable Specification
输出自然语言回答；先直接回答问题，再补充依据、引用关系、必要解释和限制。
""".strip()


def _format_conversation_history(conversation_history: list[dict[str, str]] | None) -> str:
    if not conversation_history:
        return "（无历史对话）"

    lines: list[str] = []
    for message in conversation_history:
        role = "用户" if message.get("role") == "user" else "助手"
        quote = str(message.get("quote") or "").strip()
        content = str(message.get("content") or "").strip()
        if quote:
            lines.append(f"[{role}引用]\n{quote}")
        if content:
            lines.append(f"[{role}]\n{content}")
    return "\n\n".join(lines).strip() or "（无历史对话）"


def _format_cognitive_context_brief(cognitive_context_brief: dict[str, object] | None) -> str:
    if not cognitive_context_brief:
        return "（无会影响本次回答的已沉淀认知上下文）"

    labels = [
        ("answer_strategy", "回答策略建议"),
        ("relevant_mental_models", "相关用户心智模型"),
        ("misunderstandings_to_correct", "需要纠正的误解"),
        ("knowledge_to_connect", "可连接的既有知识"),
        ("follow_up_questions", "可延展追问"),
        ("source_refs", "来源引用"),
    ]
    lines: list[str] = []
    for key, label in labels:
        value = cognitive_context_brief.get(key)
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            if items:
                lines.append(f"{label}:")
                lines.extend(f"- {item}" for item in items)
        else:
            text = str(value or "").strip()
            if text:
                lines.append(f"{label}: {text}")
    return "\n".join(lines).strip() or "（无会影响本次回答的已沉淀认知上下文）"


def _build_qa_text_prompt(
    question: str,
    quote: str,
    pdf_filename: str | None,
    pdf_context: str,
    conversation_history: list[dict[str, str]] | None,
    cognitive_context_brief: dict[str, object] | None,
) -> str:
    context_section = (
        f"""
## 论文上下文（节选）
{pdf_context}
""".strip()
        if pdf_context
        else """
## 论文上下文（节选）
（无可用内容）
""".strip()
    )

    return f"""
# Task
请基于用户问题、引用片段和论文上下文作答。

# Inputs
## 用户问题
{question}

## 用户引用片段
{quote or '（用户未提供引用）'}

## 论文文件
{pdf_filename or '（未上传）'}

## Conversation History（当前会话近期历史）
{_format_conversation_history(conversation_history)}

## Cognitive Context Brief（已沉淀认知上下文，仅作为回答策略参考）
{_format_cognitive_context_brief(cognitive_context_brief)}

{context_section}

# Task Execution Flow
1. 先直接回答问题。
2. 明确指出回答与引用片段的关系。
3. 结合 Conversation History 保持本轮对话连续性。
4. 只在 Cognitive Context Brief 影响回答策略时参考它；不要把 brief 当作论文证据。
5. 如果信息不足，明确说明还缺少什么。
""".strip()


def _build_qa_file_prompt(
    question: str,
    quote: str,
    pdf_filename: str | None,
    conversation_history: list[dict[str, str]] | None,
    cognitive_context_brief: dict[str, object] | None,
) -> str:
    return f"""
# Task
请基于用户问题、引用片段和随消息附上的 PDF 文件作答。

# Inputs
## 用户问题
{question}

## 用户引用片段
{quote or '（用户未提供引用）'}

## 论文文件
{pdf_filename or '（未上传）'}

## Conversation History（当前会话近期历史）
{_format_conversation_history(conversation_history)}

## Cognitive Context Brief（已沉淀认知上下文，仅作为回答策略参考）
{_format_cognitive_context_brief(cognitive_context_brief)}

# Task Execution Flow
1. 先直接回答问题。
2. 明确指出回答与引用片段的关系。
3. 结合 Conversation History 保持本轮对话连续性。
4. 只在 Cognitive Context Brief 影响回答策略时参考它；不要把 brief 当作论文证据。
5. 如果信息不足，明确说明还缺少什么。
""".strip()


def build_qa_user_template(
    question: str,
    quote: str,
    pdf_filename: str | None,
    pdf_context: str,
    pdf_file_url: str = "",
    conversation_history: list[dict[str, str]] | None = None,
    cognitive_context_brief: dict[str, object] | None = None,
) -> ModelMessageContent:
    if pdf_file_url:
        return [
            {
                "type": "text",
                "text": _build_qa_file_prompt(
                    question,
                    quote,
                    pdf_filename,
                    conversation_history,
                    cognitive_context_brief,
                ),
            },
            {"type": "input_file", "file_url": pdf_file_url},
        ]

    return _build_qa_text_prompt(
        question,
        quote,
        pdf_filename,
        pdf_context,
        conversation_history,
        cognitive_context_brief,
    )
