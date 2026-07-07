def build_session_name_system_template() -> str:
    return """你是 Chat Session 命名助手。

任务：根据用户在一个新 Session 里的第一句问题，生成一个简短、具体、便于回看的 session name。

要求：
- 只概括用户问题的核心对象、关系或任务，不要回答问题。
- 中文优先使用 4 到 16 个字；英文优先使用 2 到 6 个词。
- 不要使用“Session”“会话”“问题”“讨论”等泛化词。
- 不要输出编号、引号、句号或解释。
- 只输出 JSON：{"name":"..."}"""


def build_session_name_user_template(
    *,
    question: str,
    quote: str,
    paper_title: str,
    paper_topic: str,
) -> str:
    quote_block = quote.strip() or "（无）"
    return f"""请为下面这个新 Session 生成名称。

## 论文信息
标题：{paper_title or '未知'}
主题：{paper_topic or '未知'}

## 用户第一句问题
{question.strip()}

## 用户选中的引用（可选，仅用于辅助理解）
{quote_block}

输出 JSON："""
