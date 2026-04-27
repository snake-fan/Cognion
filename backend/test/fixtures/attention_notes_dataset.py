from __future__ import annotations

ATTENTION_PAPER = {
    "paper_title": "Attention Is All You Need",
    "paper_authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin",
    "paper_topic": "基于自注意力机制的 Transformer 模型与神经机器翻译",
    "paper_id": "paper-attention-fixture",
    "session_id": "session-attention-fixture",
}


ATTENTION_SESSION_MESSAGES = [
    {
        "role": "user",
        "quote": (
            "An attention function can be described as mapping a query and a set of key-value pairs to an output,\n"
            "where the query, keys, values, and output are all vectors."
        ),
        "content": "这里说的 mapping 具体是怎么做的？Q、K、V 分别起什么作用？",
    },
    {
        "role": "assistant",
        "quote": "",
        "content": (
            "这里的 mapping 指 attention 函数把 query 和一组 key-value pairs 变成输出向量。"
            "在 scaled dot-product attention 中，Q 和 K 先做相似度计算，得到分数后除以 sqrt(d_k)，"
            "再用 softmax 得到权重，最后用这些权重对 V 做加权求和。"
        ),
    },
    {
        "role": "user",
        "quote": "",
        "content": (
            "我之前误以为 QK 得到 attention 以后是去乘 K。现在理解应该是 QK 只是决定看哪些位置，"
            "真正被加权聚合的是 V，对吗？"
        ),
    },
    {
        "role": "assistant",
        "quote": "",
        "content": (
            "对。Q 和 K 决定注意力权重，V 承载被取回和聚合的信息。attention 的输出仍然是隐藏表示，"
            "不是最终 token。"
        ),
    },
    {
        "role": "user",
        "quote": (
            "Multi-head attention allows the model to jointly attend to information from different representation subspaces "
            "at different positions."
        ),
        "content": "那 multi-head 是不是把输入投影成多组 QKV，然后每组分别算 attention，最后再拼起来？",
    },
    {
        "role": "assistant",
        "quote": "",
        "content": (
            "是的。每个 head 有自己的投影矩阵，各自并行计算 attention，结果 concat 后再经过输出矩阵 W^O。"
            "这样不同 head 可以关注不同表示子空间和不同位置。"
        ),
    },
    {
        "role": "user",
        "quote": "",
        "content": (
            "我还有一个边界没搞清楚：如果 attention 已经聚合到了上下文，为什么不能直接预测下一个 token？"
            "是不是还需要 FFN 和最终 linear + softmax 把 hidden state 转到词表空间？"
        ),
    },
    {
        "role": "assistant",
        "quote": "",
        "content": (
            "是的。attention 主要做信息检索和聚合；FFN 对每个位置做非线性变换，多层堆叠继续加工表示，"
            "最后 linear + softmax 才把 decoder output 转成 next-token probabilities。"
        ),
    },
]


EXISTING_TOPIC_KEYS = [
    "attention-qk-v-weighted-sum",
]


EXISTING_KNOWLEDGE_UNITS = [
    {
        "knowledge_unit_id": 101,
        "canonical_key": "scaled-dot-product-attention",
        "unit_type": "concept",
        "term": "Scaled Dot-Product Attention",
        "core_claim": "Scaled dot-product attention computes QK^T / sqrt(d_k), normalizes with softmax, and applies the weights to V.",
        "summary": "Q and K determine attention weights; V is the information being aggregated.",
        "aliases": ["attention", "注意力机制", "QK attention"],
        "related_terms": ["query", "key", "value", "softmax", "weighted sum"],
        "slots": {"equation": "softmax(QK^T / sqrt(d_k))V"},
    },
    {
        "knowledge_unit_id": 102,
        "canonical_key": "multi-head-attention",
        "unit_type": "concept",
        "term": "Multi-Head Attention",
        "core_claim": "Multi-head attention projects Q, K, and V into multiple heads, computes attention in parallel, concatenates the heads, and applies W^O.",
        "summary": "Different heads can attend to different representation subspaces and positions.",
        "aliases": ["多头注意力", "multihead attention"],
        "related_terms": ["attention head", "representation subspace", "concat", "W^O"],
        "slots": {"heads": "parallel attention branches"},
    },
    {
        "knowledge_unit_id": 103,
        "canonical_key": "position-wise-feed-forward-network",
        "unit_type": "concept",
        "term": "Position-wise Feed-Forward Network",
        "core_claim": "The FFN applies two linear transformations with a ReLU to each position separately and identically.",
        "summary": "The FFN transforms and refines the hidden representation after attention.",
        "aliases": ["FFN", "feed-forward network", "前馈网络"],
        "related_terms": ["ReLU", "hidden representation", "nonlinear transformation"],
        "slots": {"equation": "max(0, xW1 + b1)W2 + b2"},
    },
    {
        "knowledge_unit_id": 104,
        "canonical_key": "decoder-output-token-probabilities",
        "unit_type": "claim",
        "term": "Decoder output to next-token probabilities",
        "core_claim": "The decoder output is converted to predicted next-token probabilities by a learned linear transformation and softmax.",
        "summary": "Attention output is not itself a token prediction; it must be mapped from hidden space to vocabulary space.",
        "aliases": ["output projection", "linear softmax", "词表概率"],
        "related_terms": ["decoder output", "vocabulary", "softmax", "next token"],
        "slots": {"stage": "final prediction"},
    },
    {
        "knowledge_unit_id": 105,
        "canonical_key": "recurrent-sequential-computation",
        "unit_type": "concept",
        "term": "Recurrent Sequential Computation",
        "core_claim": "Recurrent models process sequence positions step by step, limiting parallelization.",
        "summary": "This is related to Transformer motivation but should not be merged with attention mechanics.",
        "aliases": ["RNN sequential computation"],
        "related_terms": ["recurrence", "parallelization"],
        "slots": {},
    },
]
