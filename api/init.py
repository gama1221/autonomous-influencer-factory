"""
Chimera Factory API

FastAPI-based REST API for the Autonomous Influencer Platform.
"""

__version__ = "1.0.0"
__author__ = "Chimera Team"
__description__ = "Autonomous AI Influencer Factory API"

from .v1.endpoints import trends, content, engagement
from .core.dependencies import get_db, get_redis, get_settings
from .core.security import authenticate, authorize

__all__ = [
    "trends",
    "content", 
    "engagement",
    "get_db",
    "get_redis",
    "get_settings",
    "authenticate",
    "authorize"
]