"""
Database Models

SQLAlchemy models for the Chimera Factory database.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from datetime import datetime

Base = declarative_base()


def generate_uuid():
    """Generate a UUID for primary keys"""
    return str(uuid.uuid4())


class Trend(Base):
    """Trend model - stores discovered trends from social platforms"""
    __tablename__ = "trends"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # External identifiers
    external_id = Column(String(255), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    
    # Content
    title = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(100), index=True)
    
    # Engagement metrics
    engagement_score = Column(Float, nullable=False, default=0.0)
    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(BigInteger, default=0)
    shares = Column(BigInteger, default=0)
    
    # Temporal
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Analysis
    virality_score = Column(Float, default=0.0)
    sentiment_score = Column(Float, default=0.0)
    novelty_score = Column(Float, default=0.0)
    competition_score = Column(Float, default=0.0)
    
    # Metadata
    tags = Column(ARRAY(String(100)), default=[])
    metadata = Column(JSON, default=dict)
    raw_data = Column(JSON, default=dict)
    
    # Relationships
    content_briefs = relationship("ContentBrief", back_populates="trend")
    correlations = relationship("TrendCorrelation", foreign_keys="TrendCorrelation.trend_a_id")
    
    # Indexes
    __table_args__ = (
        Index('ix_trends_platform_discovered', 'platform', 'discovered_at'),
        Index('ix_trends_engagement_score', 'engagement_score'),
        Index('ix_trends_virality_score', 'virality_score'),
        Index('ix_trends_expires_at', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<Trend(id={self.id}, platform='{self.platform}', title='{self.title[:50]}...')>"


class TrendMetric(Base):
    """Detailed trend metrics over time"""
    __tablename__ = "trend_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trend_id = Column(UUID(as_uuid=True), ForeignKey("trends.id"), nullable=False, index=True)
    
    # Metrics at specific time
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    engagement_score = Column(Float, nullable=False)
    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(BigInteger, default=0)
    shares = Column(BigInteger, default=0)
    
    # Derived metrics
    growth_rate = Column(Float, default=0.0)
    velocity = Column(Float, default=0.0)
    
    # Relationships
    trend = relationship("Trend", backref="metrics")
    
    __table_args__ = (
        Index('ix_trend_metrics_trend_timestamp', 'trend_id', 'timestamp'),
    )


class TrendCorrelation(Base):
    """Correlations between trends"""
    __tablename__ = "trend_correlations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Correlated trends
    trend_a_id = Column(UUID(as_uuid=True), ForeignKey("trends.id"), nullable=False, index=True)
    trend_b_id = Column(UUID(as_uuid=True), ForeignKey("trends.id"), nullable=False, index=True)
    
    # Correlation details
    correlation_type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    evidence = Column(JSON, default=dict)
    
    # Temporal
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, index=True)
    
    # Relationships
    trend_a = relationship("Trend", foreign_keys=[trend_a_id])
    trend_b = relationship("Trend", foreign_keys=[trend_b_id])
    
    __table_args__ = (
        Index('ix_trend_correlations_pair', 'trend_a_id', 'trend_b_id', unique=True),
        Index('ix_trend_correlations_confidence', 'confidence'),
    )


class ContentBrief(Base):
    """Content brief generated from trend analysis"""
    __tablename__ = "content_briefs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source
    trend_id = Column(UUID(as_uuid=True), ForeignKey("trends.id"), nullable=False, index=True)
    
    # Target
    target_platform = Column(String(50), nullable=False, index=True)
    content_type = Column(String(50), nullable=False)
    
    # Content
    title = Column(Text, nullable=False)
    script = Column(Text, nullable=False)
    visual_cues = Column(JSON, default=dict)
    
    # Metadata
    tags = Column(ARRAY(String(100)), default=[])
    estimated_engagement = Column(Float, default=0.0)
    brand_voice = Column(String(100), default="professional")
    target_audience = Column(ARRAY(String(100)), default=[])
    keywords = Column(ARRAY(String(100)), default=[])
    
    # Status
    status = Column(String(50), nullable=False, default="draft", index=True)
    safety_check_passed = Column(Boolean, default=False)
    
    # Temporal
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scheduled_for = Column(DateTime, index=True)
    
    # Relationships
    trend = relationship("Trend", back_populates="content_briefs")
    media_assets = relationship("MediaAsset", back_populates="brief")
    
    __table_args__ = (
        Index('ix_content_briefs_status_scheduled', 'status', 'scheduled_for'),
        Index('ix_content_briefs_trend_status', 'trend_id', 'status'),
    )


class MediaAsset(Base):
    """Generated media assets"""
    __tablename__ = "media_assets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    brief_id = Column(UUID(as_uuid=True), ForeignKey("content_briefs.id"), index=True)
    
    # Asset details
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    asset_type = Column(String(50), nullable=False)  # video, image, audio, etc.
    size = Column(BigInteger, nullable=False)  # bytes
    
    # Storage
    storage_path = Column(String(500), nullable=False)
    storage_provider = Column(String(50), default="s3")
    
    # Metadata
    duration = Column(Integer)  # seconds for video/audio
    dimensions = Column(JSON)   # {width: 1920, height: 1080}
    bitrate = Column(Integer)   # kbps
    format_details = Column(JSON, default=dict)
    
    # Status
    generation_status = Column(String(50), default="pending")
    quality_score = Column(Float, default=0.0)
    
    # Temporal
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uploaded_at = Column(DateTime)
    
    # Relationships
    brief = relationship("ContentBrief", back_populates="media_assets")
    publications = relationship("Publication", back_populates="asset")
    
    __table_args__ = (
        Index('ix_media_assets_brief_type', 'brief_id', 'asset_type'),
        Index('ix_media_assets_created_at', 'created_at'),
    )


class Publication(Base):
    """Content publications to platforms"""
    __tablename__ = "publications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # References
    asset_id = Column(UUID(as_uuid=True), ForeignKey("media_assets.id"), nullable=False, index=True)
    
    # Platform
    platform = Column(String(50), nullable=False, index=True)
    platform_content_id = Column(String(255), index=True)  # External ID on platform
    
    # Publication details
    url = Column(String(500))
    status = Column(String(50), nullable=False, default="scheduled", index=True)
    
    # Scheduling
    scheduled_for = Column(DateTime, index=True)
    published_at = Column(DateTime, index=True)
    
    # Metrics (updated after publication)
    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(BigInteger, default=0)
    shares = Column(BigInteger, default=0)
    
    # Metadata
    platform_metadata = Column(JSON, default=dict)
    error_message = Column(Text)
    
    # Temporal
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    asset = relationship("MediaAsset", back_populates="publications")
    engagements = relationship("Engagement", back_populates="publication")
    
    __table_args__ = (
        Index('ix_publications_platform_status', 'platform', 'status'),
        Index('ix_publications_scheduled_for', 'scheduled_for'),
        Index('ix_publications_published_at', 'published_at'),
    )


class Engagement(Base):
    """Audience engagement data"""
    __tablename__ = "engagements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    publication_id = Column(UUID(as_uuid=True), ForeignKey("publications.id"), nullable=False, index=True)
    
    # Engagement details
    engagement_type = Column(String(50), nullable=False, index=True)  # like, comment, share, view, etc.
    platform = Column(String(50), nullable=False, index=True)
    
    # User/audience
    user_id = Column(String(255), index=True)  # Platform user ID
    username = Column(String(255), index=True)
    
    # Content
    content = Column(Text)  # For comments
    sentiment_score = Column(Float)  # -1 to 1
    
    # Metadata
    metadata = Column(JSON, default=dict)
    is_processed = Column(Boolean, default=False, index=True)
    
    # Temporal
    engaged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime)
    
    # Relationships
    publication = relationship("Publication", back_populates="engagements")
    
    __table_args__ = (
        Index('ix_engagements_publication_type', 'publication_id', 'engagement_type'),
        Index('ix_engagements_platform_engaged', 'platform', 'engaged_at'),
    )


class AudienceProfile(Base):
    """Audience profile and demographics"""
    __tablename__ = "audience_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identity
    platform = Column(String(50), nullable=False, index=True)
    platform_user_id = Column(String(255), nullable=False, index=True)
    
    # Demographics
    username = Column(String(255), index=True)
    display_name = Column(String(255))
    bio = Column(Text)
    
    # Engagement stats
    total_engagements = Column(BigInteger, default=0)
    avg_sentiment = Column(Float, default=0.0)
    last_engaged_at = Column(DateTime, index=True)
    
    # Metadata
    demographics = Column(JSON, default=dict)  # age, gender, location, etc.
    interests = Column(ARRAY(String(100)), default=[])
    metadata = Column(JSON, default=dict)
    
    # Temporal
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_audience_profiles_platform_user', 'platform', 'platform_user_id', unique=True),
        Index('ix_audience_profiles_last_engaged', 'last_engaged_at'),
    )


class AgentRun(Base):
    """Agent execution history"""
    __tablename__ = "agent_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Agent info
    agent_type = Column(String(50), nullable=False, index=True)  # research, content, engagement
    agent_id = Column(String(255), nullable=False, index=True)
    
    # Execution
    status = Column(String(50), nullable=False, index=True)  # started, completed, failed
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    end_time = Column(DateTime, index=True)
    duration = Column(Float)  # seconds
    
    # Results
    trends_processed = Column(Integer, default=0)
    content_generated = Column(Integer, default=0)
    engagements_processed = Column(Integer, default=0)
    
    # Errors
    error_message = Column(Text)
    error_traceback = Column(Text)
    
    # Metadata
    input_parameters = Column(JSON, default=dict)
    output_summary = Column(JSON, default=dict)
    
    __table_args__ = (
        Index('ix_agent_runs_type_status', 'agent_type', 'status'),
        Index('ix_agent_runs_start_time', 'start_time'),
    )


class SystemMetric(Base):
    """System performance metrics"""
    __tablename__ = "system_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metric info
    metric_type = Column(String(100), nullable=False, index=True)  # cpu, memory, response_time, etc.
    source = Column(String(100), nullable=False, index=True)  # api, agent, skill, etc.
    
    # Values
    value = Column(Float, nullable=False)
    unit = Column(String(50))  # percent, ms, mb, etc.
    
    # Context
    labels = Column(JSON, default=dict)  # Additional labels
    metadata = Column(JSON, default=dict)
    
    # Temporal
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('ix_system_metrics_type_timestamp', 'metric_type', 'timestamp'),
        Index('ix_system_metrics_source_timestamp', 'source', 'timestamp'),
    )


class Configuration(Base):
    """System configuration storage"""
    __tablename__ = "configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Configuration key
    key = Column(String(255), nullable=False, unique=True, index=True)
    namespace = Column(String(100), nullable=False, default="default", index=True)
    
    # Values
    value = Column(JSON, nullable=False)
    value_type = Column(String(50), nullable=False)  # string, number, boolean, array, object
    
    # Metadata
    description = Column(Text)
    is_encrypted = Column(Boolean, default=False)
    is_secret = Column(Boolean, default=False, index=True)
    
    # Versioning
    version = Column(Integer, nullable=False, default=1)
    previous_version = Column(UUID(as_uuid=True), ForeignKey("configurations.id"))
    
    # Temporal
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    valid_from = Column(DateTime, default=datetime.utcnow, index=True)
    valid_to = Column(DateTime, index=True)
    
    # Relationships
    previous_config = relationship("Configuration", remote_side=[id])
    
    __table_args__ = (
        Index('ix_configurations_namespace_key', 'namespace', 'key'),
        Index('ix_configurations_validity', 'valid_from', 'valid_to'),
    )


# Export models
__all__ = [
    "Base",
    "generate_uuid",
    "Trend",
    "TrendMetric",
    "TrendCorrelation",
    "ContentBrief",
    "MediaAsset",
    "Publication",
    "Engagement",
    "AudienceProfile",
    "AgentRun",
    "SystemMetric",
    "Configuration"
]