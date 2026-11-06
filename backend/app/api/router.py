"""Aggregates all API route modules under a single router."""

from fastapi import APIRouter

from app.api.routes import health, knowledge, sources, threads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(threads.router)
api_router.include_router(knowledge.router)
