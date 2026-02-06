"""
Trend API Schemas

Pydantic models for trend-related API requests and responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class TrendCategory(str, Enum):
    """Trend categories"""
    TECHNOLOGY = "technology"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    NEWS = "news"
    LIFESTYLE = "lifestyle"
    SPORTS = "sports"
    POLITICS = "politics"
    BUSINESS = "business"
    HEALTH = "health"
    OTHER = "other"


class TrendPlatform(str, Enum):
    """Social media platforms"""
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    REDDIT = "reddit"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"


class TrendMetric(BaseModel):
    """Metrics for trend analysis"""
    virality_score: float = Field(..., ge=0.0, le=100.0, description="Virality score 0-100")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score -1 to 1")
    novelty_score: float = Field(..., ge=0.0, le=100.0, description="Novelty score 0-100")
    competition_score: float = Field(..., ge=0.0, le=100.0, description="Competition score 0-100")
    estimated_reach: Optional[int] = Field(None, ge=0, description="Estimated reach")
    
    class Config:
        schema_extra = {
            "example": {
                "virality_score": 85.5,
                "sentiment_score": 0.75,
                "novelty_score": 65.0,
                "competition_score": 42.0,
                "estimated_reach": 100000
            }
        }


class Correlation(BaseModel):
    """Correlation between trends"""
    trend_id: str = Field(..., description="Correlated trend ID")
    correlation_type: str = Field(..., description="Type of correlation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Correlation confidence")
    evidence: List[Dict[str, Any]] = Field(default=[], description="Evidence for correlation")
    
    class Config:
        schema_extra = {
            "example": {
                "trend_id": "trend_456",
                "correlation_type": "direct",
                "confidence": 0.85,
                "evidence": [
                    {
                        "type": "keyword_overlap",
                        "description": "70% keyword similarity",
                        "strength": 0.7
                    }
                ]
            }
        }


class TrendResponse(BaseModel):
    """Response model for trend data"""
    id: str = Field(..., description="Unique trend ID")
    external_id: str = Field(..., description="External platform ID")
    platform: TrendPlatform = Field(..., description="Source platform")
    title: str = Field(..., min_length=1, max_length=500, description="Trend title")
    description: Optional[str] = Field(None, description="Trend description")
    engagement_score: float = Field(..., ge=0.0, le=1.0, description="Engagement score")
    discovered_at: datetime = Field(..., description="When trend was discovered")
    expires_at: Optional[datetime] = Field(None, description="When trend expires")
    category: Optional[TrendCategory] = Field(None, description="Trend category")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")
    metrics: Optional[TrendMetric] = Field(None, description="Analysis metrics")
    tags: List[str] = Field(default=[], description="Trend tags")
    correlations: List[Correlation] = Field(default=[], description="Correlated trends")
    
    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "trend_123",
                "external_id": "yt_video_abc123",
                "platform": "youtube",
                "title": "AI Revolution in 2024",
                "description": "Exploring the latest AI advancements...",
                "engagement_score": 0.85,
                "discovered_at": "2024-02-04T10:00:00Z",
                "expires_at": "2024-02-05T10:00:00Z",
                "category": "technology",
                "metadata": {
                    "views": 1000000,
                    "likes": 50000,
                    "comments": 2000
                },
                "metrics": {
                    "virality_score": 85.5,
                    "sentiment_score": 0.75,
                    "novelty_score": 65.0,
                    "competition_score": 42.0,
                    "estimated_reach": 100000
                },
                "tags": ["ai", "technology", "future"],
                "correlations": [
                    {
                        "trend_id": "trend_456",
                        "correlation_type": "direct",
                        "confidence": 0.85,
                        "evidence": []
                    }
                ]
            }
        }


class TrendAnalysisRequest(BaseModel):
    """Request model for trend analysis"""
    trend_ids: List[str] = Field(..., min_items=1, description="Trend IDs to analyze")
    analysis_depth: str = Field(
        default="standard",
        description="Depth of analysis",
        regex="^(quick|standard|deep)$"
    )
    content_focus: Optional[str] = Field(
        None,
        description="Optional content focus area"
    )
    include_correlations: bool = Field(
        default=True,
        description="Include correlation analysis"
    )
    include_recommendations: bool = Field(
        default=True,
        description="Include content recommendations"
    )
    
    @validator('trend_ids')
    def validate_trend_ids(cls, v):
        """Validate trend IDs"""
        if len(v) > 100:
            raise ValueError("Maximum 100 trends per analysis")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "trend_ids": ["trend_123", "trend_456"],
                "analysis_depth": "deep",
                "content_focus": "educational",
                "include_correlations": True,
                "include_recommendations": True
            }
        }


class TrendUpdateRequest(BaseModel):
    """Request model for updating trend"""
    engagement_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    category: Optional[TrendCategory] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "engagement_score": 0.9,
                "category": "technology",
                "tags": ["ai", "machine learning"],
                "metadata": {"verified": True}
            }
        }


class TrendSearchRequest(BaseModel):
    """Request model for searching trends"""
    query: Optional[str] = Field(None, description="Search query")
    platforms: Optional[List[TrendPlatform]] = Field(None, description="Filter by platform")
    categories: Optional[List[TrendCategory]] = Field(None, description="Filter by category")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum engagement score")
    max_score: float = Field(1.0, ge=0.0, le=1.0, description="Maximum engagement score")
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    
    class Config:
        schema_extra = {
            "example": {
                "query": "artificial intelligence",
                "platforms": ["youtube", "twitter"],
                "categories": ["technology"],
                "min_score": 0.5,
                "max_score": 1.0,
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-02-04T23:59:59Z",
                "limit": 50,
                "offset": 0
            }
        }


class TrendBatchResponse(BaseModel):
    """Response model for batch operations"""
    created: int = Field(..., description="Number of trends created")
    updated: int = Field(..., description="Number of trends updated")
    failed: int = Field(..., description="Number of failed operations")
    errors: List[Dict[str, Any]] = Field(default=[], description="Error details")
    
    class Config:
        schema_extra = {
            "example": {
                "created": 95,
                "updated": 5,
                "failed": 2,
                "errors": [
                    {"index": 0, "error": "Invalid platform"},
                    {"index": 42, "error": "Missing required field"}
                ]
            }
        }