"""
Trends API Endpoints

Handle trend discovery, analysis, and correlation endpoints.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import uuid

from ...core.dependencies import get_db, get_redis, get_settings, authenticate
from ...core.security import authorize
from .schemas.trend import TrendResponse, TrendAnalysisRequest
from agents.research_agent.agent import ResearchAgent, FetchTrendsRequest
from data.models.trend import Trend, TrendMetric
from utils.logging.structured_logger import get_logger

router = APIRouter()
logger = get_logger("api.trends")


class TrendFetchRequest(BaseModel):
    """Request model for fetching trends"""
    platforms: List[str] = Field(
        default=["youtube", "tiktok", "twitter"],
        description="Platforms to fetch trends from"
    )
    time_window: str = Field(
        default="24h",
        regex=r'^\d+[hd]$',
        description="Time window (1h, 4h, 24h, 7d)"
    )
    categories: Optional[List[str]] = Field(
        default=None,
        max_items=10,
        description="Optional categories to filter"
    )
    geo_target: Optional[str] = Field(
        default=None,
        regex=r'^[A-Z]{2}$',
        description="Two-letter country code"
    )
    max_results: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of trends to return"
    )


class TrendAnalysisResponse(BaseModel):
    """Response model for trend analysis"""
    analysis_id: str = Field(..., description="Unique analysis ID")
    trends_analyzed: int = Field(..., description="Number of trends analyzed")
    insights: Dict[str, Any] = Field(..., description="Analysis insights")
    recommendations: List[Dict[str, Any]] = Field(..., description="Content recommendations")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


@router.post("/fetch", response_model=List[TrendResponse])
async def fetch_trends(
    request: TrendFetchRequest,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(authenticate),
    db=Depends(get_db),
    redis=Depends(get_redis)
):
    """
    Fetch trends from specified platforms
    
    - **platforms**: List of platforms to fetch from
    - **time_window**: Time window for trends
    - **categories**: Optional category filters
    - **geo_target**: Optional geographic target
    - **max_results**: Maximum trends to return
    """
    # Check authorization
    if not authorize(auth, "trends:fetch"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    logger.info(
        "Fetching trends",
        user=auth.get("user_id"),
        platforms=request.platforms,
        time_window=request.time_window
    )
    
    try:
        # Initialize research agent
        agent = ResearchAgent(
            agent_id=f"api-agent-{uuid.uuid4().hex[:8]}",
            config={
                "default_categories": request.categories,
                "geo_target": request.geo_target
            }
        )
        
        # Create fetch request
        fetch_request = FetchTrendsRequest(
            platforms=request.platforms,
            time_window=request.time_window,
            categories=request.categories,
            geo_target=request.geo_target
        )
        
        # Fetch trends (async)
        trends = await agent.fetch_trends(fetch_request)
        
        # Limit results
        limited_trends = trends[:request.max_results]
        
        # Store in database (async)
        background_tasks.add_task(_store_trends, limited_trends, db)
        
        # Cache in Redis
        background_tasks.add_task(_cache_trends, limited_trends, redis, request)
        
        # Convert to response models
        response_trends = []
        for trend in limited_trends:
            response_trend = TrendResponse(
                id=str(trend.id),
                external_id=trend.external_id,
                platform=trend.platform,
                title=trend.title,
                description=trend.description,
                engagement_score=trend.engagement_score,
                discovered_at=trend.discovered_at,
                expires_at=trend.expires_at,
                metadata=trend.raw_metadata,
                metrics=TrendMetric(
                    virality_score=trend.metrics.virality_score if trend.metrics else 0,
                    sentiment_score=trend.metrics.sentiment_score if trend.metrics else 0,
                    novelty_score=trend.metrics.novelty_score if trend.metrics else 0,
                    competition_score=trend.metrics.competition_score if trend.metrics else 0
                ) if trend.metrics else None,
                tags=trend.tags or [],
                correlations=trend.correlations or []
            )
            response_trends.append(response_trend)
        
        logger.info(
            "Trends fetched successfully",
            count=len(response_trends),
            platforms=request.platforms
        )
        
        return response_trends
        
    except Exception as e:
        logger.error(
            "Trend fetch failed",
            error=str(e),
            platforms=request.platforms
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=TrendAnalysisResponse)
async def analyze_trends(
    request: TrendAnalysisRequest,
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """
    Analyze trends for content creation potential
    
    - **trend_ids**: List of trend IDs to analyze
    - **analysis_depth**: Depth of analysis (quick, standard, deep)
    - **content_focus**: Optional content focus area
    """
    if not authorize(auth, "trends:analyze"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    logger.info(
        "Analyzing trends",
        user=auth.get("user_id"),
        trend_count=len(request.trend_ids),
        depth=request.analysis_depth
    )
    
    try:
        # Fetch trends from database
        trends = []
        for trend_id in request.trend_ids:
            trend = db.query(Trend).filter(Trend.id == trend_id).first()
            if trend:
                trends.append(trend)
        
        if not trends:
            raise HTTPException(status_code=404, detail="No trends found")
        
        # Initialize research agent
        agent = ResearchAgent(
            agent_id=f"analysis-{uuid.uuid4().hex[:8]}",
            config={
                "analysis_depth": request.analysis_depth,
                "content_focus": request.content_focus
            }
        )
        
        # Generate report
        report = await agent.generate_report(trends)
        
        # Create response
        response = TrendAnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            trends_analyzed=len(trends),
            insights=report.get("insights", {}),
            recommendations=report.get("recommendations", [])
        )
        
        logger.info(
            "Trend analysis completed",
            analysis_id=response.analysis_id,
            trends_analyzed=len(trends)
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Trend analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trend_id}", response_model=TrendResponse)
async def get_trend(
    trend_id: str,
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Get specific trend by ID"""
    if not authorize(auth, "trends:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    
    return TrendResponse.from_orm(trend)


@router.get("/", response_model=List[TrendResponse])
async def list_trends(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_score: Optional[float] = Query(0.0, ge=0.0, le=1.0, description="Minimum engagement score"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """List trends with filtering"""
    if not authorize(auth, "trends:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = db.query(Trend)
    
    # Apply filters
    if platform:
        query = query.filter(Trend.platform == platform)
    
    if category:
        query = query.filter(Trend.raw_metadata["category"].astext == category)
    
    if min_score > 0:
        query = query.filter(Trend.engagement_score >= min_score)
    
    # Order by discovery time (newest first)
    query = query.order_by(Trend.discovered_at.desc())
    
    # Paginate
    trends = query.offset(offset).limit(limit).all()
    
    return [TrendResponse.from_orm(trend) for trend in trends]


@router.get("/platforms/{platform}/correlations")
async def get_platform_correlations(
    platform: str,
    time_window: str = Query("24h", regex=r'^\d+[hd]$'),
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Get correlations for trends on a specific platform"""
    if not authorize(auth, "trends:correlations"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    logger.info(
        "Fetching platform correlations",
        platform=platform,
        time_window=time_window
    )
    
    try:
        # Calculate time cutoff
        if time_window.endswith('h'):
            hours = int(time_window[:-1])
            cutoff = datetime.utcnow() - timedelta(hours=hours)
        else:
            days = int(time_window[:-1])
            cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Fetch recent trends for platform
        trends = db.query(Trend).filter(
            Trend.platform == platform,
            Trend.discovered_at >= cutoff
        ).all()
        
        if len(trends) < 2:
            return {"correlations": [], "message": "Insufficient data for correlation analysis"}
        
        # Initialize correlation detector
        from agents.research_agent.tools.correlation_detector import CorrelationDetector
        detector = CorrelationDetector(min_confidence=min_confidence)
        
        # Convert trends to dict format
        trend_dicts = []
        for trend in trends:
            trend_dict = {
                "id": str(trend.id),
                "title": trend.title,
                "description": trend.description,
                "platform": trend.platform,
                "engagement": {
                    "score": trend.engagement_score
                },
                "metadata": trend.raw_metadata,
                "timestamp": trend.discovered_at
            }
            trend_dicts.append(trend_dict)
        
        # Detect correlations
        correlations = detector.detect(trend_dicts)
        
        # Get correlation summary
        summary = detector.get_correlation_summary()
        
        logger.info(
            "Platform correlations analyzed",
            platform=platform,
            correlations_found=summary.get("total_correlations_detected", 0)
        )
        
        return {
            "platform": platform,
            "time_window": time_window,
            "trends_analyzed": len(trends),
            "correlations": correlations,
            "summary": summary
        }
        
    except Exception as e:
        logger.error("Correlation analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trends/batch")
async def create_trends_batch(
    trends: List[Dict[str, Any]],
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Create multiple trends in batch"""
    if not authorize(auth, "trends:write"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    created = 0
    errors = []
    
    for trend_data in trends:
        try:
            trend = Trend(**trend_data)
            db.add(trend)
            created += 1
        except Exception as e:
            errors.append({
                "data": trend_data,
                "error": str(e)
            })
    
    db.commit()
    
    return {
        "created": created,
        "errors": errors,
        "total": len(trends)
    }


@router.delete("/{trend_id}")
async def delete_trend(
    trend_id: str,
    auth: dict = Depends(authenticate),
    db=Depends(get_db)
):
    """Delete a trend"""
    if not authorize(auth, "trends:delete"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    
    db.delete(trend)
    db.commit()
    
    return {"message": "Trend deleted successfully"}


# Background task functions
async def _store_trends(trends: List[Trend], db):
    """Store trends in database (background task)"""
    try:
        for trend in trends:
            # Check if trend already exists
            existing = db.query(Trend).filter(
                Trend.external_id == trend.external_id,
                Trend.platform == trend.platform
            ).first()
            
            if not existing:
                db.add(trend)
        
        db.commit()
        logger.info("Trends stored in database", count=len(trends))
    except Exception as e:
        logger.error("Failed to store trends in database", error=str(e))
        db.rollback()


async def _cache_trends(trends: List[Trend], redis, request: TrendFetchRequest):
    """Cache trends in Redis (background task)"""
    try:
        cache_key = f"trends:{hash(str(request.dict()))}"
        
        # Convert trends to dict for caching
        trend_dicts = []
        for trend in trends:
            trend_dict = {
                "id": str(trend.id),
                "external_id": trend.external_id,
                "platform": trend.platform,
                "title": trend.title,
                "description": trend.description,
                "engagement_score": trend.engagement_score,
                "discovered_at": trend.discovered_at.isoformat(),
                "metadata": trend.raw_metadata
            }
            trend_dicts.append(trend_dict)
        
        # Cache for 1 hour
        redis.setex(cache_key, 3600, str(trend_dicts))
        logger.info("Trends cached in Redis", key=cache_key, count=len(trends))
    except Exception as e:
        logger.error("Failed to cache trends in Redis", error=str(e))