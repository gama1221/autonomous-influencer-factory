"""
FastAPI Dependencies

Shared dependencies for the API layer.
"""

import os
from typing import Generator, Optional
from contextlib import contextmanager

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from redis import Redis
from pydantic import BaseSettings

from utils.logging.structured_logger import get_logger

logger = get_logger("api.dependencies")


class Settings(BaseSettings):
    """Application settings"""
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/chimera")
    database_pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "20"))
    database_max_overflow: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "40"))
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "development-secret-key-change-in-production")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # API
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    api_version: str = os.getenv("API_VERSION", "v1")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Rate limiting
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
    
    # External APIs
    youtube_api_key: Optional[str] = os.getenv("YOUTUBE_API_KEY")
    tiktok_access_token: Optional[str] = os.getenv("TIKTOK_ACCESS_TOKEN")
    twitter_bearer_token: Optional[str] = os.getenv("TWITTER_BEARER_TOKEN")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # CORS
    cors_origins: list = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()

# Database engine
engine = create_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Check connections before using
    echo=settings.debug  # SQL logging in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Redis connection pool
redis_pool = None


def get_settings() -> Settings:
    """Get application settings"""
    return settings


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    
    Yields:
        SQLAlchemy session
        
    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Database session error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error"
        )
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Useful for background tasks and non-FastAPI contexts.
    
    Usage:
        with get_db_context() as db:
            item = db.query(Item).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_redis() -> Redis:
    """
    Redis connection dependency.
    
    Returns:
        Redis connection
        
    Usage:
        @app.get("/cache/{key}")
        def get_cache(key: str, redis: Redis = Depends(get_redis)):
            return redis.get(key)
    """
    global redis_pool
    
    if redis_pool is None:
        redis_pool = Redis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True
        )
    
    try:
        # Test connection
        redis_pool.ping()
        return redis_pool
    except Exception as e:
        logger.error("Redis connection error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service unavailable"
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user.
    
    Args:
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
    
    # In production, you would fetch user from database
    # For now, return a placeholder user
    user = {
        "username": username,
        "permissions": payload.get("permissions", []),
        "role": payload.get("role", "user")
    }
    
    return user


def get_rate_limiter() -> dict:
    """
    Rate limiting dependency.
    
    Returns:
        Rate limiting configuration
    """
    return {
        "requests": settings.rate_limit_requests,
        "window": settings.rate_limit_window
    }


def get_external_apis() -> dict:
    """
    External API credentials dependency.
    
    Returns:
        Dictionary of API credentials
    """
    return {
        "youtube": settings.youtube_api_key,
        "tiktok": settings.tiktok_access_token,
        "twitter": settings.twitter_bearer_token,
        "openai": settings.openai_api_key
    }


# OAuth2 scheme for token authentication
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/{settings.api_version}/auth/token",
    auto_error=False  # Don't auto-raise on missing token
)


def authenticate(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Authentication dependency.
    
    Args:
        token: Optional JWT token
        
    Returns:
        Authentication payload or anonymous user
        
    Note:
        This is a simplified version. In production, use proper JWT validation.
    """
    if not token:
        # Anonymous user
        return {
            "authenticated": False,
            "user_id": None,
            "role": "anonymous",
            "permissions": ["read:public"]
        }
    
    try:
        # In production, validate JWT token
        # For now, parse a simple format
        import jwt
        
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        
        return {
            "authenticated": True,
            "user_id": payload.get("sub"),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", []),
            "token_payload": payload
        }
    except Exception:
        # Invalid token
        return {
            "authenticated": False,
            "user_id": None,
            "role": "anonymous",
            "permissions": ["read:public"]
        }


# Health check dependency
def health_check() -> dict:
    """
    Health check endpoint dependency.
    
    Returns:
        Health status
    """
    try:
        # Check database
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Check Redis
        redis = get_redis()
        redis.ping()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Request context dependency
from contextvars import ContextVar
import uuid

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """
    Get or generate request ID for correlation.
    
    Returns:
        Request ID string
    """
    request_id = request_id_var.get()
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        request_id_var.set(request_id)
    
    return request_id


# Performance monitoring dependency
def get_performance_monitor() -> dict:
    """
    Performance monitoring configuration.
    
    Returns:
        Monitoring configuration
    """
    return {
        "enabled": not settings.debug,  # Disable in debug mode
        "sample_rate": 0.1,  # Sample 10% of requests
        "threshold_ms": 1000  # Log slow requests > 1s
    }


# Feature flag dependency
def get_feature_flags() -> dict:
    """
    Feature flag configuration.
    
    Returns:
        Feature flags
    """
    return {
        "ai_content_generation": os.getenv("FEATURE_AI_CONTENT", "true").lower() == "true",
        "auto_scheduling": os.getenv("FEATURE_AUTO_SCHEDULE", "true").lower() == "true",
        "multi_platform_publishing": os.getenv("FEATURE_MULTI_PLATFORM", "true").lower() == "true",
        "audience_analytics": os.getenv("FEATURE_ANALYTICS", "true").lower() == "true",
        "trend_prediction": os.getenv("FEATURE_PREDICTION", "false").lower() == "true",
        "content_safety": os.getenv("FEATURE_SAFETY", "true").lower() == "true"
    }