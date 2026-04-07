from fastapi import APIRouter

from .chat import router as chat_router
from .knowledge_graph import router as knowledge_graph_router
from .notes import router as notes_router
from .papers import router as papers_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(papers_router)
router.include_router(notes_router)
router.include_router(knowledge_graph_router)
