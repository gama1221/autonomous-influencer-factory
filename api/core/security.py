"""
Security Module

Authentication, authorization, and security utilities.
"""

import os
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import wraps

import jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
import redis

from .dependencies import get_redis, get_settings, authenticate
from utils.logging.structured_logger import get_logger

logger = get_logger("security")


# Security models
class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str  # Subject (user ID)
    role: str
    permissions: List[str]
    exp: datetime
    iat: datetime
    
    @validator('exp', 'iat', pre=True)
    def parse_datetime(cls, v):
        """Parse datetime from timestamp"""
        if isinstance(v, (int, float)):
            return datetime.utcfromtimestamp(v)
        return v


class User(BaseModel):
    """User model"""
    id: str
    username: str
    email: str
    role: str
    permissions: List[str]
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class Permission(BaseModel):
    """Permission model"""
    resource: str
    action: str
    description: str


# Security configuration
class SecurityConfig:
    """Security configuration"""
    
    # JWT configuration
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES = 30
    JWT_REFRESH_EXPIRE_DAYS = 7
    
    # Password hashing
    PASSWORD_HASH_ALGORITHM = "bcrypt"
    PASSWORD_SALT_ROUNDS = 12
    
    # Rate limiting
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 100
    
    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    # CORS settings
    CORS_ALLOW_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS = ["Authorization", "Content-Type", "X-Request-ID"]
    
    # Permission matrix
    PERMISSIONS = {
        "admin": {
            "trends": ["create", "read", "update", "delete", "analyze"],
            "content": ["create", "read", "update", "delete", "publish", "approve"],
            "engagement": ["read", "analyze", "manage"],
            "users": ["create", "read", "update", "delete", "manage"],
            "system": ["configure", "monitor", "maintain"]
        },
        "editor": {
            "trends": ["create", "read", "update", "analyze"],
            "content": ["create", "read", "update", "publish"],
            "engagement": ["read", "analyze"],
            "users": ["read"]
        },
        "viewer": {
            "trends": ["read"],
            "content": ["read"],
            "engagement": ["read"],
            "users": ["read"]
        }
    }


# Authentication
class Authenticator:
    """Authentication handler"""
    
    def __init__(self, secret_key: str, redis_client: redis.Redis):
        self.secret_key = secret_key
        self.redis = redis_client
        self.config = SecurityConfig()
    
    def create_access_token(
        self,
        user_id: str,
        role: str,
        permissions: List[str],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User identifier
            role: User role
            permissions: List of permissions
            expires_delta: Optional token expiration
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.config.JWT_ACCESS_EXPIRE_MINUTES
            )
        
        payload = {
            "sub": user_id,
            "role": role,
            "permissions": permissions,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.config.JWT_ALGORITHM
        )
        
        # Store token in Redis (for invalidation)
        token_key = f"token:{user_id}:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
        self.redis.setex(
            token_key,
            int(expire.timestamp() - time.time()),
            "valid"
        )
        
        logger.info("Access token created", user_id=user_id, role=role)
        
        return token
    
    def create_refresh_token(self, user_id: str) -> str:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User identifier
            
        Returns:
            JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=self.config.JWT_REFRESH_EXPIRE_DAYS)
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.config.JWT_ALGORITHM
        )
        
        # Store refresh token
        refresh_key = f"refresh:{user_id}:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
        self.redis.setex(
            refresh_key,
            int(expire.timestamp() - time.time()),
            "valid"
        )
        
        logger.info("Refresh token created", user_id=user_id)
        
        return token
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """
        Verify JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenPayload if valid, None otherwise
        """
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.config.JWT_ALGORITHM]
            )
            
            # Check token type
            if payload.get("type") != "access":
                logger.warning("Invalid token type", token_type=payload.get("type"))
                return None
            
            # Check if token is blacklisted
            user_id = payload.get("sub")
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            token_key = f"token:{user_id}:{token_hash}"
            
            if not self.redis.exists(token_key):
                logger.warning("Token not found in store", user_id=user_id)
                return None
            
            # Convert to TokenPayload
            token_payload = TokenPayload(**payload)
            
            return token_payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e))
            return None
        except Exception as e:
            logger.error("Token verification error", error=str(e))
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token or None
        """
        try:
            # Verify refresh token
            payload = jwt.decode(
                refresh_token,
                self.secret_key,
                algorithms=[self.config.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "refresh":
                return None
            
            user_id = payload.get("sub")
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()[:16]
            refresh_key = f"refresh:{user_id}:{token_hash}"
            
            if not self.redis.exists(refresh_key):
                return None
            
            # Get user data (in production, fetch from database)
            user_data = self._get_user_data(user_id)
            if not user_data:
                return None
            
            # Create new access token
            new_token = self.create_access_token(
                user_id=user_id,
                role=user_data.get("role", "user"),
                permissions=user_data.get("permissions", [])
            )
            
            logger.info("Access token refreshed", user_id=user_id)
            
            return new_token
            
        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            return None
    
    def invalidate_token(self, token: str) -> bool:
        """
        Invalidate a token.
        
        Args:
            token: Token to invalidate
            
        Returns:
            True if successful
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.config.JWT_ALGORITHM]
            )
            
            user_id = payload.get("sub")
            token_type = payload.get("type")
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            
            if token_type == "access":
                key = f"token:{user_id}:{token_hash}"
            else:
                key = f"refresh:{user_id}:{token_hash}"
            
            self.redis.delete(key)
            logger.info("Token invalidated", user_id=user_id, token_type=token_type)
            
            return True
            
        except Exception as e:
            logger.error("Token invalidation failed", error=str(e))
            return False
    
    def _get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user data from storage.
        
        Args:
            user_id: User identifier
            
        Returns:
            User data dictionary
        """
        # In production, fetch from database
        # For now, return mock data
        user_roles = {
            "admin": {
                "role": "admin",
                "permissions": self._get_permissions_for_role("admin")
            },
            "editor": {
                "role": "editor",
                "permissions": self._get_permissions_for_role("editor")
            },
            "viewer": {
                "role": "viewer",
                "permissions": self._get_permissions_for_role("viewer")
            }
        }
        
        # Default to viewer if user not found
        return user_roles.get(user_id.split("_")[0] if "_" in user_id else "viewer")
    
    def _get_permissions_for_role(self, role: str) -> List[str]:
        """Get permissions for a role"""
        permissions = []
        role_perms = SecurityConfig.PERMISSIONS.get(role, {})
        
        for resource, actions in role_perms.items():
            for action in actions:
                permissions.append(f"{resource}:{action}")
        
        return permissions


# Authorization
def authorize(auth_payload: Dict[str, Any], permission: str) -> bool:
    """
    Check if authenticated user has required permission.
    
    Args:
        auth_payload: Authentication payload from authenticate()
        permission: Required permission (format: "resource:action")
        
    Returns:
        True if authorized
    """
    if not auth_payload.get("authenticated", False):
        logger.warning("Authorization failed: not authenticated")
        return False
    
    user_permissions = auth_payload.get("permissions", [])
    user_role = auth_payload.get("role", "anonymous")
    
    # Check direct permission
    if permission in user_permissions:
        return True
    
    # Check wildcard permissions
    resource, action = permission.split(":", 1) if ":" in permission else (permission, "*")
    
    # Check resource:* permission
    if f"{resource}:*" in user_permissions:
        return True
    
    # Check *:action permission
    if f"*:{action}" in user_permissions:
        return True
    
    # Check admin override
    if user_role == "admin":
        return True
    
    logger.warning(
        "Authorization failed",
        user_role=user_role,
        required_permission=permission,
        user_permissions=user_permissions
    )
    
    return False


def require_permission(permission: str):
    """
    Decorator to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get auth from kwargs or request
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                auth = request.state.auth if hasattr(request.state, "auth") else None
            else:
                # Try to get from kwargs
                auth = kwargs.get("auth")
            
            if not auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not authorize(auth, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Rate limiting
class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.config = SecurityConfig()
    
    def is_rate_limited(
        self,
        identifier: str,
        window: int = None,
        max_requests: int = None
    ) -> bool:
        """
        Check if request is rate limited.
        
        Args:
            identifier: Rate limit identifier (e.g., user_id, IP)
            window: Time window in seconds
            max_requests: Maximum requests in window
            
        Returns:
            True if rate limited
        """
        window = window or self.config.RATE_LIMIT_WINDOW
        max_requests = max_requests or self.config.RATE_LIMIT_MAX_REQUESTS
        
        key = f"rate_limit:{identifier}:{int(time.time() // window)}"
        
        try:
            # Increment counter
            current = self.redis.incr(key)
            
            # Set expiration if this is the first request
            if current == 1:
                self.redis.expire(key, window)
            
            # Check limit
            if current > max_requests:
                logger.warning(
                    "Rate limit exceeded",
                    identifier=identifier,
                    current=current,
                    max=max_requests
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Fail open - don't block requests if Redis is down
            return False
    
    def get_remaining_requests(
        self,
        identifier: str,
        window: int = None,
        max_requests: int = None
    ) -> int:
        """
        Get remaining requests in current window.
        
        Args:
            identifier: Rate limit identifier
            window: Time window in seconds
            max_requests: Maximum requests in window
            
        Returns:
            Remaining requests
        """
        window = window or self.config.RATE_LIMIT_WINDOW
        max_requests = max_requests or self.config.RATE_LIMIT_MAX_REQUESTS
        
        key = f"rate_limit:{identifier}:{int(time.time() // window)}"
        
        try:
            current = int(self.redis.get(key) or 0)
            remaining = max(0, max_requests - current)
            return remaining
        except Exception:
            return max_requests


# Password hashing
class PasswordHasher:
    """Password hashing utilities"""
    
    def __init__(self):
        self.config = SecurityConfig()
    
    def hash_password(self, password: str) -> str:
        """
        Hash password.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        import bcrypt
        
        salt = bcrypt.gensalt(rounds=self.config.PASSWORD_SALT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode(), salt)
        
        return hashed.decode()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            password: Plain text password
            hashed: Hashed password
            
        Returns:
            True if password matches
        """
        import bcrypt
        
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False


# Input validation and sanitization
class InputValidator:
    """Input validation and sanitization"""
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """
        Sanitize string input.
        
        Args:
            input_str: Input string
            max_length: Maximum length
            
        Returns:
            Sanitized string
        """
        import html
        
        # Trim whitespace
        sanitized = input_str.strip()
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Escape HTML
        sanitized = html.escape(sanitized)
        
        return sanitized
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address.
        
        Args:
            email: Email address
            
        Returns:
            True if valid
        """
        import re
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL.
        
        Args:
            url: URL string
            
        Returns:
            True if valid
        """
        import re
        
        pattern = r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w.%?=&]*)*$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def sanitize_dict(input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize dictionary values.
        
        Args:
            input_dict: Input dictionary
            
        Returns:
            Sanitized dictionary
        """
        sanitized = {}
        
        for key, value in input_dict.items():
            if isinstance(value, str):
                sanitized[key] = InputValidator.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = InputValidator.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    InputValidator.sanitize_string(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized


# Request signing
class RequestSigner:
    """Request signing for API security"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
    
    def sign_request(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        timestamp: Optional[int] = None
    ) -> str:
        """
        Sign API request.
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body
            timestamp: Unix timestamp
            
        Returns:
            Signature string
        """
        timestamp = timestamp or int(time.time())
        
        # Create signature payload
        payload = f"{method}|{path}|{timestamp}|".encode() + body
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key,
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}:{signature}"
    
    def verify_request(
        self,
        method: str,
        path: str,
        body: bytes,
        signature: str,
        max_age: int = 300
    ) -> bool:
        """
        Verify API request signature.
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body
            signature: Signature string
            max_age: Maximum age in seconds
            
        Returns:
            True if valid
        """
        try:
            timestamp_str, received_signature = signature.split(":", 1)
            timestamp = int(timestamp_str)
            
            # Check timestamp
            current_time = int(time.time())
            if abs(current_time - timestamp) > max_age:
                logger.warning("Request signature expired", timestamp=timestamp)
                return False
            
            # Generate expected signature
            expected_signature = self.sign_request(method, path, body, timestamp)
            _, expected_sig = expected_signature.split(":", 1)
            
            # Compare signatures
            if not hmac.compare_digest(received_signature, expected_sig):
                logger.warning("Invalid request signature")
                return False
            
            return True
            
        except Exception as e:
            logger.error("Signature verification failed", error=str(e))
            return False


# Security middleware
async def security_middleware(request: Request, call_next):
    """
    Security middleware for adding security headers and request validation.
    
    Args:
        request: FastAPI request
        call_next: Next middleware
        
    Returns:
        Response
    """
    # Add security headers
    response = await call_next(request)
    
    for header, value in SecurityConfig.SECURITY_HEADERS.items():
        response.headers[header] = value
    
    # Add request ID for correlation
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    
    response.headers["X-Request-ID"] = request_id
    
    return response


# Dependency injection setup
def get_authenticator() -> Authenticator:
    """Get authenticator instance"""
    settings = get_settings()
    redis_client = get_redis()
    return Authenticator(settings.secret_key, redis_client)


def get_rate_limiter_dep() -> RateLimiter:
    """Get rate limiter instance"""
    redis_client = get_redis()
    return RateLimiter(redis_client)


def get_password_hasher() -> PasswordHasher:
    """Get password hasher instance"""
    return PasswordHasher()


def get_input_validator() -> InputValidator:
    """Get input validator instance"""
    return InputValidator()


def get_request_signer() -> RequestSigner:
    """Get request signer instance"""
    settings = get_settings()
    return RequestSigner(settings.secret_key)


# Export
__all__ = [
    "SecurityConfig",
    "Authenticator",
    "TokenPayload",
    "User",
    "Permission",
    "authorize",
    "require_permission",
    "RateLimiter",
    "PasswordHasher",
    "InputValidator",
    "RequestSigner",
    "security_middleware",
    "get_authenticator",
    "get_rate_limiter_dep",
    "get_password_hasher",
    "get_input_validator",
    "get_request_signer"
]