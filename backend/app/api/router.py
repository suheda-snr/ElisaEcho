"""Aggregates all API route modules under a single router."""

from fastapi import APIRouter

from app.api.routes import (
    discovery,
    feedback,
    guides,
    health,
    integrations,
    knowledge,
    knowledge_groups,
    search,
    sources,
    threads,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(threads.router)
api_router.include_router(knowledge.router)
api_router.include_router(knowledge_groups.router)
api_router.include_router(discovery.router)
api_router.include_router(search.router)
api_router.include_router(guides.router)
api_router.include_router(feedback.router)
api_router.include_router(integrations.router)
