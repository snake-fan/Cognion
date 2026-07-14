import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, ChatMessage, ChatSession, Paper, User
from backend.app.routes.chat import ask_about_quote


class ChatSessionNameTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        TestingSession = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSession()
        self.db.add(User(id="test-user", email="test@example.com", password_hash="unused"))
        self.db.commit()
        self.db.info["user_id"] = "test-user"
        self.db.add(
            Paper(
                id="paper-1",
                title="Attention Is All You Need",
                authors="Author",
                research_topic="Transformer attention",
                journal="Journal",
                publication_date="2017",
                original_filename="paper.pdf",
                file_path="/tmp/paper.pdf",
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_session(self, name="Session 1") -> ChatSession:
        chat_session = ChatSession(id=1, paper_id="paper-1", name=name)
        self.db.add(chat_session)
        self.db.commit()
        return chat_session

    async def test_first_question_generates_session_name_in_parallel(self):
        self.add_session()
        name_started = asyncio.Event()
        answer_started = asyncio.Event()

        async def fake_generate_session_name(**_kwargs):
            name_started.set()
            await answer_started.wait()
            return "QK 与 V 的关系"

        async def fake_answer_with_context(**_kwargs):
            answer_started.set()
            await name_started.wait()
            return "answer"

        with (
            patch("backend.app.routes.chat.generate_session_name", side_effect=fake_generate_session_name) as name_mock,
            patch("backend.app.routes.chat.answer_with_context", side_effect=fake_answer_with_context),
        ):
            payload = await asyncio.wait_for(
                ask_about_quote(
                    question="QK 算出来的权重为什么要作用到 V 上？",
                    quote="",
                    paper_id="paper-1",
                    session_id=1,
                    stream=False,
                    pdf_file=None,
                    db=self.db,
                ),
                timeout=1,
            )

        self.assertEqual(payload["answer"], "answer")
        self.assertEqual(payload["session"]["name"], "QK 与 V 的关系")
        self.assertEqual(self.db.get(ChatSession, 1).name, "QK 与 V 的关系")
        name_mock.assert_called_once()

    async def test_custom_session_name_is_not_overwritten(self):
        self.add_session(name="我手动命名的会话")

        with (
            patch("backend.app.routes.chat.generate_session_name", new_callable=AsyncMock) as name_mock,
            patch("backend.app.routes.chat.answer_with_context", new_callable=AsyncMock, return_value="answer"),
        ):
            payload = await ask_about_quote(
                question="解释一下 attention。",
                quote="",
                paper_id="paper-1",
                session_id=1,
                stream=False,
                pdf_file=None,
                db=self.db,
            )

        self.assertEqual(payload["session"]["name"], "我手动命名的会话")
        self.assertEqual(self.db.get(ChatSession, 1).name, "我手动命名的会话")
        name_mock.assert_not_called()

    async def test_existing_session_messages_skip_auto_name(self):
        self.add_session()
        self.db.add(ChatMessage(paper_id="paper-1", session_id=1, role="user", content="已有问题", quote=""))
        self.db.commit()

        with (
            patch("backend.app.routes.chat.generate_session_name", new_callable=AsyncMock) as name_mock,
            patch("backend.app.routes.chat.answer_with_context", new_callable=AsyncMock, return_value="answer"),
        ):
            payload = await ask_about_quote(
                question="这是第二个问题。",
                quote="",
                paper_id="paper-1",
                session_id=1,
                stream=False,
                pdf_file=None,
                db=self.db,
            )

        self.assertEqual(payload["session"]["name"], "Session 1")
        self.assertEqual(self.db.get(ChatSession, 1).name, "Session 1")
        name_mock.assert_not_called()

    async def test_session_name_failure_does_not_block_chat(self):
        self.add_session()

        with (
            patch("backend.app.routes.chat.generate_session_name", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch("backend.app.routes.chat.answer_with_context", new_callable=AsyncMock, return_value="answer"),
        ):
            payload = await ask_about_quote(
                question="解释一下 self-attention。",
                quote="",
                paper_id="paper-1",
                session_id=1,
                stream=False,
                pdf_file=None,
                db=self.db,
            )

        self.assertEqual(payload["answer"], "answer")
        self.assertEqual(payload["session"]["name"], "Session 1")
        self.assertEqual(self.db.query(ChatMessage).filter(ChatMessage.session_id == 1).count(), 2)

    async def test_detached_session_instance_still_persists_turn(self):
        self.add_session()

        async def fake_answer_with_context(**_kwargs):
            self.db.close()
            return "answer"

        with (
            patch("backend.app.routes.chat.generate_session_name", new_callable=AsyncMock, return_value="QK 与 V 的关系"),
            patch("backend.app.routes.chat.answer_with_context", side_effect=fake_answer_with_context),
        ):
            payload = await ask_about_quote(
                question="QK 算出来的权重为什么要作用到 V 上？",
                quote="",
                paper_id="paper-1",
                session_id=1,
                stream=False,
                pdf_file=None,
                db=self.db,
            )

        self.assertEqual(payload["answer"], "answer")
        self.assertEqual(payload["session"]["name"], "QK 与 V 的关系")
        self.assertEqual(self.db.query(ChatMessage).filter(ChatMessage.session_id == 1).count(), 2)


if __name__ == "__main__":
    unittest.main()
