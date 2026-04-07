from __future__ import annotations

import asyncio

from .agents.orchestrator import build_default_orchestrator


async def demo_qa() -> None:
    orchestrator = build_default_orchestrator()
    answer = await orchestrator.answer_qa(
        question="这篇论文的核心贡献是什么？",
        quote="",
        pdf_bytes=None,
        pdf_filename=None,
        local_pdf_path=None,
    )
    print(answer)


if __name__ == "__main__":
    asyncio.run(demo_qa())
