"""
Content API Schemas

Pydantic models for content-related API requests and responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class ContentType(str, Enum):
    """Content types"""
    VIDEO = "video"
    ARTICLE = "article"
    POST = "post"
    STORY = "story"
    REEL = "reel"
    TWEET = "tweet"
    THREAD = "thread"


class ContentStatus(str, Enum):
    """Content status"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    GENERATING = "generating"
    GENERATED = "generated"
    PUBLISHED = "published"
    FAILED = "failed"


class BrandVoice(str, Enum):
    """Brand voice options"""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    EDUCATIONAL = "educational"
    ENTERTAINING = "entertaining"
    INSPIRATIONAL = "inspirational"
    AUTHORITATIVE = "authoritative"


class ContentBriefRequest(BaseModel):
    """Request model for content brief creation"""
    trend_id: str = Field(..., description="Source trend ID")
    target_platform: str = Field(..., description="Target platform")
    content_type: ContentType = Field(..., description="Type of content")
    target_duration: Optional[int] = Field(None, ge=1, description="Target duration in seconds")
    brand_voice: BrandVoice = Field(default=BrandVoice.PROFESSIONAL, description="Brand voice")
    additional_notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    target_audience: Optional[List[str]] = Field(None, description="Target audience segments")
    keywords: Optional[List[str]] = Field(None, description="SEO keywords")
    
    @validator('target_duration')
    def validate_duration(cls, v):
        """Validate duration based on content type"""
        if v:
            if v > 3600:  # 1 hour
                raise ValueError("Duration cannot exceed 1 hour")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "trend_id": "trend_123",
                "target_platform": "youtube",
                "content_type": "video",
                "target_duration": 600,
                "brand_voice": "educational",
                "additional_notes": "Focus on practical applications",
                "target_audience": ["developers", "tech enthusiasts"],
                "keywords": ["ai", "machine learning", "tutorial"]
            }
        }


class ContentBriefResponse(BaseModel):
    """Response model for content brief"""
    id: str = Field(..., description="Brief ID")
    trend_id: str = Field(..., description="Source trend ID")
    target_platform: str = Field(..., description="Target platform")
    content_type: ContentType = Field(..., description="Content type")
    title: str = Field(..., min_length=1, max_length=200, description="Content title")
    script: str = Field(..., min_length=1, description="Content script")
    visual_cues: Optional[Dict[str, Any]] = Field(None, description="Visual direction")
    tags: List[str] = Field(default=[], description="Content tags")
    estimated_engagement: float = Field(..., ge=0.0, le=1.0, description="Estimated engagement")
    status: ContentStatus = Field(..., description="Current status")
    brand_voice: BrandVoice = Field(..., description="Brand voice")
    additional_notes: Optional[str] = Field(None, description="Additional notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "brief_abc123",
                "trend_id": "trend_123",
                "target_platform": "youtube",
                "content_type": "video",
                "title": "AI Revolution: Practical Applications",
                "script": "In this video, we'll explore...",
                "visual_cues": {
                    "mood": "professional",
                    "color_palette": ["#1a1a2e", "#16213e"],
                    "visual_elements": ["charts", "animations"]
                },
                "tags": ["ai", "technology", "tutorial"],
                "estimated_engagement": 0.85,
                "status": "draft",
                "brand_voice": "educational",
                "additional_notes": "Focus on practical applications",
                "created_at": "2024-02-04T10:00:00Z",
                "updated_at": "2024-02-04T10:00:00Z"
            }
        }


class GenerateContentRequest(BaseModel):
    """Request model for content generation"""
    brief_id: str = Field(..., description="Content brief ID")
    quality: str = Field(
        default="standard",
        description="Quality level",
        regex="^(low|standard|high|premium)$"
    )
    use_ai: bool = Field(default=True, description="Use AI generation")
    human_review: bool = Field(default=True, description="Require human review")
    variants: int = Field(default=1, ge=1, le=5, description="Number of variants")
    custom_prompt: Optional[str] = Field(None, description="Custom generation prompt")
    
    class Config:
        schema_extra = {
            "example": {
                "brief_id": "brief_abc123",
                "quality": "high",
                "use_ai": True,
                "human_review": True,
                "variants": 2,
                "custom_prompt": "Make it more engaging for beginners"
            }
        }


class MediaAssetResponse(BaseModel):
    """Response model for media asset"""
    id: str = Field(..., description="Asset ID")
    brief_id: Optional[str] = Field(None, description="Associated brief ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    asset_type: str = Field(..., description="Asset type")
    size: int = Field(..., ge=0, description="File size in bytes")
    storage_path: str = Field(..., description="Storage path")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "asset_xyz789",
                "brief_id": "brief_abc123",
                "filename": "ai_video.mp4",
                "content_type": "video/mp4",
                "asset_type": "video",
                "size": 10485760,
                "storage_path": "uploads/ai_video_123.mp4",
                "created_at": "2024-02-04T10:00:00Z"
            }
        }


class ContentGenerationStatus(BaseModel):
    """Content generation status"""
    brief_id: str = Field(..., description="Brief ID")
    status: ContentStatus = Field(..., description="Current status")
    progress: float = Field(..., ge=0.0, le=1.0, description="Generation progress")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion")
    assets_generated: List[MediaAssetResponse] = Field(default=[], description="Generated assets")
    errors: List[str] = Field(default=[], description="Generation errors")
    
    class Config:
        schema_extra = {
            "example": {
                "brief_id": "brief_abc123",
                "status": "generating",
                "progress": 0.65,
                "estimated_completion": "2024-02-04T10:05:00Z",
                "assets_generated": [],
                "errors": []
            }
        }


class PublishContentRequest(BaseModel):
    """Request model for publishing content"""
    asset_ids: List[str] = Field(..., min_items=1, description="Asset IDs to publish")
    platforms: List[str] = Field(..., min_items=1, description="Target platforms")
    schedule_time: Optional[datetime] = Field(None, description="Scheduled publish time")
    auto_schedule: bool = Field(default=True, description="Use optimal scheduling")
    cross_promote: bool = Field(default=True, description="Cross-promote across platforms")
    
    @validator('platforms')
    def validate_platforms(cls, v):
        """Validate platforms"""
        valid_platforms = ["youtube", "tiktok", "twitter", "instagram", "facebook", "linkedin"]
        for platform in v:
            if platform not in valid_platforms:
                raise ValueError(f"Invalid platform: {platform}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "asset_ids": ["asset_xyz789"],
                "platforms": ["youtube", "twitter"],
                "schedule_time": "2024-02-04T15:00:00Z",
                "auto_schedule": True,
                "cross_promote": True
            }
        }


class PublishedContentResponse(BaseModel):
    """Response model for published content"""
    publication_id: str = Field(..., description="Publication ID")
    asset_id: str = Field(..., description="Asset ID")
    platform: str = Field(..., description="Platform")
    status: str = Field(..., description="Publication status")
    url: Optional[str] = Field(None, description="Published content URL")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Publication metrics")
    
    class Config:
        schema_extra = {
            "example": {
                "publication_id": "pub_123456",
                "asset_id": "asset_xyz789",
                "platform": "youtube",
                "status": "published",
                "url": "https://youtube.com/watch?v=abc123",
                "published_at": "2024-02-04T15:00:00Z",
                "metrics": {
                    "views": 1000,
                    "likes": 50,
                    "comments": 10
                }
            }
        }


class ContentAnalyticsRequest(BaseModel):
    """Request model for content analytics"""
    content_ids: List[str] = Field(..., min_items=1, description="Content IDs to analyze")
    time_window: str = Field(
        default="7d",
        regex=r'^\d+[hd]$',
        description="Time window for analytics"
    )
    include_comparison: bool = Field(
        default=True,
        description="Include comparison with similar content"
    )
    
    @validator('content_ids')
    def validate_content_ids(cls, v):
        """Validate content IDs"""
        if len(v) > 50:
            raise ValueError("Maximum 50 content IDs per analysis")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "content_ids": ["content_123", "content_456"],
                "time_window": "7d",
                "include_comparison": True
            }
        }


class ContentAnalyticsResponse(BaseModel):
    """Response model for content analytics"""
    content_id: str = Field(..., description="Content ID")
    time_window: str = Field(..., description="Analysis time window")
    engagement_metrics: Dict[str, Any] = Field(..., description="Engagement metrics")
    audience_metrics: Dict[str, Any] = Field(..., description="Audience metrics")
    performance_score: float = Field(..., ge=0.0, le=100.0, description="Performance score")
    recommendations: List[str] = Field(default=[], description="Optimization recommendations")
    
    class Config:
        schema_extra = {
            "example": {
                "content_id": "content_123",
                "time_window": "7d",
                "engagement_metrics": {
                    "views": 10000,
                    "engagement_rate": 0.15,
                    "avg_watch_time": 180
                },
                "audience_metrics": {
                    "demographics": {
                        "age": {"18-24": 0.4, "25-34": 0.35},
                        "gender": {"male": 0.6, "female": 0.4}
                    },
                    "geography": {"US": 0.4, "UK": 0.2}
                },
                "performance_score": 85.5,
                "recommendations": [
                    "Optimize title for SEO",
                    "Add more visual elements",
                    "Publish during peak hours"
                ]
            }
        }