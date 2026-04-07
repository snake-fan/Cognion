def build_fallback_message(prompt: str) -> str:
    return (
        "[本地占位回复] 检测到未配置 OPENAI_API_KEY。"
        "你提交的问题和引用已成功到达后端。"
        "请在 backend/.env 中配置 OPENAI_API_KEY 后即可切换到真实大模型回答。\n\n"
        f"Prompt Preview:\n{prompt[:800]}"
    )
