"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import files, health, history, providers, solutions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(providers.router)
api_router.include_router(solutions.router)
api_router.include_router(files.router)
api_router.include_router(history.router)
