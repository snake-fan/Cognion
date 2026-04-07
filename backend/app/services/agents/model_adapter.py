from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from ..config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_URL
from .schemas import LLMInvocationLog, ModelCallParams, ModelInvocationResult, ModelMessage, TokenUsage


class InvocationLogSink(ABC):
    @abstractmethod
    def write(self, log: LLMInvocationLog) -> None:
        pass


class JsonlInvocationLogSink(InvocationLogSink):
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, log: LLMInvocationLog) -> None:
        with self._file_path.open("a", encoding="utf-8") as file:
            file.write(log.model_dump_json(ensure_ascii=False) + "\n")


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
        api_key: str | None = OPENAI_API_KEY,
        base_url: str | None = OPENAI_URL,
        default_model: str = OPENAI_MODEL,
        default_timeout_seconds: float = 45.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        log_sink: InvocationLogSink | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._default_model = default_model
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
        session_id: str | None,
        agent_name: str,
        messages: list[ModelMessage],
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
        session_id: str | None,
        agent_name: str,
        messages: list[ModelMessage],
        params: ModelCallParams | None = None,
    ) -> AsyncGenerator[str, None]:
        effective_params = params or ModelCallParams()
        model = effective_params.model or self._default_model
        temperature = effective_params.temperature if effective_params.temperature is not None else 0.2
        timeout_seconds = effective_params.timeout_seconds or self._default_timeout_seconds

        client = self._build_client()
        payload_messages = [message.model_dump() for message in messages]

        started = time.perf_counter()
        raw_chunks: list[dict[str, Any]] = []
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
                raw_chunks.append(chunk.model_dump(mode="json"))
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = delta.content if delta else None
                if isinstance(text, str) and text:
                    collected_text.append(text)
                    yield text

            latency_ms = int((time.perf_counter() - started) * 1000)
            self._log_invocation(
                trace_id=trace_id,
                session_id=session_id,
                agent_name=agent_name,
                messages=messages,
                raw_response={"chunks": raw_chunks},
                pre_parse_text="".join(collected_text),
                token_usage=None,
                latency_ms=latency_ms,
                error=None,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._log_invocation(
                trace_id=trace_id,
                session_id=session_id,
                agent_name=agent_name,
                messages=messages,
                raw_response={"chunks": raw_chunks},
                pre_parse_text="".join(collected_text),
                token_usage=None,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise ModelAdapterError(str(exc)) from exc


def default_log_sink() -> InvocationLogSink:
    return JsonlInvocationLogSink(Path(__file__).resolve().parents[3] / "storage" / "llm_invocations" / "invocations.jsonl")
