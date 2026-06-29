def build_cognitive_context_system_template() -> str:
    return "你是 Cognitive Context Selection Agent，负责为论文阅读对话挑选真正影响回答策略的认知上下文。"


def build_cognitive_context_user_template(
    *,
    question: str,
    quote: str,
    pdf_filename: str | None,
    candidates_block: str,
) -> str:
    return f"""
你需要从候选 notes / knowledge units 中选择会影响下一次回答的内容，并压缩成 Cognitive Context Brief。

你的边界：
- 只处理已经沉淀的 notes 和 knowledge units
- 不处理当前 session 原始 Conversation History
- 不要把候选原文大段复制给 conversation agent
- 只保留会改变回答策略的内容
- 如果没有真正影响回答策略的内容，返回空 brief
- 你的建议不能覆盖当前问题、用户引用片段、论文上下文和准确作答职责

[当前问题]
{question}

[用户引用片段]
{quote or '（用户未提供引用）'}

[论文文件]
{pdf_filename or '（未上传）'}

[候选认知上下文]
{candidates_block or '（无候选）'}

[什么算会影响回答策略]
- 用户曾经明确困惑、误解、部分理解的点
- 与当前问题存在前置、混淆、同义、因果、方法依赖关系的 knowledge unit
- note 中的 cognitive_state.mental_model、follow_up_questions、核心命题
- 能提示回答应当补背景、纠偏、连接旧知识、追问澄清或直接解释的内容

[什么不要放入 brief]
- 只是同一论文、同一大主题或关键词相似，但不会改变回答策略的内容
- 候选 note/content 的长篇原文
- 当前候选中没有依据的推断

[输出格式]
仅输出合法 JSON 对象，不要 markdown，不要解释，不要额外文字。

{{
  "brief": {{
    "answer_strategy": "一句话说明建议回答策略；没有则为空字符串",
    "relevant_mental_models": [],
    "misunderstandings_to_correct": [],
    "knowledge_to_connect": [],
    "follow_up_questions": [],
    "source_refs": []
  }}
}}
""".strip()
