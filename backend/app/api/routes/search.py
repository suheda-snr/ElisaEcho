from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.ai.embeddings import EmbeddingService
from app.api.deps import DbSession, SettingsDep
from app.schemas.search import RetrievalInfo, SearchRequest, SearchResponse
from app.services.retrieval.results import build_results
from app.services.retrieval.search import SearchFilters, hybrid_search

router = APIRouter(tags=["search"])


def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embeddings


@router.post("/search", response_model=SearchResponse, summary="Hybrid knowledge search")
async def search(
    body: SearchRequest,
    session: DbSession,
    settings: SettingsDep,
    embedder: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> SearchResponse:
    """Semantic (pgvector) + full-text + exact identifier search, fused with Reciprocal Rank
    Fusion. If embeddings are unavailable the response says so and keyword/identifier
    results are still returned."""
    outcome = await hybrid_search(
        session,
        body.query,
        embedder,
        limit=body.limit,
        filters=SearchFilters(**body.filters.model_dump()),
        pool=settings.search_candidate_pool,
        min_similarity=settings.search_min_similarity,
        similarity_margin=settings.search_similarity_margin,
    )
    results = await build_results(session, outcome.ranked)
    return SearchResponse(
        query=body.query,
        results=results,
        retrieval=RetrievalInfo(
            semantic=outcome.semantic_status,
            semantic_detail=outcome.semantic_detail,
            identifiers=outcome.identifiers,
            embedding_model=embedder.model if embedder.configured else None,
        ),
    )
