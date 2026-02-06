"""
Engagement API Endpoints

Handle audience interaction, analytics, and optimization.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
import uuid

from ...core.dependencies import get_db, get_redis, get_settings, authenticate
from ...core.security import authorize
from data.models.engagement import Audience, Interaction, Campaign
from utils.logging.structured_logger import get_logger

router = APIRouter()
logger = get_logger("api.engagement")


class InteractionResponse(BaseModel):
    """Response model for interaction"""
    id: str
    content_id: str
    platform: str
    interaction_type: str
    sentiment: Optional[float]
    metadata: Dict[str, Any]
    created_at: datetime


class CampaignRequest(BaseModel):
    """Request model for creating campaign"""
    name: str = Field(..., min_length=1, max_length=200)
    content_ids: List[str] = Field(..., min_items=1)
    platforms: List[str] = Field(..., min_items=1)
    schedule_start: datetime = Field(..., description="Campaign start time")
    schedule_end: Optional[datetime] = Field(None, description="Campaign end time")
    budget: Optional[float] = Field(None, ge=0, description="Campaign budget")
    objectives: List[str] = Field(default=["engagement"], description="Campaign objectives")


class AudienceAnalysisRequest(BaseModel):
    """Request model for audience analysis"""
    time_window: str = Field(default="7d", regex=r'^\d+[hd]$')
    platform: Optional[str] = Field(None, description="Filter by platform")
    content_type: Optional[str] = Field(None, description="Filter by content type")


@router.get("/interactions", response_model=List[InteractionResponse])
async def list_interactions(
    content_id: Optional[str] = Query(None, description="Filter by content ID"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    interaction_type: Optional[str] = Query(None, description="Filter by type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """List audience interactions with filtering"""
    if not authorize(auth, "engagement:interactions:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = db.query(Interaction)
    
    if content_id:
        query = query.filter(Interaction.content_id == content_id)
    
    if platform:
        query = query.filter(Interaction.platform == platform)
    
    if interaction_type:
        query = query.filter(Interaction.interaction_type == interaction_type)
    
    if start_date:
        query = query.filter(Interaction.created_at >= start_date)
    
    if end_date:
        query = query.filter(Interaction.created_at <= end_date)
    
    query = query.order_by(Interaction.created_at.desc())
    interactions = query.offset(offset).limit(limit).all()
    
    return [InteractionResponse.from_orm(interaction) for interaction in interactions]


@router.post("/interactions", response_model=InteractionResponse)
async def create_interaction(
    content_id: str = Query(..., description="Content ID"),
    platform: str = Query(..., description="Platform"),
    interaction_type: str = Query(..., description="Type of interaction"),
    sentiment: Optional[float] = Query(None, ge=-1, le=1, description="Sentiment score"),
    metadata: Dict[str, Any] = Query(default={}, description="Additional metadata"),
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Create a new interaction record"""
    if not authorize(auth, "engagement:interactions:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    logger.info(
        "Creating interaction",
        user=auth.get("user_id"),
        content_id=content_id,
        platform=platform,
        type=interaction_type
    )
    
    try:
        interaction = Interaction(
            content_id=content_id,
            platform=platform,
            interaction_type=interaction_type,
            sentiment=sentiment,
            metadata=metadata
        )
        
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        
        logger.info("Interaction created", interaction_id=str(interaction.id))
        
        return InteractionResponse.from_orm(interaction)
        
    except Exception as e:
        logger.error("Failed to create interaction", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns", response_model=Dict[str, Any])
async def create_campaign(
    request: CampaignRequest,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Create a new engagement campaign"""
    if not authorize(auth, "engagement:campaigns:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    logger.info(
        "Creating campaign",
        user=auth.get("user_id"),
        name=request.name,
        content_count=len(request.content_ids)
    )
    
    try:
        campaign = Campaign(
            name=request.name,
            content_ids=request.content_ids,
            platforms=request.platforms,
            schedule_start=request.schedule_start,
            schedule_end=request.schedule_end,
            budget=request.budget,
            objectives=request.objectives,
            status="planned"
        )
        
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        
        # Start campaign monitoring in background
        background_tasks.add_task(_monitor_campaign, campaign.id, db)
        
        logger.info("Campaign created", campaign_id=str(campaign.id))
        
        return {
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "status": campaign.status,
            "monitoring_url": f"/api/v1/engagement/campaigns/{campaign.id}/status"
        }
        
    except Exception as e:
        logger.error("Failed to create campaign", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/audience", response_model=Dict[str, Any])
async def analyze_audience(
    request: AudienceAnalysisRequest,
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Analyze audience behavior and preferences"""
    if not authorize(auth, "engagement:analyze"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    logger.info(
        "Analyzing audience",
        user=auth.get("user_id"),
        time_window=request.time_window,
        platform=request.platform
    )
    
    try:
        # Calculate time cutoff
        if request.time_window.endswith('h'):
            hours = int(request.time_window[:-1])
            cutoff = datetime.utcnow() - timedelta(hours=hours)
        else:
            days = int(request.time_window[:-1])
            cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Build query
        query = db.query(Interaction).filter(Interaction.created_at >= cutoff)
        
        if request.platform:
            query = query.filter(Interaction.platform == request.platform)
        
        interactions = query.all()
        
        if not interactions:
            return {
                "message": "No interaction data found for the specified period",
                "time_window": request.time_window,
                "interaction_count": 0
            }
        
        # Analyze interactions
        analysis = self._analyze_interactions(interactions)
        
        # Get audience demographics (if available)
        demographics = self._get_audience_demographics(interactions, db)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(analysis, demographics)
        
        logger.info(
            "Audience analysis completed",
            interaction_count=len(interactions),
            platform=request.platform or "all"
        )
        
        return {
            "time_window": request.time_window,
            "interaction_count": len(interactions),
            "analysis": analysis,
            "demographics": demographics,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Audience analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}/status")
async def get_campaign_status(
    campaign_id: str,
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Get campaign status and metrics"""
    if not authorize(auth, "engagement:campaigns:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Calculate campaign metrics
    metrics = self._calculate_campaign_metrics(campaign, db)
    
    return {
        "campaign_id": str(campaign.id),
        "name": campaign.name,
        "status": campaign.status,
        "metrics": metrics,
        "schedule": {
            "start": campaign.schedule_start,
            "end": campaign.schedule_end,
            "current_time": datetime.utcnow()
        }
    }


@router.get("/metrics/summary")
async def get_engagement_metrics(
    time_window: str = Query("24h", regex=r'^\d+[hd]$'),
    platform: Optional[str] = Query(None),
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Get engagement metrics summary"""
    if not authorize(auth, "engagement:metrics:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Calculate time cutoff
    if time_window.endswith('h'):
        hours = int(time_window[:-1])
        cutoff = datetime.utcnow() - timedelta(hours=hours)
    else:
        days = int(time_window[:-1])
        cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(Interaction).filter(Interaction.created_at >= cutoff)
    
    if platform:
        query = query.filter(Interaction.platform == platform)
    
    interactions = query.all()
    
    # Calculate metrics
    total_interactions = len(interactions)
    
    # Group by type
    by_type = {}
    for interaction in interactions:
        interaction_type = interaction.interaction_type
        by_type[interaction_type] = by_type.get(interaction_type, 0) + 1
    
    # Calculate sentiment
    sentiments = [i.sentiment for i in interactions if i.sentiment is not None]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
    
    # Platform distribution
    platform_dist = {}
    for interaction in interactions:
        platform = interaction.platform
        platform_dist[platform] = platform_dist.get(platform, 0) + 1
    
    return {
        "time_window": time_window,
        "total_interactions": total_interactions,
        "interactions_by_type": by_type,
        "average_sentiment": avg_sentiment,
        "platform_distribution": platform_dist,
        "period_start": cutoff,
        "period_end": datetime.utcnow()
    }


# Analysis methods
def _analyze_interactions(self, interactions: List[Interaction]) -> Dict[str, Any]:
    """Analyze interaction patterns"""
    analysis = {
        "peak_times": self._find_peak_times(interactions),
        "popular_content": self._find_popular_content(interactions),
        "engagement_patterns": self._analyze_engagement_patterns(interactions),
        "sentiment_trends": self._analyze_sentiment_trends(interactions)
    }
    
    return analysis


def _find_peak_times(self, interactions: List[Interaction]) -> Dict[str, Any]:
    """Find peak engagement times"""
    if not interactions:
        return {}
    
    # Group by hour
    hourly_counts = {}
    for interaction in interactions:
        hour = interaction.created_at.hour
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    
    # Find peaks
    if hourly_counts:
        max_hour = max(hourly_counts.items(), key=lambda x: x[1])
        return {
            "peak_hour": max_hour[0],
            "peak_count": max_hour[1],
            "hourly_distribution": hourly_counts
        }
    
    return {}


def _find_popular_content(self, interactions: List[Interaction]) -> List[Dict[str, Any]]:
    """Find most popular content based on interactions"""
    content_counts = {}
    for interaction in interactions:
        content_id = interaction.content_id
        content_counts[content_id] = content_counts.get(content_id, 0) + 1
    
    # Sort by interaction count
    sorted_content = sorted(content_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Return top 10
    return [
        {"content_id": content_id, "interaction_count": count}
        for content_id, count in sorted_content[:10]
    ]


def _analyze_engagement_patterns(self, interactions: List[Interaction]) -> Dict[str, Any]:
    """Analyze engagement patterns"""
    patterns = {
        "reply_rate": self._calculate_reply_rate(interactions),
        "share_rate": self._calculate_share_rate(interactions),
        "conversion_rate": self._calculate_conversion_rate(interactions)
    }
    
    return patterns


def _analyze_sentiment_trends(self, interactions: List[Interaction]) -> Dict[str, Any]:
    """Analyze sentiment trends over time"""
    sentiments = {}
    for interaction in interactions:
        if interaction.sentiment is not None:
            date = interaction.created_at.date()
            if date not in sentiments:
                sentiments[date] = []
            sentiments[date].append(interaction.sentiment)
    
    # Calculate daily averages
    daily_averages = {}
    for date, sentiment_list in sentiments.items():
        daily_averages[str(date)] = sum(sentiment_list) / len(sentiment_list)
    
    return {
        "daily_averages": daily_averages,
        "overall_average": sum(sum(v) for v in sentiments.values()) / 
                          sum(len(v) for v in sentiments.values()) if sentiments else 0
    }


def _get_audience_demographics(self, interactions: List[Interaction], db) -> Dict[str, Any]:
    """Get audience demographics from interactions"""
    # This would typically query audience database
    # For now, return placeholder
    return {
        "age_distribution": {"18-24": 0.35, "25-34": 0.40, "35-44": 0.15, "45+": 0.10},
        "gender_distribution": {"male": 0.55, "female": 0.45},
        "geographic_distribution": {"US": 0.40, "UK": 0.15, "Canada": 0.10, "Other": 0.35},
        "interests": ["technology", "education", "entertainment"]
    }


def _generate_recommendations(self, analysis: Dict[str, Any], demographics: Dict[str, Any]) -> List[str]:
    """Generate engagement recommendations"""
    recommendations = []
    
    # Time-based recommendations
    peak_time = analysis.get("peak_times", {}).get("peak_hour")
    if peak_time is not None:
        recommendations.append(
            f"Schedule content around {peak_time}:00 for maximum engagement"
        )
    
    # Content recommendations
    popular_content = analysis.get("popular_content", [])
    if popular_content:
        top_content = popular_content[0] if popular_content else {}
        recommendations.append(
            f"Create more content similar to {top_content.get('content_id', 'top-performing content')}"
        )
    
    # Audience-specific recommendations
    if demographics.get("interests"):
        top_interest = demographics["interests"][0] if demographics["interests"] else "general"
        recommendations.append(
            f"Focus on {top_interest}-related content to match audience interests"
        )
    
    return recommendations[:5]  # Return top 5 recommendations


def _calculate_campaign_metrics(self, campaign: Campaign, db) -> Dict[str, Any]:
    """Calculate campaign metrics"""
    # Get interactions for campaign content
    interactions = []
    for content_id in campaign.content_ids:
        content_interactions = db.query(Interaction).filter(
            Interaction.content_id == content_id,
            Interaction.created_at >= campaign.schedule_start
        ).all()
        interactions.extend(content_interactions)
    
    total_interactions = len(interactions)
    
    # Calculate engagement rate
    # This would be more sophisticated in production
    engagement_rate = min(total_interactions / max(len(campaign.content_ids), 1) / 100, 1.0)
    
    # Calculate ROI if budget is set
    roi = None
    if campaign.budget and campaign.budget > 0:
        # Simplified ROI calculation
        estimated_value = total_interactions * 0.1  # $0.10 per interaction
        roi = (estimated_value - campaign.budget) / campaign.budget
    
    return {
        "total_interactions": total_interactions,
        "engagement_rate": engagement_rate,
        "roi": roi,
        "content_count": len(campaign.content_ids),
        "interaction_types": self._group_interactions_by_type(interactions)
    }


def _group_interactions_by_type(self, interactions: List[Interaction]) -> Dict[str, int]:
    """Group interactions by type"""
    by_type = {}
    for interaction in interactions:
        interaction_type = interaction.interaction_type
        by_type[interaction_type] = by_type.get(interaction_type, 0) + 1
    
    return by_type


def _calculate_reply_rate(self, interactions: List[Interaction]) -> float:
    """Calculate reply rate"""
    replies = [i for i in interactions if i.interaction_type == "reply"]
    return len(replies) / len(interactions) if interactions else 0


def _calculate_share_rate(self, interactions: List[Interaction]) -> float:
    """Calculate share rate"""
    shares = [i for i in interactions if i.interaction_type == "share"]
    return len(shares) / len(interactions) if interactions else 0


def _calculate_conversion_rate(self, interactions: List[Interaction]) -> float:
    """Calculate conversion rate"""
    conversions = [i for i in interactions if i.interaction_type == "conversion"]
    return len(conversions) / len(interactions) if interactions else 0


# Background task function
async def _monitor_campaign(campaign_id: str, db):
    """Monitor campaign performance (background task)"""
    import time
    
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return
        
        # Update campaign status
        campaign.status = "active"
        db.commit()
        
        logger.info("Campaign monitoring started", campaign_id=campaign_id)
        
        # Simulate monitoring for 1 minute (in production, this would run continuously)
        for _ in range(60):
            time.sleep(1)
            
            # Check if campaign has ended
            if campaign.schedule_end and datetime.utcnow() > campaign.schedule_end:
                campaign.status = "completed"
                db.commit()
                logger.info("Campaign completed", campaign_id=campaign_id)
                break
        
        # If not completed, mark as completed
        if campaign.status != "completed":
            campaign.status = "completed"
            db.commit()
            logger.info("Campaign monitoring ended", campaign_id=campaign_id)
            
    except Exception as e:
        logger.error("Campaign monitoring failed", error=str(e), campaign_id=campaign_id)