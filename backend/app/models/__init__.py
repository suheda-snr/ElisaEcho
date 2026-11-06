"""SQLAlchemy ORM models. Importing this package registers every table on Base.metadata."""

from app.models.associations import knowledge_item_equipment, knowledge_item_incidents
from app.models.communication import CommunicationSource, ConversationThread, Message
from app.models.knowledge import (
    EMBEDDING_DIMENSION,
    KnowledgeCandidate,
    KnowledgeChunk,
    KnowledgeEvidence,
    KnowledgeItem,
)
from app.models.reference import Equipment, Incident

__all__ = [
    "EMBEDDING_DIMENSION",
    "CommunicationSource",
    "ConversationThread",
    "Equipment",
    "Incident",
    "KnowledgeCandidate",
    "KnowledgeChunk",
    "KnowledgeEvidence",
    "KnowledgeItem",
    "Message",
    "knowledge_item_equipment",
    "knowledge_item_incidents",
]
