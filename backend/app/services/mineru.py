import asyncio
import importlib
import logging
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx

from .config import (
    ALIYUN_OSS_ACCESS_KEY_ID,
    ALIYUN_OSS_ACCESS_KEY_SECRET,
    ALIYUN_OSS_BUCKET,
    ALIYUN_OSS_ENABLED,
    ALIYUN_OSS_ENDPOINT,
    ALIYUN_OSS_KEY_PREFIX,
    ALIYUN_OSS_PUBLIC_BASE_URL,
    ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS,
    MINERU_API_KEY,
    MINERU_API_URL,
    MINERU_ENABLED,
    MINERU_MAX_CHARS,
    MINERU_MODEL,
    MINERU_POLL_INTERVAL_SECONDS,
    MINERU_TIMEOUT_SECONDS,
)
from .pdf_storage import extract_pdf_text

logger = logging.getLogger(__name__)


def _extract_text_from_payload(payload: object) -> str:
    if isinstance(payload, str):
        return payload

    preferred_keys = [
        "markdown",
        "md",
        "text",
        "content",
        "full_text",
        "parsed_text",
        "result",
        "data",
        "output",
    ]

    if isinstance(payload, dict):
        for key in preferred_keys:
            if key in payload:
                extracted = _extract_text_from_payload(payload[key])
                if extracted:
                    return extracted

        for value in payload.values():
            extracted = _extract_text_from_payload(value)
            if extracted:
                return extracted
        return ""

    if isinstance(payload, list):
        parts: list[str] = []
        for item in payload:
            extracted = _extract_text_from_payload(item)
            if extracted:
                parts.append(extracted)
        return "\n\n".join(parts)

    return ""


def _extract_markdown_from_zip_bytes(zip_bytes: bytes) -> str:
    if not zip_bytes:
        return ""

    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
            file_names = [name for name in archive.namelist() if not name.endswith("/")]
            if not file_names:
                return ""

            preferred_name = next(
                (name for name in file_names if Path(name).name.lower() == "full.md"),
                None,
            )
            markdown_name = preferred_name or next(
                (name for name in file_names if name.lower().endswith(".md")),
                None,
            )

            if not markdown_name:
                return ""

            return archive.read(markdown_name).decode("utf-8", errors="ignore").strip()
    except (zipfile.BadZipFile, OSError, RuntimeError, KeyError):
        return ""


async def _download_markdown_from_url(client: httpx.AsyncClient, markdown_url: str) -> str:
    if not markdown_url:
        return ""

    try:
        response = await client.get(markdown_url)
    except httpx.HTTPError as error:
        logger.error("MinerU markdown download failed: url=%s error=%s", markdown_url, error)
        return ""

    if response.status_code >= 400:
        logger.error(
            "MinerU markdown download failed: status=%s url=%s body=%s",
            response.status_code,
            markdown_url,
            response.text[:300],
        )
        return ""

    return response.text.strip()


async def _download_markdown_from_zip_url(client: httpx.AsyncClient, zip_url: str) -> str:
    if not zip_url:
        return ""

    try:
        response = await client.get(zip_url)
    except httpx.HTTPError as error:
        logger.error("MinerU zip download failed: url=%s error=%s", zip_url, error)
        return ""

    if response.status_code >= 400:
        logger.error(
            "MinerU zip download failed: status=%s url=%s body=%s",
            response.status_code,
            zip_url,
            response.text[:300],
        )
        return ""

    markdown_text = _extract_markdown_from_zip_bytes(response.content)
    if not markdown_text:
        logger.error("MinerU zip parse failed: no markdown found in zip_url=%s", zip_url)
    return markdown_text


def _markdown_cache_path(local_pdf_path: str | None) -> Path | None:
    if not local_pdf_path:
        return None
    pdf_path = Path(local_pdf_path)
    if not pdf_path.exists():
        return None
    return pdf_path.with_suffix(".md")


def _read_markdown_cache(local_pdf_path: str | None, max_chars: int) -> str:
    cache_path = _markdown_cache_path(local_pdf_path)
    if not cache_path or not cache_path.exists():
        return ""
    try:
        content = cache_path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""
    return content[:max_chars] if content else ""


def _write_markdown_cache(local_pdf_path: str | None, markdown_text: str) -> None:
    if not markdown_text.strip():
        return
    cache_path = _markdown_cache_path(local_pdf_path)
    if not cache_path:
        return
    try:
        cache_path.write_text(markdown_text, encoding="utf-8")
    except OSError:
        return


def upload_pdf_to_aliyun_oss(pdf_bytes: bytes | None, pdf_filename: str | None) -> str:
    if not pdf_bytes:
        logger.warning("OSS upload skipped: empty pdf bytes")
        return ""

    required = [
        ALIYUN_OSS_ENDPOINT,
        ALIYUN_OSS_BUCKET,
        ALIYUN_OSS_ACCESS_KEY_ID,
        ALIYUN_OSS_ACCESS_KEY_SECRET,
    ]
    if not all(required):
        logger.error(
            "OSS upload skipped: missing config endpoint=%s bucket=%s ak_set=%s sk_set=%s",
            bool(ALIYUN_OSS_ENDPOINT),
            bool(ALIYUN_OSS_BUCKET),
            bool(ALIYUN_OSS_ACCESS_KEY_ID),
            bool(ALIYUN_OSS_ACCESS_KEY_SECRET),
        )
        return ""

    try:
        oss2 = importlib.import_module("oss2")
    except ModuleNotFoundError as error:
        logger.error("OSS upload skipped: oss2 not installed (%s)", error)
        return ""

    auth = oss2.Auth(ALIYUN_OSS_ACCESS_KEY_ID, ALIYUN_OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, ALIYUN_OSS_ENDPOINT, ALIYUN_OSS_BUCKET)

    extension = Path(pdf_filename or "paper.pdf").suffix.lower() or ".pdf"
    key_prefix = ALIYUN_OSS_KEY_PREFIX.strip("/")
    object_key = f"{key_prefix}/{uuid4().hex}{extension}" if key_prefix else f"{uuid4().hex}{extension}"

    try:
        bucket.put_object(object_key, pdf_bytes, headers={"Content-Type": "application/pdf"})
    except Exception as error:
        logger.exception(
            "OSS upload failed: endpoint=%s bucket=%s object_key=%s error=%s",
            ALIYUN_OSS_ENDPOINT,
            ALIYUN_OSS_BUCKET,
            object_key,
            error,
        )
        return ""

    logger.info(
        "OSS upload succeeded: endpoint=%s bucket=%s object_key=%s",
        ALIYUN_OSS_ENDPOINT,
        ALIYUN_OSS_BUCKET,
        object_key,
    )

    if ALIYUN_OSS_PUBLIC_BASE_URL:
        base_url = ALIYUN_OSS_PUBLIC_BASE_URL.rstrip("/")
        return f"{base_url}/{quote(object_key)}"

    try:
        return bucket.sign_url("GET", object_key, ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS)
    except Exception as error:
        logger.exception(
            "OSS sign_url failed: bucket=%s object_key=%s expires=%s error=%s",
            ALIYUN_OSS_BUCKET,
            object_key,
            ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS,
            error,
        )
        return ""


async def call_mineru_api_with_pdf_url(pdf_url: str) -> str:
    if not MINERU_API_URL or not pdf_url:
        logger.warning(
            "MinerU call skipped: api_url_set=%s pdf_url_set=%s",
            bool(MINERU_API_URL),
            bool(pdf_url),
        )
        return ""

    headers = {"Content-Type": "application/json"}
    if MINERU_API_KEY:
        headers["Authorization"] = f"Bearer {MINERU_API_KEY}"

    submit_body = {
        "url": pdf_url,
        "model_version": MINERU_MODEL,
    }

    poll_interval = max(0.5, MINERU_POLL_INTERVAL_SECONDS)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + MINERU_TIMEOUT_SECONDS

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MINERU_API_URL, json=submit_body, headers=headers)

            if response.status_code >= 400:
                logger.error(
                    "MinerU submit failed: status=%s url=%s body=%s",
                    response.status_code,
                    MINERU_API_URL,
                    response.text[:500],
                )
                return ""

            try:
                submit_payload = response.json()
            except ValueError as error:
                logger.error("MinerU submit JSON parse failed: error=%s body=%s", error, response.text[:500])
                return ""

            if not isinstance(submit_payload, dict):
                logger.error("MinerU submit response invalid: payload_type=%s", type(submit_payload).__name__)
                return ""

            if int(submit_payload.get("code", -1)) != 0:
                logger.error(
                    "MinerU submit business failed: code=%s msg=%s trace_id=%s",
                    submit_payload.get("code"),
                    submit_payload.get("msg"),
                    submit_payload.get("trace_id"),
                )
                return ""

            submit_data = submit_payload.get("data") if isinstance(submit_payload.get("data"), dict) else {}
            task_id = str(submit_data.get("task_id") or "").strip()
            if not task_id:
                logger.error("MinerU submit missing task_id: data=%s", submit_data)
                return ""

            query_url = f"{MINERU_API_URL.rstrip('/')}/{task_id}"

            while loop.time() < deadline:
                query_response = await client.get(query_url, headers=headers)
                if query_response.status_code >= 400:
                    logger.error(
                        "MinerU query failed: status=%s url=%s body=%s",
                        query_response.status_code,
                        query_url,
                        query_response.text[:500],
                    )
                    return ""

                try:
                    query_payload = query_response.json()
                except ValueError as error:
                    logger.error("MinerU query JSON parse failed: error=%s body=%s", error, query_response.text[:500])
                    return ""

                if not isinstance(query_payload, dict):
                    logger.error("MinerU query response invalid: payload_type=%s", type(query_payload).__name__)
                    return ""

                if int(query_payload.get("code", -1)) != 0:
                    logger.error(
                        "MinerU query business failed: code=%s msg=%s trace_id=%s",
                        query_payload.get("code"),
                        query_payload.get("msg"),
                        query_payload.get("trace_id"),
                    )
                    return ""

                query_data = query_payload.get("data") if isinstance(query_payload.get("data"), dict) else {}
                state = str(query_data.get("state") or "").strip().lower()

                if state == "done":
                    full_zip_url = str(query_data.get("full_zip_url") or "").strip()
                    markdown_text = await _download_markdown_from_zip_url(client, full_zip_url)
                    if markdown_text:
                        return markdown_text

                    markdown_url = str(query_data.get("markdown_url") or "").strip()
                    markdown_text = await _download_markdown_from_url(client, markdown_url)
                    if markdown_text:
                        return markdown_text

                    fallback_text = _extract_text_from_payload(query_data)
                    if fallback_text:
                        return fallback_text

                    logger.error("MinerU done state but no markdown content: task_id=%s data=%s", task_id, query_data)
                    return ""

                if state == "failed":
                    logger.error(
                        "MinerU parse failed: task_id=%s err_msg=%s err_code=%s",
                        task_id,
                        query_data.get("err_msg"),
                        query_data.get("err_code"),
                    )
                    return ""

                if state in {"pending", "running", "converting", "waiting-file", "uploading"}:
                    await asyncio.sleep(poll_interval)
                    continue

                logger.warning("MinerU query unknown state: task_id=%s state=%s", task_id, state)
                await asyncio.sleep(poll_interval)

            logger.error(
                "MinerU polling timeout: task not completed within %ss, submit_url=%s",
                MINERU_TIMEOUT_SECONDS,
                MINERU_API_URL,
            )
            return ""
    except httpx.TimeoutException as error:
        logger.error("MinerU request timeout: base_url=%s error=%s", MINERU_API_URL, error)
        return ""
    except httpx.HTTPError as error:
        logger.error("MinerU HTTP transport error: base_url=%s error=%s", MINERU_API_URL, error)
        return ""


async def extract_pdf_text_with_mineru_api(
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    max_chars: int = MINERU_MAX_CHARS,
) -> str:
    logger.info("Start MinerU extraction for file=%s", pdf_filename)
    if not pdf_bytes:
        logger.warning("MinerU extraction skipped: empty pdf bytes")
        return ""

    if not MINERU_API_URL or not ALIYUN_OSS_ENABLED:
        logger.warning(
            "MinerU extraction skipped: api_url_set=%s oss_enabled=%s",
            bool(MINERU_API_URL),
            ALIYUN_OSS_ENABLED,
        )
        return ""

    public_pdf_url = upload_pdf_to_aliyun_oss(pdf_bytes, pdf_filename)
    if not public_pdf_url:
        logger.error("MinerU extraction stopped: failed to get OSS url for file=%s", pdf_filename)
        return ""

    parsed_text = await call_mineru_api_with_pdf_url(public_pdf_url)
    if parsed_text:
        logger.info("MinerU extraction succeeded: file=%s chars=%s", pdf_filename, len(parsed_text))
    else:
        logger.warning("MinerU extraction returned empty text: file=%s", pdf_filename)
    return parsed_text[:max_chars] if parsed_text else ""


async def extract_pdf_context_for_qa(
    pdf_bytes: bytes | None,
    pdf_filename: str | None,
    local_pdf_path: str | None = None,
    max_chars: int = MINERU_MAX_CHARS,
) -> str:
    cached_markdown = _read_markdown_cache(local_pdf_path, max_chars=max_chars)
    if cached_markdown:
        return cached_markdown

    source_bytes = pdf_bytes
    if source_bytes is None and local_pdf_path:
        try:
            source_bytes = Path(local_pdf_path).read_bytes()
        except OSError:
            source_bytes = None

    if not source_bytes:
        return ""

    parsed_text = ""
    if MINERU_ENABLED:
        parsed_text = await extract_pdf_text_with_mineru_api(
            source_bytes,
            pdf_filename,
            max_chars=max_chars,
        )
        if parsed_text:
            _write_markdown_cache(local_pdf_path, parsed_text)
            return parsed_text

    return extract_pdf_text(source_bytes, max_chars=min(max_chars, 12000))
