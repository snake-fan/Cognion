import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from backend.app.agents.model_adapter import OpenAIModelAdapter, TraceJsonInvocationLogSink, default_log_sink
from backend.app.agents.schemas import LLMInvocationLog, ModelCallParams, ModelMessage


class CaptureLogSink:
    def __init__(self):
        self.logs = []

    def write(self, log):
        self.logs.append(log)


class FakeStreamingAdapter(OpenAIModelAdapter):
    def __init__(self, *, chunks=None, response_events=None, response_stream_error=None, log_sink):
        super().__init__(api_key="test-key", base_url="https://example.test/v1", default_model="test-model", log_sink=log_sink)
        self._chunks = chunks or []
        self._response_events = response_events or []
        self._response_stream_error = response_stream_error
        self.chat_calls = []
        self.response_calls = []

    def _build_client(self):
        chunks = self._chunks
        response_events = self._response_events
        response_stream_error = self._response_stream_error
        chat_calls = self.chat_calls
        response_calls = self.response_calls

        class FakeCompletions:
            async def create(self, **kwargs):
                chat_calls.append(kwargs)

                async def stream():
                    for chunk in chunks:
                        yield chunk

                return stream()

        class FakeResponses:
            async def create(self, **kwargs):
                response_calls.append(kwargs)
                if not kwargs.get("stream"):
                    return FakeResponse()
                if response_stream_error is not None:
                    raise response_stream_error

                async def stream():
                    for event in response_events:
                        yield event

                return stream()

        return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()), responses=FakeResponses())


class FakeCompletion:
    choices = [SimpleNamespace(message=SimpleNamespace(content="ok"))]
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)

    def model_dump(self, **_kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeResponse:
    output_text = "file summary"
    usage = SimpleNamespace(input_tokens=10, output_tokens=2, total_tokens=12)

    def model_dump(self, **_kwargs):
        return {"output": [{"content": [{"type": "output_text", "text": "file summary"}]}]}


class FakeCallAdapter(OpenAIModelAdapter):
    def __init__(self):
        super().__init__(api_key="test-key", base_url="https://example.test/v1", default_model="test-model")
        self.calls = []
        self.response_calls = []

    def _build_client(self):
        calls = self.calls
        response_calls = self.response_calls

        class FakeCompletions:
            async def create(self, **kwargs):
                calls.append(kwargs)
                return FakeCompletion()

        class FakeResponses:
            async def create(self, **kwargs):
                response_calls.append(kwargs)
                return FakeResponse()

        return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()), responses=FakeResponses())


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


def fake_response_stream_event(event_type, **kwargs):
    return SimpleNamespace(type=event_type, **kwargs)


class ModelAdapterLogTests(unittest.TestCase):
    def test_model_message_accepts_text_image_and_file_content_parts(self):
        image_content = [
            {"type": "text", "text": "What is in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://example.test/image.jpg",
                    "detail": "auto",
                },
            },
        ]
        file_content = [
            {
                "type": "file",
                "file": {
                    "filename": "paper.pdf",
                    "file_data": "data:application/pdf;base64,JVBERi0x",
                },
            },
            {"type": "text", "text": "Summarize this file."},
        ]

        text_message = ModelMessage(role="user", content="plain text")
        image_message = ModelMessage(role="user", content=image_content)
        file_message = ModelMessage(role="user", content=file_content)

        self.assertEqual(text_message.content, "plain text")
        self.assertEqual(image_message.content, image_content)
        self.assertEqual(file_message.content, file_content)

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

    def test_trace_json_sink_preserves_content_parts(self):
        content_parts = [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": "https://example.test/image.jpg"}},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            sink = TraceJsonInvocationLogSink(Path(temp_dir))
            log = LLMInvocationLog(
                timestamp=datetime(2026, 4, 26, 12, 30, 1, 123456),
                trace_id="trace-parts",
                workflow="conversation",
                paper_id=None,
                session_id=None,
                agent_name="qa_agent",
                messages=[ModelMessage(role="user", content=content_parts)],
                raw_response={"choices": []},
                pre_parse_text="ok",
                latency_ms=42,
            )

            sink.write(log)

            files = list(Path(temp_dir).glob("**/*.json"))
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["messages"][0]["content"], content_parts)

    def test_default_log_sink_uses_backend_storage(self):
        sink = default_log_sink()

        self.assertIsInstance(sink, TraceJsonInvocationLogSink)
        self.assertEqual(sink._directory_path.name, "llm_invocations")
        self.assertEqual(sink._directory_path.parent.name, "storage")
        self.assertEqual(sink._directory_path.parent.parent.name, "backend")


class ModelAdapterCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_passes_content_parts_to_openai_payload(self):
        adapter = FakeCallAdapter()
        content_parts = [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": "https://example.test/image.jpg"}},
        ]

        result = await adapter.call(
            trace_id="trace-payload",
            workflow="conversation",
            paper_id=None,
            session_id=None,
            agent_name="qa_agent",
            messages=[ModelMessage(role="user", content=content_parts)],
        )

        self.assertEqual(result.text, "ok")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0]["messages"][0]["content"], content_parts)
        self.assertEqual(adapter.response_calls, [])

    async def test_call_routes_input_file_content_parts_to_responses_api(self):
        adapter = FakeCallAdapter()
        content_parts = [
            {"type": "text", "text": "What is in this file?"},
            {
                "type": "input_file",
                "file_url": "https://example.test/paper.pdf",
            },
        ]

        result = await adapter.call(
            trace_id="trace-responses",
            workflow="conversation",
            paper_id=None,
            session_id=None,
            agent_name="qa_agent",
            messages=[
                ModelMessage(role="system", content="You are concise."),
                ModelMessage(role="user", content=content_parts),
            ],
            params=ModelCallParams(temperature=0.0, timeout_seconds=30.0, max_tokens=64),
        )

        self.assertEqual(result.text, "file summary")
        self.assertEqual(result.token_usage.prompt_tokens, 10)
        self.assertEqual(result.token_usage.completion_tokens, 2)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(len(adapter.response_calls), 1)
        response_call = adapter.response_calls[0]
        self.assertEqual(response_call["max_output_tokens"], 64)
        self.assertEqual(response_call["input"][0]["role"], "system")
        self.assertEqual(response_call["input"][1]["content"][0], {"type": "input_text", "text": "What is in this file?"})
        self.assertEqual(
            response_call["input"][1]["content"][1],
            {
                "type": "input_file",
                "file_url": "https://example.test/paper.pdf",
            },
        )


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

    async def test_stream_routes_input_file_content_parts_to_responses_api(self):
        log_sink = CaptureLogSink()
        response = SimpleNamespace(
            id="resp-test",
            model="test-model",
            usage=SimpleNamespace(input_tokens=10, output_tokens=2, total_tokens=12),
        )
        adapter = FakeStreamingAdapter(
            response_events=[
                fake_response_stream_event("response.output_text.delta", delta="file "),
                fake_response_stream_event("response.output_text.delta", delta="summary"),
                fake_response_stream_event("response.completed", response=response),
            ],
            log_sink=log_sink,
        )

        tokens = []
        async for token in adapter.stream(
            trace_id="trace-response-stream",
            workflow="conversation",
            paper_id="paper-1",
            session_id="session-1",
            agent_name="qa_agent_stream",
            messages=[
                ModelMessage(role="system", content="You are concise."),
                ModelMessage(
                    role="user",
                    content=[
                        {"type": "text", "text": "What is in this file?"},
                        {"type": "input_file", "file_url": "https://example.test/paper.pdf"},
                    ],
                ),
            ],
            params=ModelCallParams(max_tokens=64),
        ):
            tokens.append(token)

        self.assertEqual(tokens, ["file ", "summary"])
        self.assertEqual(adapter.chat_calls, [])
        self.assertEqual(len(adapter.response_calls), 1)
        response_call = adapter.response_calls[0]
        self.assertTrue(response_call["stream"])
        self.assertEqual(response_call["max_output_tokens"], 64)
        self.assertEqual(response_call["input"][1]["content"][0], {"type": "input_text", "text": "What is in this file?"})
        self.assertEqual(len(log_sink.logs), 1)
        log = log_sink.logs[0]
        self.assertEqual(log.pre_parse_text, "file summary")
        self.assertEqual(log.raw_response["completion_id"], "resp-test")
        self.assertEqual(log.raw_response["finish_reason"], "completed")
        self.assertEqual(log.token_usage.prompt_tokens, 10)
        self.assertEqual(log.token_usage.completion_tokens, 2)

    async def test_stream_falls_back_to_non_streaming_responses_before_any_delta(self):
        log_sink = CaptureLogSink()
        adapter = FakeStreamingAdapter(
            response_stream_error=RuntimeError("stream failed before first delta"),
            log_sink=log_sink,
        )

        tokens = []
        async for token in adapter.stream(
            trace_id="trace-response-stream-fallback",
            workflow="conversation",
            paper_id="paper-1",
            session_id="session-1",
            agent_name="qa_agent_stream",
            messages=[
                ModelMessage(role="system", content="You are concise."),
                ModelMessage(
                    role="user",
                    content=[
                        {"type": "text", "text": "What is in this file?"},
                        {"type": "input_file", "file_url": "https://example.test/paper.pdf"},
                    ],
                ),
            ],
            params=ModelCallParams(max_tokens=64),
        ):
            tokens.append(token)

        self.assertEqual(tokens, ["file summary"])
        self.assertEqual(len(adapter.response_calls), 2)
        self.assertTrue(adapter.response_calls[0]["stream"])
        self.assertNotIn("stream", adapter.response_calls[1])
        self.assertEqual(len(log_sink.logs), 1)
        log = log_sink.logs[0]
        self.assertEqual(log.pre_parse_text, "file summary")
        self.assertEqual(log.raw_response["fallback"], "responses_non_stream")
        self.assertEqual(log.raw_response["stream_error"], "stream failed before first delta")
        self.assertEqual(log.raw_response["text"], "file summary")
        self.assertEqual(log.token_usage.prompt_tokens, 10)


if __name__ == "__main__":
    unittest.main()
