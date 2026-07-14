from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user
from .auth import router as auth_router

from .chat import router as chat_router
from .knowledge_graph import router as knowledge_graph_router
from .notes import router as notes_router
from .papers import router as papers_router
from .users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
protected = [Depends(get_current_user)]
router.include_router(chat_router, dependencies=protected)
router.include_router(papers_router, dependencies=protected)
router.include_router(notes_router, dependencies=protected)
router.include_router(knowledge_graph_router, dependencies=protected)
