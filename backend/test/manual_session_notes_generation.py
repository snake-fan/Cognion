from __future__ import annotations

import argparse
import asyncio
import json
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

from backend.app.agents.implementations.orchestrators.notes import NotesOrchestrator
from backend.app.agents.model_adapter import OpenAIModelAdapter, TraceJsonInvocationLogSink
from backend.test.fixtures.attention_notes_dataset import (
    ATTENTION_PAPER,
    ATTENTION_SESSION_MESSAGES,
    EXISTING_KNOWLEDGE_UNITS,
    EXISTING_TOPIC_KEYS,
)


def _install_agent_timeouts(orchestrator: NotesOrchestrator, timeout_seconds: float) -> None:
    for agent_name in ["note_agent", "unit_extraction_agent", "canonicalization_agent", "relation_agent"]:
        agent = orchestrator.get_agent(agent_name)
        agent.timeout_seconds = timeout_seconds


def _print_notes(notes: list[dict[str, object]]) -> None:
    print(f"notes_count={len(notes)}")
    for index, note in enumerate(notes, start=1):
        cognitive_state = note.get("cognitive_state") if isinstance(note.get("cognitive_state"), dict) else {}
        print(f"note[{index}].id={note.get('note_id')}")
        print(f"note[{index}].title={note.get('title')}")
        print(f"note[{index}].topic_key={note.get('topic_key')}")
        print(f"note[{index}].state={cognitive_state.get('state')}")
        print(f"note[{index}].summary={note.get('summary')}")


def _print_graph_patch(graph_patch: dict[str, object]) -> None:
    unit_sections = ["units_to_create", "units_to_merge", "units_to_link", "relations_to_create"]
    for section in unit_sections:
        items = graph_patch.get(section)
        count = len(items) if isinstance(items, list) else 0
        print(f"{section}_count={count}")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            summary = {
                "note_id": item.get("note_id"),
                "source_unit_id": item.get("source_unit_id"),
                "action": item.get("action"),
                "target_unit_id": item.get("target_unit_id"),
                "canonical_name": item.get("canonical_name"),
                "relation_type": item.get("relation_type"),
                "from_unit_ref": item.get("from_unit_ref"),
                "to_unit_ref": item.get("to_unit_ref"),
            }
            compact = {key: value for key, value in summary.items() if value not in (None, "")}
            print(f"{section}[{index}]={json.dumps(compact, ensure_ascii=False)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run real LLM session-note generation against the Attention fixture.")
    parser.add_argument(
        "--stage",
        choices=["notes-only", "full"],
        default="full",
        help="notes-only disables existing knowledge units, so only note generation and unit creation fallback are exercised.",
    )
    parser.add_argument("--max-points", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--wait-timeout", type=float, default=300.0)
    parser.add_argument("--trace-id", default="manual-attention-notes")
    args = parser.parse_args()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_url = os.getenv("OPENAI_URL", "https://api.openai.com/v1")
    log_sink = TraceJsonInvocationLogSink(BACKEND_DIR / "storage" / "llm_invocations")
    adapter = OpenAIModelAdapter(
        api_key=openai_api_key,
        base_url=openai_url,
        default_model=openai_model,
        max_retries=0,
        log_sink=log_sink,
    )
    orchestrator = NotesOrchestrator(adapter)
    _install_agent_timeouts(orchestrator, args.timeout)

    existing_units = EXISTING_KNOWLEDGE_UNITS if args.stage == "full" else []
    existing_topic_keys = EXISTING_TOPIC_KEYS if args.stage == "full" else []

    print(f"model={openai_model}")
    print(f"base_url={openai_url}")
    print(f"stage={args.stage}")
    print(f"max_points={args.max_points}")
    print(f"timeout_seconds={args.timeout}")
    print(f"existing_units_count={len(existing_units)}")

    started = time.perf_counter()
    result = await asyncio.wait_for(
        orchestrator.generate_session_notes(
            paper_title=ATTENTION_PAPER["paper_title"],
            paper_authors=ATTENTION_PAPER["paper_authors"],
            paper_topic=ATTENTION_PAPER["paper_topic"],
            session_messages=ATTENTION_SESSION_MESSAGES,
            existing_topic_keys=existing_topic_keys,
            existing_knowledge_units=existing_units,
            max_points=args.max_points,
            trace_id=args.trace_id,
            paper_id=ATTENTION_PAPER["paper_id"],
            session_id=ATTENTION_PAPER["session_id"],
        ),
        timeout=args.wait_timeout,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    print(f"returned_after_ms={elapsed_ms}")
    notes = result.get("notes") if isinstance(result.get("notes"), list) else []
    graph_patch = result.get("graph_patch") if isinstance(result.get("graph_patch"), dict) else {}
    _print_notes(notes)
    _print_graph_patch(graph_patch)


if __name__ == "__main__":
    asyncio.run(main())
