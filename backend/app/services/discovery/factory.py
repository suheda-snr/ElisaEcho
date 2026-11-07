"""Build the discovery engine (shared by the API process and the Slack worker)."""

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiClient
from app.core.config import Settings
from app.db.session import get_sessionmaker
from app.services.discovery.engine import DiscoveryEngine


def build_discovery_engine(settings: Settings, gemini: GeminiClient, embeddings: EmbeddingService) -> DiscoveryEngine:
    return DiscoveryEngine(
        session_factory=lambda: get_sessionmaker()(),
        gemini_factory=lambda: gemini,
        embedder_factory=lambda: embeddings,
        debounce_seconds=settings.discovery_debounce_seconds,
        message_interval_seconds=settings.simulation_message_interval_seconds,
        max_concurrent_analyses=settings.discovery_max_concurrent_analyses,
    )
