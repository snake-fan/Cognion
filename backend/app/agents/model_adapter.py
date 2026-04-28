from __future__ import annotations

import asyncio
import os
import time
import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx
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
        trust_env: bool | None = None,
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
        self._trust_env = trust_env if trust_env is not None else os.getenv("OPENAI_TRUST_ENV", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _build_client(self) -> AsyncOpenAI:
        if not self._api_key:
            raise ModelAdapterError("OPENAI_API_KEY is not configured")
        return AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=0,
            http_client=httpx.AsyncClient(trust_env=self._trust_env),
        )

    def _normalize_usage(self, usage: Any) -> TokenUsage | None:
        if usage is None:
            return None
        return TokenUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def _uses_responses_api(self, messages: list[ModelMessage]) -> bool:
        for message in messages:
            if not isinstance(message.content, list):
                continue
            for part in message.content:
                part_type = part.get("type")
                if isinstance(part_type, str) and part_type.startswith("input_"):
                    return True
                if part.get("file_url"):
                    return True
        return False

    def _responses_content_part(self, part: dict[str, Any]) -> dict[str, Any]:
        part_type = part.get("type")
        if part_type == "text":
            return {"type": "input_text", "text": str(part.get("text") or "")}
        if part_type == "image_url":
            image_url = part.get("image_url")
            if isinstance(image_url, dict):
                converted = {"type": "input_image", "image_url": str(image_url.get("url") or "")}
                if image_url.get("detail"):
                    converted["detail"] = image_url["detail"]
                return converted
            return {"type": "input_image", "image_url": str(image_url or "")}
        if part_type == "file":
            file_payload = part.get("file")
            converted = dict(file_payload) if isinstance(file_payload, dict) else {}
            converted["type"] = "input_file"
            return converted
        return dict(part)

    def _build_responses_input(self, messages: list[ModelMessage]) -> list[dict[str, Any]]:
        input_messages: list[dict[str, Any]] = []
        for message in messages:
            role = message.role if message.role in {"system", "user", "assistant"} else "user"
            content: str | list[dict[str, Any]]
            if isinstance(message.content, list):
                content = [self._responses_content_part(part) for part in message.content]
            else:
                content = message.content
            input_messages.append({"role": role, "content": content})
        return input_messages

    def _response_output_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str):
            return output_text

        texts: list[str] = []
        for output in getattr(response, "output", []) or []:
            for content in getattr(output, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    text = getattr(content, "text", None)
                    if isinstance(text, str):
                        texts.append(text)
        return "".join(texts)

    def _responses_create_kwargs(
        self,
        *,
        model: str,
        messages: list[ModelMessage],
        temperature: float,
        timeout_seconds: float,
        params: ModelCallParams,
    ) -> dict[str, Any]:
        response_kwargs: dict[str, Any] = {
            "model": model,
            "input": self._build_responses_input(messages),
            "temperature": temperature,
            "timeout": timeout_seconds,
        }
        if params.max_tokens is not None:
            response_kwargs["max_output_tokens"] = params.max_tokens
        if params.response_format is not None:
            response_kwargs["text"] = {"format": params.response_format}
        return response_kwargs

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
        payload_messages = [message.model_dump(mode="json") for message in messages]
        use_responses_api = self._uses_responses_api(messages)

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            started = time.perf_counter()
            raw_response: dict[str, Any] | None = None
            response_text = ""
            token_usage: TokenUsage | None = None
            try:
                if use_responses_api:
                    response_kwargs = self._responses_create_kwargs(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        timeout_seconds=timeout_seconds,
                        params=effective_params,
                    )
                    completion = await client.responses.create(**response_kwargs)
                    response_text = self._response_output_text(completion)
                else:
                    completion = await client.chat.completions.create(
                        model=model,
                        messages=payload_messages,
                        temperature=temperature,
                        response_format=effective_params.response_format,
                        timeout=timeout_seconds,
                        max_tokens=effective_params.max_tokens,
                    )
                    if completion.choices and completion.choices[0].message:
                        response_text = completion.choices[0].message.content or ""
                raw_response = completion.model_dump(mode="json")
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
        payload_messages = [message.model_dump(mode="json") for message in messages]
        use_responses_api = self._uses_responses_api(messages)

        started = time.perf_counter()
        chunk_count = 0
        completion_id: str | None = None
        response_model: str | None = None
        finish_reason: str | None = None
        collected_text: list[str] = []
        token_usage: TokenUsage | None = None

        try:
            if use_responses_api:
                response_kwargs = self._responses_create_kwargs(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
                    params=effective_params,
                )
                stream = await client.responses.create(**response_kwargs, stream=True)
                async for event in stream:
                    chunk_count += 1
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        text = getattr(event, "delta", None)
                        if isinstance(text, str) and text:
                            collected_text.append(text)
                            yield text
                        continue

                    response = getattr(event, "response", None)
                    if response is None:
                        continue
                    completion_id = getattr(response, "id", completion_id)
                    response_model = getattr(response, "model", response_model)
                    if event_type == "response.completed":
                        finish_reason = "completed"
                    elif event_type == "response.incomplete":
                        finish_reason = "incomplete"
                    elif event_type == "response.failed":
                        finish_reason = "failed"
                    token_usage = self._normalize_usage(getattr(response, "usage", None)) or token_usage
            else:
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
                token_usage=token_usage,
                latency_ms=latency_ms,
                error=None,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            response_text = "".join(collected_text)
            if use_responses_api and not collected_text:
                stream_error = str(exc)
                try:
                    response_kwargs = self._responses_create_kwargs(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        timeout_seconds=timeout_seconds,
                        params=effective_params,
                    )
                    completion = await client.responses.create(**response_kwargs)
                    raw_response = completion.model_dump(mode="json")
                    response_text = self._response_output_text(completion)
                    token_usage = self._normalize_usage(completion.usage)
                    completion_id = raw_response.get("id") if isinstance(raw_response, dict) else completion_id
                    response_model = raw_response.get("model") if isinstance(raw_response, dict) else response_model
                    finish_reason = raw_response.get("status") if isinstance(raw_response, dict) else "completed"
                    if response_text:
                        collected_text.append(response_text)
                        yield response_text

                    latency_ms = int((time.perf_counter() - started) * 1000)
                    self._log_invocation(
                        trace_id=trace_id,
                        workflow=workflow,
                        paper_id=paper_id,
                        session_id=session_id,
                        agent_name=agent_name,
                        messages=messages,
                        raw_response={
                            "stream": True,
                            "fallback": "responses_non_stream",
                            "stream_error": stream_error,
                            "completion_id": completion_id,
                            "model": response_model,
                            "chunk_count": 1 if response_text else 0,
                            "finish_reason": finish_reason,
                            "text": response_text,
                            "response": raw_response,
                        },
                        pre_parse_text=response_text,
                        token_usage=token_usage,
                        latency_ms=latency_ms,
                        error=None,
                    )
                    return
                except Exception as fallback_exc:
                    exc = fallback_exc
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
                token_usage=token_usage,
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
