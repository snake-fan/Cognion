from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.app.agents.implementations.agents.qa_agent import QAAgent
from backend.app.agents.implementations.templates.qa import build_qa_user_template
from backend.app.agents.state import ConversationAgentState
from backend.app.services.mineru import extract_pdf_context_for_qa


class QAPdfTemplateTests(unittest.TestCase):
    def test_template_uses_input_file_when_pdf_url_is_available(self):
        content = build_qa_user_template(
            question="What is the method?",
            quote="Important quote",
            pdf_filename="paper.pdf",
            pdf_context="",
            pdf_file_url="https://example.test/paper.pdf",
        )

        self.assertIsInstance(content, list)
        self.assertEqual(content[1], {"type": "input_file", "file_url": "https://example.test/paper.pdf"})
        self.assertNotIn("无可用内容", content[0]["text"])
        self.assertIn("随消息附上的 PDF 文件", content[0]["text"])

    def test_qa_agent_builds_file_content_parts_from_state(self):
        state = ConversationAgentState(
            user_input="Explain this",
            pdf_file_url="https://example.test/paper.pdf",
            retrieval_context={"quote": "quoted text", "pdf_filename": "paper.pdf"},
        )
        messages = QAAgent(adapter=object()).build_messages(state)

        self.assertEqual(messages[0].role, "system")
        self.assertIsInstance(messages[1].content, list)
        self.assertEqual(messages[1].content[1]["type"], "input_file")
        self.assertEqual(messages[1].content[1]["file_url"], "https://example.test/paper.pdf")


class QAPdfContextServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_mineru_uploads_pdf_url_without_calling_mineru(self):
        with (
            patch("backend.app.services.mineru.MINERU_ENABLED", False),
            patch("backend.app.services.mineru.ALIYUN_OSS_ENABLED", True),
            patch("backend.app.services.mineru.upload_pdf_to_aliyun_oss", return_value="https://example.test/paper.pdf") as upload,
            patch("backend.app.services.mineru.call_mineru_api_with_pdf_url", new_callable=AsyncMock) as call_mineru,
            patch("backend.app.services.mineru.extract_pdf_text", return_value="local text") as extract_text,
        ):
            context = await extract_pdf_context_for_qa(b"%PDF-1.4", "paper.pdf")

        self.assertEqual(context.file_url, "https://example.test/paper.pdf")
        self.assertEqual(context.text, "")
        self.assertEqual(context.source, "file_url")
        upload.assert_called_once_with(b"%PDF-1.4", "paper.pdf")
        call_mineru.assert_not_called()
        extract_text.assert_not_called()

    async def test_disabled_mineru_falls_back_to_local_text_when_upload_fails(self):
        with (
            patch("backend.app.services.mineru.MINERU_ENABLED", False),
            patch("backend.app.services.mineru.ALIYUN_OSS_ENABLED", True),
            patch("backend.app.services.mineru.upload_pdf_to_aliyun_oss", return_value=""),
            patch("backend.app.services.mineru.extract_pdf_text", return_value="local text") as extract_text,
        ):
            context = await extract_pdf_context_for_qa(b"%PDF-1.4", "paper.pdf")

        self.assertEqual(context.file_url, "")
        self.assertEqual(context.text, "local text")
        self.assertEqual(context.source, "local_text")
        extract_text.assert_called_once_with(b"%PDF-1.4", max_chars=12000)

    async def test_enabled_mineru_preserves_cached_markdown_behavior(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "paper.pdf"
            md_path = Path(temp_dir) / "paper.md"
            pdf_path.write_bytes(b"%PDF-1.4")
            md_path.write_text("cached markdown", encoding="utf-8")

            with (
                patch("backend.app.services.mineru.MINERU_ENABLED", True),
                patch("backend.app.services.mineru.extract_pdf_text_with_mineru_api", new_callable=AsyncMock) as extract_mineru,
            ):
                context = await extract_pdf_context_for_qa(None, "paper.pdf", local_pdf_path=str(pdf_path))

        self.assertEqual(context.text, "cached markdown")
        self.assertEqual(context.file_url, "")
        self.assertEqual(context.source, "cache")
        extract_mineru.assert_not_called()

    async def test_enabled_mineru_writes_markdown_result_to_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "paper.pdf"
            md_path = Path(temp_dir) / "paper.md"
            pdf_path.write_bytes(b"%PDF-1.4")

            with (
                patch("backend.app.services.mineru.MINERU_ENABLED", True),
                patch("backend.app.services.mineru.extract_pdf_text_with_mineru_api", new_callable=AsyncMock) as extract_mineru,
            ):
                extract_mineru.return_value = "mineru markdown"
                context = await extract_pdf_context_for_qa(None, "paper.pdf", local_pdf_path=str(pdf_path))

            cached_text = md_path.read_text(encoding="utf-8")

        self.assertEqual(context.text, "mineru markdown")
        self.assertEqual(context.source, "mineru")
        self.assertEqual(cached_text, "mineru markdown")


if __name__ == "__main__":
    unittest.main()
