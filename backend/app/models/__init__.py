"""SQLAlchemy ORM models. Importing this package registers every table on Base.metadata."""

from app.models.associations import knowledge_item_equipment, knowledge_item_incidents
from app.models.communication import CommunicationSource, ConversationThread, Message
from app.models.knowledge import (
    EMBEDDING_DIMENSION,
    KnowledgeCandidate,
    KnowledgeChunk,
    KnowledgeEntityLink,
    KnowledgeEvidence,
    KnowledgeItem,
)
from app.models.consolidation import (
    KnowledgeConsolidationState,
    KnowledgeGroup,
    KnowledgeGroupMember,
    KnowledgeRelationship,
)
from app.models.feedback import TroubleshootingFeedback
from app.models.integrations import EmailConnection, IntegrationEvent, IntegrationState
from app.models.reference import Equipment, Incident, Site
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
    "EmailConnection",
    "CommunicationSource",
    "ConversationThread",
    "Equipment",
    "GuideEdge",
    "GuideNode",
    "Incident",
    "IntegrationEvent",
    "IntegrationState",
    "KnowledgeCandidate",
    "KnowledgeChunk",
    "KnowledgeConsolidationState",
    "KnowledgeEntityLink",
    "KnowledgeEvidence",
    "KnowledgeGroup",
    "KnowledgeGroupMember",
    "KnowledgeItem",
    "KnowledgeRelationship",
    "Message",
    "NodeEvidence",
    "SessionStep",
    "Site",
    "TroubleshootingGuide",
    "TroubleshootingFeedback",
    "TroubleshootingSession",
    "knowledge_item_equipment",
    "knowledge_item_incidents",
]
