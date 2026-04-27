from .base import BaseOrchestrator

__all__ = ["BaseOrchestrator", "ConversationOrchestrator", "NotesOrchestrator"]


def __getattr__(name):
    if name == "ConversationOrchestrator":
        from .conversation import ConversationOrchestrator

        return ConversationOrchestrator
    if name == "NotesOrchestrator":
        from .notes import NotesOrchestrator

        return NotesOrchestrator
    raise AttributeError(name)
