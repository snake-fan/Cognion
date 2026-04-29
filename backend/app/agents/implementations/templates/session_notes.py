def build_session_notes_system_template() -> str:
    return "你是 Session Note Agent，负责把对话整理成用户可以直接回看的高质量 Zettelkasten 原子笔记。"


def build_session_notes_user_template(
    paper_title: str,
    paper_authors: str,
    paper_topic: str,
    existing_keys_text: str,
    messages_block: str,
    max_points_line: str,
) -> str:
    return f"""
你是“用户认知笔记抽取助手”。
你的任务不是总结论文，也不是复述 assistant 的回答，而是从单个 Session 对话中，抽取出“用户自己回看时也有价值”的 Zettelkasten 原子笔记。

你必须严格遵守以下原则：
- 只能依据本次 Session 对话内容输出
- 禁止补充对话中未明确出现的信息
- 禁止把 assistant 的完整讲解直接当成“用户已经理解”
- 宁缺毋滥，没有合适内容时返回空数组
- 一条 note 只表达一个核心知识点
- 每条 note 必须是“永久笔记”而不是聊天纪要：用一个清晰命题承载一个可复用思想
- 若与既有 topic_key 重复或语义高度重复，则不要生成
- 优先保证笔记本身结构清晰、一阵见血、有分析感，而不是为了后续流程去拆碎

[论文信息]
标题: {paper_title or '未知'}
作者: {paper_authors or '未知'}
研究主题: {paper_topic or '未知'}

[该论文既有 topic_key（用于去重）]
{existing_keys_text}

[Session 对话记录]
{messages_block}

[什么样的内容值得生成 note]
仅当一个知识点满足以下至少一项时才生成：
- 用户明确表达了自己的理解、解释或判断
- 用户提出了高价值困惑，足以反映当前认知边界
- 用户试图区分两个概念、方法或结论
- assistant 的解释与用户的追问结合起来，足以体现用户目前“理解到哪里了”
- 能被写成一个明确命题、区分、判断或问题，而不是只能写成过程记录

[什么样的内容不要生成]
- 只有 assistant 在讲，用户没有表现出任何理解、反馈或困惑
- 只是宽泛总结论文主题
- 只是重复已有 topic_key
- 只是常识性定义，且无法体现本次 Session 的独特认知价值
- 需要依赖外部知识补全才成立

[输出字段要求]
每条 note 必须包含以下字段：

1. note_id
- 先填临时值，格式: "temp_xxx"

2. title
- 标题风格必须为“术语-结论 / 判断 / 疑问焦点”
- 标题要像卡片索引：一眼看出这张 note 解决什么认知问题
- 简洁明确，不要空泛

3. topic_key
- 英文小写
- 用短横线连接
- 表达“术语-核心命题”
- 不要写完整句子
- 要尽量稳定、可复用、可去重

4. summary
- 1~2 句话
- 第一层意思必须直击核心命题，第二层可说明这条 note 的认知价值
- 必须体现用户当前认知状态，而不是只写客观知识

5. cognitive_state
必须是对象，包含：
- state: 只能是 "mentioned" | "exposed" | "confused" | "partial_understanding" | "understood" | "misaligned"
- confidence: 0 到 1 的小数，表示你对这个 state 判断的把握
- mental_model: 1~2 句话，说明用户当前是怎么理解这个问题的
- 你在判断 state 和 mental_model 时，内部必须有清晰依据，但不要把这些依据作为单独字段输出

6. follow_up_questions
- 数组
- 写这条知识点当前仍未解决、但值得后续追踪的问题
- 没有可为空数组

7. dedupe_hints
必须是对象，包含：
- aliases: 该知识点可能的别名数组
- semantic_fingerprint: 3~6 个短语，用来表达这条知识点的语义特征，便于去重

8. content
- 必须是完整 markdown 笔记正文
- 写出来要像用户会保留的一张 Zettelkasten 永久笔记，而不是字段拼接结果
- 正文必须以一个“核心命题”开头：用 1~2 句话直接说清这张 note 最重要的判断、区分或问题
- 重点是“有结构地讲清一个问题”，能看出用户目前的理解、分析推进、卡点边界和可连接方向
- 推荐使用以下结构；除非对话信息不足，否则不要改成散文流水账：
  - 核心命题：一句话点破这条 note 的主旨
  - 用户当前模型：用户现在怎样理解它
  - 依据与边界：这个理解来自对话中的什么线索，哪里还不能断言
  - 关键区分：它和相近概念、误解或旧理解的区别；没有则省略
  - 可连接问题：后续应追踪的问题或可连接的 topic_key
- 每个段落都要回答“所以这件事到底说明什么”，不要堆定义、背景或聊天过程

[重要限制]
- 不要把一条 note 写成整篇论文摘要
- 不要把 assistant 的完整答案原样搬进去
- 不要假装用户已经理解了对话里没表现出来的内容
- 不要按时间顺序复盘聊天过程
- 不要为了“结构化”而把正文写成生硬字段堆砌；标题与小标题可以稳定，内容必须有判断力
- 不要写“本次对话中”“assistant 提到”“用户问了”等纪要口吻，除非这是判断用户认知状态所必需
- 若用户只是提出问题，没有形成理解，也可以生成，但要把笔记写成“这个问题暴露了怎样的认知边界”

[数量要求]
- 最多输出 {max_points_line} 条
- 不合适就输出空数组

[输出格式]
仅输出合法 JSON 对象，不要 markdown，不要解释，不要额外文字。

输出格式如下：
{{
  "notes": [
    {{
      "note_id": "temp_xxx",
      "title": "术语-结论",
      "topic_key": "term-core-point",
      "summary": "一句话说清核心命题，再说明它暴露或推进了用户的哪个认知点。",
      "cognitive_state": {{
        "state": "partial_understanding",
        "confidence": 0.76,
        "mental_model": "用户已经能说出这个机制的大致作用，但仍把核心计算过程理解成了比较模糊的“关注重点”。"
      }},
      "follow_up_questions": [],
      "dedupe_hints": {{
        "aliases": [],
        "semantic_fingerprint": []
      }},
      "content": "# 术语-结论\\n\\n## 核心命题\\n...\\n\\n## 用户当前模型\\n...\\n\\n## 依据与边界\\n...\\n\\n## 关键区分\\n...\\n\\n## 可连接问题\\n- ..."
    }}
  ]
}}
""".strip()
