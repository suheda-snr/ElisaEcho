"""Aggregates all API route modules under a single router."""

from fastapi import APIRouter

from app.api.routes import discovery, guides, health, knowledge, search, sources, threads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(threads.router)
api_router.include_router(knowledge.router)
api_router.include_router(discovery.router)
api_router.include_router(search.router)
api_router.include_router(guides.router)
