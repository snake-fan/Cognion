from __future__ import annotations

import asyncio
import time
import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from .schemas import LLMInvocationLog, ModelCallParams, ModelInvocationResult, ModelMessage, TokenUsage


class InvocationLogSink(ABC):
    @abstractmethod
    def write(self, log: LLMInvocationLog) -> None:
        pass


class TraceJsonInvocationLogSink(InvocationLogSink):
    def __init__(self, directory_path: Path) -> None:
        self._directory_path = directory_path
        self._directory_path.mkdir(parents=True, exist_ok=True)

    def _safe_segment(self, value: str | None, fallback: str) -> str:
        text = str(value or fallback).strip() or fallback
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in text)

    def write(self, log: LLMInvocationLog) -> None:
        timestamp = log.timestamp.strftime("%Y%m%dT%H%M%S%f")
        trace_id = self._safe_segment(log.trace_id, "trace-unknown")
        workflow = self._safe_segment(log.workflow, "workflow-unknown")
        paper_dir = f"paper-{self._safe_segment(log.paper_id, 'unknown')}"
        session_dir = f"session-{self._safe_segment(log.session_id, 'unknown')}"
        directory_path = self._directory_path / workflow / paper_dir / session_dir
        directory_path.mkdir(parents=True, exist_ok=True)

        file_path = directory_path / f"{timestamp}-{trace_id}.json"
        with file_path.open("w", encoding="utf-8") as file:
            file.write(log.model_dump_json(ensure_ascii=False, indent=2))
            file.write("\n")


class CompositeLogSink(InvocationLogSink):
    def __init__(self, sinks: list[InvocationLogSink] | None = None) -> None:
        self._sinks = sinks or []

    def add_sink(self, sink: InvocationLogSink) -> None:
        self._sinks.append(sink)

    def write(self, log: LLMInvocationLog) -> None:
        for sink in self._sinks:
            sink.write(log)


class ModelAdapterError(RuntimeError):
    pass


class OpenAIModelAdapter:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        default_timeout_seconds: float = 45.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        log_sink: InvocationLogSink | None = None,
    ) -> None:
        if api_key is None or base_url is None or default_model is None:
            from ..services.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_URL
        else:
            OPENAI_API_KEY = api_key
            OPENAI_URL = base_url
            OPENAI_MODEL = default_model

        self._api_key = OPENAI_API_KEY if api_key is None else api_key
        self._base_url = OPENAI_URL if base_url is None else base_url
        self._default_model = OPENAI_MODEL if default_model is None else default_model
        self._default_timeout_seconds = default_timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._log_sink = log_sink

    def _build_client(self) -> AsyncOpenAI:
        if not self._api_key:
            raise ModelAdapterError("OPENAI_API_KEY is not configured")
        return AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)

    def _normalize_usage(self, usage: Any) -> TokenUsage | None:
        if usage is None:
            return None
        return TokenUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def _log_invocation(
        self,
        *,
        trace_id: str,
        workflow: str | None,
        paper_id: str | None,
        session_id: str | None,
        agent_name: str,
        messages: list[ModelMessage],
        raw_response: dict[str, Any] | None,
        pre_parse_text: str,
        token_usage: TokenUsage | None,
        latency_ms: int,
        error: str | None,
    ) -> None:
        if self._log_sink is None:
            return
        self._log_sink.write(
            LLMInvocationLog(
                trace_id=trace_id,
                workflow=workflow,
                paper_id=paper_id,
                session_id=session_id,
                agent_name=agent_name,
                messages=messages,
                raw_response=raw_response,
                pre_parse_text=pre_parse_text,
                token_usage=token_usage,
                latency_ms=latency_ms,
                error=error,
            )
        )

    async def call(
        self,
        *,
        trace_id: str,
        agent_name: str,
        messages: list[ModelMessage],
        workflow: str | None = None,
        paper_id: str | None = None,
        session_id: str | None = None,
        params: ModelCallParams | None = None,
    ) -> ModelInvocationResult:
        effective_params = params or ModelCallParams()
        model = effective_params.model or self._default_model
        temperature = effective_params.temperature if effective_params.temperature is not None else 0.2
        timeout_seconds = effective_params.timeout_seconds or self._default_timeout_seconds

        client = self._build_client()
        payload_messages = [message.model_dump() for message in messages]

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            started = time.perf_counter()
            raw_response: dict[str, Any] | None = None
            response_text = ""
            token_usage: TokenUsage | None = None
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=payload_messages,
                    temperature=temperature,
                    response_format=effective_params.response_format,
                    timeout=timeout_seconds,
                    max_tokens=effective_params.max_tokens,
                )
                raw_response = completion.model_dump(mode="json")
                if completion.choices and completion.choices[0].message:
                    response_text = completion.choices[0].message.content or ""
                token_usage = self._normalize_usage(completion.usage)

                latency_ms = int((time.perf_counter() - started) * 1000)
                self._log_invocation(
                    trace_id=trace_id,
                    workflow=workflow,
                    paper_id=paper_id,
                    session_id=session_id,
                    agent_name=agent_name,
                    messages=messages,
                    raw_response=raw_response,
                    pre_parse_text=response_text,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                    error=None,
                )
                return ModelInvocationResult(
                    text=response_text,
                    raw_response=raw_response,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                    model=model,
                )
            except (RateLimitError, APITimeoutError) as exc:
                last_error = exc
                latency_ms = int((time.perf_counter() - started) * 1000)
                self._log_invocation(
                    trace_id=trace_id,
                    workflow=workflow,
                    paper_id=paper_id,
                    session_id=session_id,
                    agent_name=agent_name,
                    messages=messages,
                    raw_response=raw_response,
                    pre_parse_text=response_text,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))
            except Exception as exc:
                last_error = exc
                latency_ms = int((time.perf_counter() - started) * 1000)
                self._log_invocation(
                    trace_id=trace_id,
                    workflow=workflow,
                    paper_id=paper_id,
                    session_id=session_id,
                    agent_name=agent_name,
                    messages=messages,
                    raw_response=raw_response,
                    pre_parse_text=response_text,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                    error=str(exc),
                )
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))

        raise ModelAdapterError(str(last_error or "Unknown model adapter error"))

    async def stream(
        self,
        *,
        trace_id: str,
        agent_name: str,
        messages: list[ModelMessage],
        workflow: str | None = None,
        paper_id: str | None = None,
        session_id: str | None = None,
        params: ModelCallParams | None = None,
    ) -> AsyncGenerator[str, None]:
        effective_params = params or ModelCallParams()
        model = effective_params.model or self._default_model
        temperature = effective_params.temperature if effective_params.temperature is not None else 0.2
        timeout_seconds = effective_params.timeout_seconds or self._default_timeout_seconds

        client = self._build_client()
        payload_messages = [message.model_dump() for message in messages]

        started = time.perf_counter()
        chunk_count = 0
        completion_id: str | None = None
        response_model: str | None = None
        finish_reason: str | None = None
        collected_text: list[str] = []

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=payload_messages,
                temperature=temperature,
                response_format=effective_params.response_format,
                timeout=timeout_seconds,
                max_tokens=effective_params.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                chunk_count += 1
                completion_id = getattr(chunk, "id", completion_id)
                response_model = getattr(chunk, "model", response_model)
                if not chunk.choices:
                    continue
                finish_reason = getattr(chunk.choices[0], "finish_reason", finish_reason)
                delta = chunk.choices[0].delta
                text = delta.content if delta else None
                if isinstance(text, str) and text:
                    collected_text.append(text)
                    yield text

            latency_ms = int((time.perf_counter() - started) * 1000)
            response_text = "".join(collected_text)
            self._log_invocation(
                trace_id=trace_id,
                workflow=workflow,
                paper_id=paper_id,
                session_id=session_id,
                agent_name=agent_name,
                messages=messages,
                raw_response={
                    "stream": True,
                    "completion_id": completion_id,
                    "model": response_model,
                    "chunk_count": chunk_count,
                    "finish_reason": finish_reason,
                    "text": response_text,
                },
                pre_parse_text=response_text,
                token_usage=None,
                latency_ms=latency_ms,
                error=None,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            response_text = "".join(collected_text)
            self._log_invocation(
                trace_id=trace_id,
                workflow=workflow,
                paper_id=paper_id,
                session_id=session_id,
                agent_name=agent_name,
                messages=messages,
                raw_response={
                    "stream": True,
                    "completion_id": completion_id,
                    "model": response_model,
                    "chunk_count": chunk_count,
                    "finish_reason": finish_reason,
                    "text": response_text,
                },
                pre_parse_text=response_text,
                token_usage=None,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise ModelAdapterError(str(exc)) from exc

    async def call_via_stream(
        self,
        *,
        trace_id: str,
        agent_name: str,
        messages: list[ModelMessage],
        workflow: str | None = None,
        paper_id: str | None = None,
        session_id: str | None = None,
        params: ModelCallParams | None = None,
    ) -> ModelInvocationResult:
        started = time.perf_counter()
        chunks: list[str] = []
        async for token in self.stream(
            trace_id=trace_id,
            workflow=workflow,
            paper_id=paper_id,
            session_id=session_id,
            agent_name=agent_name,
            messages=messages,
            params=params,
        ):
            chunks.append(token)

        response_text = "".join(chunks)
        return ModelInvocationResult(
            text=response_text,
            raw_response={"stream": True, "text": response_text},
            token_usage=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=(params.model if params else None) or self._default_model,
        )

    def call_blocking(
        self,
        *,
        trace_id: str,
        agent_name: str,
        messages: list[ModelMessage],
        workflow: str | None = None,
        paper_id: str | None = None,
        session_id: str | None = None,
        params: ModelCallParams | None = None,
    ) -> ModelInvocationResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.call(
                    trace_id=trace_id,
                    workflow=workflow,
                    paper_id=paper_id,
                    session_id=session_id,
                    agent_name=agent_name,
                    messages=messages,
                    params=params,
                )
            )

        result: ModelInvocationResult | None = None
        error: BaseException | None = None

        def _runner() -> None:
            nonlocal result, error
            try:
                result = asyncio.run(
                    self.call(
                        trace_id=trace_id,
                        workflow=workflow,
                        paper_id=paper_id,
                        session_id=session_id,
                        agent_name=agent_name,
                        messages=messages,
                        params=params,
                    )
                )
            except BaseException as exc:  # pragma: no cover - defensive bridge for async callers
                error = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        # 这里的 join 可以理解为阻塞线程，等待 thread 执行完返回结果
        thread.join()

        if error is not None:
            raise error
        if result is None:
            raise ModelAdapterError("Blocking model invocation returned no result")
        return result


def default_log_sink() -> InvocationLogSink:
    return TraceJsonInvocationLogSink(Path(__file__).resolve().parents[2] / "storage" / "llm_invocations")
