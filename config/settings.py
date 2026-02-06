"""
Application Settings Management

Centralized configuration management with environment-specific settings.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseSettings, Field, validator, root_validator
from pydantic.networks import PostgresDsn, RedisDsn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Environment(str, Enum):
    """Application environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    url: PostgresDsn = Field(
        default=PostgresDsn("postgresql://user:pass@localhost:5432/chimera"),
        description="PostgreSQL connection URL"
    )
    pool_size: int = Field(default=20, ge=1, le=100)
    max_overflow: int = Field(default=40, ge=0)
    pool_timeout: int = Field(default=30, ge=1)
    pool_recycle: int = Field(default=3600, ge=1)
    echo: bool = Field(default=False, description="SQL echo mode")
    
    class Config:
        env_prefix = "DATABASE_"


class RedisConfig(BaseSettings):
    """Redis configuration"""
    url: RedisDsn = Field(
        default=RedisDsn("redis://localhost:6379/0"),
        description="Redis connection URL"
    )
    max_connections: int = Field(default=50, ge=1)
    socket_timeout: int = Field(default=5, ge=1)
    socket_connect_timeout: int = Field(default=5, ge=1)
    
    class Config:
        env_prefix = "REDIS_"


class APIConfig(BaseSettings):
    """API configuration"""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1)
    reload: bool = Field(default=False)
    cors_origins: List[str] = Field(default=["http://localhost:3000"])
    api_prefix: str = Field(default="/api")
    api_version: str = Field(default="v1")
    docs_url: Optional[str] = Field(default="/docs")
    redoc_url: Optional[str] = Field(default="/redoc")
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_prefix = "API_"


class SecurityConfig(BaseSettings):
    """Security configuration"""
    secret_key: str = Field(
        default="development-secret-key-change-in-production",
        min_length=32
    )
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    password_hash_rounds: int = Field(default=12, ge=4, le=20)
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)
    
    class Config:
        env_prefix = "SECURITY_"


class ExternalAPIConfig(BaseSettings):
    """External API configurations"""
    youtube_api_key: Optional[str] = None
    tiktok_access_token: Optional[str] = None
    twitter_bearer_token: Optional[str] = None
    openai_api_key: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    instagram_access_token: Optional[str] = None
    facebook_page_token: Optional[str] = None
    
    class Config:
        env_prefix = ""


class AgentConfig(BaseSettings):
    """Agent configuration"""
    research_agent_interval: str = Field(default="4h", regex=r'^\d+[hd]$')
    content_agent_batch_size: int = Field(default=10, ge=1, le=100)
    engagement_agent_polling_interval: int = Field(default=300, ge=30)
    max_concurrent_agents: int = Field(default=5, ge=1, le=50)
    agent_timeout: int = Field(default=3600, ge=60)
    
    class Config:
        env_prefix = "AGENT_"


class SkillConfig(BaseSettings):
    """Skill framework configuration"""
    skill_timeout: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: int = Field(default=2, ge=0)
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    circuit_breaker_timeout: int = Field(default=60, ge=10)
    
    class Config:
        env_prefix = "SKILL_"


class LoggingConfig(BaseSettings):
    """Logging configuration"""
    level: LogLevel = Field(default=LogLevel.INFO)
    format: str = Field(
        default="json",
        regex="^(json|text)$"
    )
    file_path: Optional[str] = Field(None)
    max_file_size: int = Field(default=104857600, ge=1048576)  # 100MB
    backup_count: int = Field(default=10, ge=0)
    
    class Config:
        env_prefix = "LOGGING_"


class MonitoringConfig(BaseSettings):
    """Monitoring configuration"""
    enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    traces_endpoint: Optional[str] = Field(None)
    metrics_endpoint: Optional[str] = Field(None)
    logs_endpoint: Optional[str] = Field(None)
    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    class Config:
        env_prefix = "MONITORING_"


class StorageConfig(BaseSettings):
    """Storage configuration"""
    media_bucket: str = Field(default="chimera-media")
    archive_bucket: str = Field(default="chimera-archive")
    max_file_size: int = Field(default=1073741824, ge=1048576)  # 1GB
    allowed_mime_types: List[str] = Field(
        default=[
            "video/mp4",
            "image/jpeg",
            "image/png",
            "audio/mpeg",
            "application/json"
        ]
    )
    
    class Config:
        env_prefix = "STORAGE_"


class FeatureFlags(BaseSettings):
    """Feature flags"""
    ai_content_generation: bool = Field(default=True)
    auto_scheduling: bool = Field(default=True)
    multi_platform_publishing: bool = Field(default=True)
    audience_analytics: bool = Field(default=True)
    trend_prediction: bool = Field(default=False)
    content_safety: bool = Field(default=True)
    openclaw_integration: bool = Field(default=False)
    mcp_enabled: bool = Field(default=True)
    
    class Config:
        env_prefix = "FEATURE_"


class Settings(BaseSettings):
    """
    Main application settings
    
    Combines all configuration sections and provides environment-specific defaults.
    """
    
    # Core
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    project_name: str = Field(default="Chimera Factory")
    version: str = Field(default="1.0.0")
    
    # Sub-configurations
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    api: APIConfig = APIConfig()
    security: SecurityConfig = SecurityConfig()
    external_apis: ExternalAPIConfig = ExternalAPIConfig()
    agent: AgentConfig = AgentConfig()
    skill: SkillConfig = SkillConfig()
    logging: LoggingConfig = LoggingConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    storage: StorageConfig = StorageConfig()
    features: FeatureFlags = FeatureFlags()
    
    # Computed properties
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING
    
    @property
    def database_url_private(self) -> str:
        """Get database URL without password for logging"""
        url = str(self.database.url)
        if "@" in url:
            scheme, rest = url.split("://", 1)
            if ":" in rest.split("@")[0]:
                user_pass, host = rest.split("@", 1)
                user = user_pass.split(":")[0]
                return f"{scheme}://{user}:****@{host}"
        return url
    
    @root_validator(pre=True)
    def set_environment_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Set environment-specific defaults"""
        env = values.get("environment", Environment.DEVELOPMENT)
        
        # Environment-specific defaults
        if env == Environment.DEVELOPMENT:
            values.setdefault("debug", True)
            values.setdefault("api", {}).setdefault("reload", True)
            values.setdefault("logging", {}).setdefault("level", LogLevel.DEBUG)
            
        elif env == Environment.TESTING:
            values.setdefault("database", {}).setdefault(
                "url",
                "postgresql://test:test@localhost:5432/chimera_test"
            )
            values.setdefault("redis", {}).setdefault(
                "url",
                "redis://localhost:6379/1"
            )
            values.setdefault("api", {}).setdefault("docs_url", None)
            values.setdefault("api", {}).setdefault("redoc_url", None)
            
        elif env == Environment.PRODUCTION:
            values.setdefault("debug", False)
            values.setdefault("api", {}).setdefault("reload", False)
            values.setdefault("logging", {}).setdefault("level", LogLevel.INFO)
            values.setdefault("api", {}).setdefault("docs_url", None)
            values.setdefault("api", {}).setdefault("redoc_url", None)
            
        return values
    
    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """
        Convert settings to dictionary
        
        Args:
            mask_secrets: Whether to mask sensitive values
            
        Returns:
            Settings dictionary
        """
        data = self.dict()
        
        if mask_secrets:
            # Mask sensitive values
            if "database" in data and "url" in data["database"]:
                data["database"]["url"] = self.database_url_private
            
            # Mask API keys
            if "external_apis" in data:
                for key in data["external_apis"]:
                    if data["external_apis"][key]:
                        data["external_apis"][key] = "****"
            
            # Mask secret key
            if "security" in data and "secret_key" in data["security"]:
                data["security"]["secret_key"] = "****"
        
        return data
    
    def save_to_file(self, filepath: str, format: str = "json") -> None:
        """
        Save settings to file
        
        Args:
            filepath: Path to save file
            format: File format (json or yaml)
        """
        data = self.to_dict(mask_secrets=False)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if format.lower() == "json":
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
        
        elif format.lower() == "yaml":
            with open(filepath, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    @classmethod
    def from_file(cls, filepath: str) -> "Settings":
        """
        Load settings from file
        
        Args:
            filepath: Path to settings file
            
        Returns:
            Settings instance
        """
        with open(filepath, "r") as f:
            if filepath.endswith(".json"):
                data = json.load(f)
            elif filepath.endswith((".yaml", ".yml")):
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {filepath}")
        
        return cls(**data)
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False
        validate_assignment = True


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get settings instance (singleton pattern)
    
    Returns:
        Settings instance
    """
    global _settings
    
    if _settings is None:
        _settings = Settings()
    
    return _settings


def reload_settings() -> None:
    """Reload settings from environment"""
    global _settings
    _settings = Settings()


def get_settings_dict(mask_secrets: bool = True) -> Dict[str, Any]:
    """
    Get settings as dictionary
    
    Args:
        mask_secrets: Whether to mask sensitive values
        
    Returns:
        Settings dictionary
    """
    return get_settings().to_dict(mask_secrets=mask_secrets)


# Export
__all__ = [
    "Environment",
    "LogLevel",
    "DatabaseConfig",
    "RedisConfig",
    "APIConfig",
    "SecurityConfig",
    "ExternalAPIConfig",
    "AgentConfig",
    "SkillConfig",
    "LoggingConfig",
    "MonitoringConfig",
    "StorageConfig",
    "FeatureFlags",
    "Settings",
    "get_settings",
    "reload_settings",
    "get_settings_dict"
]