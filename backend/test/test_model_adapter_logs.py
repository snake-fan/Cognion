import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from backend.app.agents.model_adapter import OpenAIModelAdapter, TraceJsonInvocationLogSink, default_log_sink
from backend.app.agents.schemas import LLMInvocationLog, ModelMessage


class CaptureLogSink:
    def __init__(self):
        self.logs = []

    def write(self, log):
        self.logs.append(log)


class FakeStreamingAdapter(OpenAIModelAdapter):
    def __init__(self, *, chunks, log_sink):
        super().__init__(api_key="test-key", base_url="https://example.test/v1", default_model="test-model", log_sink=log_sink)
        self._chunks = chunks

    def _build_client(self):
        chunks = self._chunks

        class FakeCompletions:
            async def create(self, **_kwargs):
                async def stream():
                    for chunk in chunks:
                        yield chunk

                return stream()

        return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))


def fake_stream_chunk(content, *, finish_reason=None):
    return SimpleNamespace(
        id="chatcmpl-test",
        model="test-model",
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
    )


class ModelAdapterLogTests(unittest.TestCase):
    def test_trace_json_sink_writes_readable_trace_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sink = TraceJsonInvocationLogSink(Path(temp_dir))
            log = LLMInvocationLog(
                timestamp=datetime(2026, 4, 26, 12, 30, 1, 123456),
                trace_id="trace/one",
                workflow="notes",
                paper_id="paper/1",
                session_id="session-1",
                agent_name="note_agent",
                messages=[ModelMessage(role="user", content="生成笔记")],
                raw_response={"choices": []},
                pre_parse_text='{"notes":[]}',
                latency_ms=42,
            )

            sink.write(log)

            files = list(Path(temp_dir).glob("**/*.json"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, "20260426T123001123456-trace_one.json")
            self.assertEqual(files[0].parent, Path(temp_dir) / "notes" / "paper-paper_1" / "session-session-1")
            content = files[0].read_text(encoding="utf-8")
            self.assertIn("\n  ", content)
            payload = json.loads(content)
            self.assertEqual(payload["trace_id"], "trace/one")
            self.assertEqual(payload["workflow"], "notes")
            self.assertEqual(payload["paper_id"], "paper/1")
            self.assertEqual(payload["messages"][0]["content"], "生成笔记")

    def test_default_log_sink_uses_backend_storage(self):
        sink = default_log_sink()

        self.assertIsInstance(sink, TraceJsonInvocationLogSink)
        self.assertEqual(sink._directory_path.name, "llm_invocations")
        self.assertEqual(sink._directory_path.parent.name, "storage")
        self.assertEqual(sink._directory_path.parent.parent.name, "backend")


class ModelAdapterStreamLogTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_via_stream_returns_collected_text(self):
        log_sink = CaptureLogSink()
        adapter = FakeStreamingAdapter(
            chunks=[
                fake_stream_chunk("好"),
                fake_stream_chunk("的"),
                fake_stream_chunk(None, finish_reason="stop"),
            ],
            log_sink=log_sink,
        )

        result = await adapter.call_via_stream(
            trace_id="trace-2",
            workflow="notes",
            paper_id="paper-1",
            session_id="session-1",
            agent_name="note_agent",
            messages=[ModelMessage(role="user", content="generate notes")],
        )

        self.assertEqual(result.text, "好的")
        self.assertEqual(result.raw_response["stream"], True)
        self.assertEqual(result.raw_response["text"], "好的")
        self.assertEqual(len(log_sink.logs), 1)
        self.assertEqual(log_sink.logs[0].pre_parse_text, "好的")

    async def test_stream_log_uses_final_text_instead_of_raw_chunks(self):
        log_sink = CaptureLogSink()
        adapter = FakeStreamingAdapter(
            chunks=[
                fake_stream_chunk("你"),
                fake_stream_chunk("好"),
                fake_stream_chunk(None, finish_reason="stop"),
            ],
            log_sink=log_sink,
        )

        tokens = []
        async for token in adapter.stream(
            trace_id="trace-1",
            workflow="conversation",
            paper_id="paper-1",
            session_id="session-1",
            agent_name="qa_agent_stream",
            messages=[ModelMessage(role="user", content="hello")],
        ):
            tokens.append(token)

        self.assertEqual(tokens, ["你", "好"])
        self.assertEqual(len(log_sink.logs), 1)
        log = log_sink.logs[0]
        self.assertEqual(log.pre_parse_text, "你好")
        self.assertEqual(log.raw_response["text"], "你好")
        self.assertEqual(log.raw_response["chunk_count"], 3)
        self.assertEqual(log.raw_response["finish_reason"], "stop")
        self.assertNotIn("chunks", log.raw_response)


if __name__ == "__main__":
    unittest.main()
