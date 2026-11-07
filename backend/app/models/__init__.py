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
from app.models.troubleshooting import (
    GuideEdge,
    GuideNode,
    NodeEvidence,
    SessionStep,
    TroubleshootingGuide,
    TroubleshootingSession,
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "CommunicationSource",
    "ConversationThread",
    "Equipment",
    "GuideEdge",
    "GuideNode",
    "Incident",
    "KnowledgeCandidate",
    "KnowledgeChunk",
    "KnowledgeEvidence",
    "KnowledgeItem",
    "Message",
    "NodeEvidence",
    "SessionStep",
    "TroubleshootingGuide",
    "TroubleshootingSession",
    "knowledge_item_equipment",
    "knowledge_item_incidents",
]
