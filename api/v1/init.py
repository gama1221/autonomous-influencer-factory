"""
API Version 1

REST API endpoints for Chimera Factory v1.
"""

from fastapi import APIRouter

from .endpoints import trends, content, engagement

api_v1_router = APIRouter(prefix="/v1")

# Include all endpoint routers
api_v1_router.include_router(trends.router, prefix="/trends", tags=["trends"])
api_v1_router.include_router(content.router, prefix="/content", tags=["content"])
api_v1_router.include_router(engagement.router, prefix="/engagement", tags=["engagement"])

__all__ = ["api_v1_router"]