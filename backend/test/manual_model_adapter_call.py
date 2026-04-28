from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(BACKEND_DIR / ".env", override=False)

from backend.app.agents.model_adapter import OpenAIModelAdapter
from backend.app.agents.schemas import ModelCallParams, ModelMessage


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test OpenAIModelAdapter.call with a tiny non-streaming request.")
    parser.add_argument("--timeout", type=float, default=300.0, help="OpenAI request timeout in seconds.")
    parser.add_argument("--wait-timeout", type=float, default=300.0, help="Outer asyncio wait timeout in seconds.")
    parser.add_argument("--max-tokens", type=int, default=32, help="Maximum completion tokens.")
    args = parser.parse_args()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_url = os.getenv("OPENAI_URL", "https://api.openai.com/v1")

    adapter = OpenAIModelAdapter(
        api_key=openai_api_key,
        base_url=openai_url,
        default_model=openai_model,
        max_retries=0,
    )
    messages = [
        ModelMessage(role="system", content="You are a concise test assistant."),
        ModelMessage(role="user", content=[
            {
                "type":"text",
                "text":"What is in this file?"
            }, 
            {
                "type":"input_file",
                "file_url":"https://cognion-outside.oss-ap-southeast-1.aliyuncs.com/cognion/mineru/6c7f546de41c4f8c9b7bb86b1ef0c5b4.pdf"
            }
        ]),
    ]

    print(f"model={openai_model}")
    print(f"base_url={openai_url}")
    print(f"timeout_seconds={args.timeout}")
    print(f"max_tokens={args.max_tokens}")

    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            adapter.call(
                trace_id="manual-model-adapter-call",
                workflow="manual-test",
                paper_id=None,
                session_id=None,
                agent_name="manual_call_test",
                messages=messages,
                params=ModelCallParams(
                    temperature=0.0,
                    timeout_seconds=args.timeout,
                    max_tokens=args.max_tokens,
                ),
            ),
            timeout=args.wait_timeout,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print(f"failed_after_ms={elapsed_ms}")
        print(f"exception_type={type(exc).__name__}")
        print(f"exception={exc}")
        raise

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    print(f"returned_after_ms={elapsed_ms}")
    print(f"adapter_latency_ms={result.latency_ms}")
    print(f"text={result.text!r}")
    print(f"raw_response_is_null={result.raw_response is None}")
    print(f"usage={result.token_usage.model_dump() if result.token_usage else None}")


if __name__ == "__main__":
    asyncio.run(main())
