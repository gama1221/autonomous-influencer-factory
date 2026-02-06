"""
Research Agent - Discovers and analyzes trends across platforms
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import structlog
from pydantic import BaseModel, Field, validator
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base_agent import BaseAgent
from .tools.trend_analyzer import TrendAnalyzer, TrendAnalysisResult
from .tools.correlation_detector import CorrelationDetector
from utils.logging.structured_logger import get_logger
from utils.telemetry.tracer import tracer
from data.models.trend import Trend, TrendMetric


class AgentState(Enum):
    """Research Agent state machine"""
    IDLE = "idle"
    FETCHING = "fetching_trends"
    ANALYZING = "analyzing_trends"
    CORRELATING = "detecting_correlations"
    REPORTING = "generating_report"
    ERROR = "error"


@dataclass
class PlatformConfig:
    """Configuration for platform trend fetching"""
    name: str
    enabled: bool = True
    rate_limit: int = 100  # requests per hour
    time_window: str = "24h"
    categories: List[str] = None
    priority: int = 1


class FetchTrendsRequest(BaseModel):
    """Request model for fetching trends"""
    platforms: List[str] = Field(
        default=["youtube", "tiktok", "twitter"],
        description="Platforms to fetch trends from"
    )
    time_window: str = Field(
        default="24h",
        regex=r'^\d+[hd]$',
        description="Time window (e.g., 1h, 4h, 24h, 7d)"
    )
    categories: Optional[List[str]] = Field(
        default=None,
        max_items=10,
        description="Optional categories to filter trends"
    )
    geo_target: Optional[str] = Field(
        default=None,
        regex=r'^[A-Z]{2}$',
        description="Two-letter country code"
    )
    
    @validator('time_window')
    def validate_time_window(cls, v):
        """Validate time window format"""
        if not v.endswith(('h', 'd')):
            raise ValueError('Time window must end with h or d')
        return v


class ResearchAgent(BaseAgent):
    """
    Autonomous agent for trend research and analysis
    """
    
    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any] = None,
        skills_registry: Any = None
    ):
        super().__init__(agent_id, "research", config)
        self.logger = get_logger(f"agent.research.{agent_id}")
        self.state = AgentState.IDLE
        self.skills = skills_registry
        self.trend_analyzer = TrendAnalyzer()
        self.correlation_detector = CorrelationDetector()
        self.platform_configs = self._init_platform_configs()
        
        # Statistics
        self.stats = {
            "trends_fetched": 0,
            "correlations_found": 0,
            "platform_errors": 0,
            "avg_processing_time": 0.0
        }
        
        self.logger.info(
            "Research agent initialized",
            agent_id=agent_id,
            platforms=len(self.platform_configs)
        )
    
    def _init_platform_configs(self) -> Dict[str, PlatformConfig]:
        """Initialize platform configurations"""
        return {
            "youtube": PlatformConfig(
                name="youtube",
                enabled=self.config.get("youtube_enabled", True),
                rate_limit=self.config.get("youtube_rate_limit", 100),
                categories=["technology", "entertainment", "education"]
            ),
            "tiktok": PlatformConfig(
                name="tiktok",
                enabled=self.config.get("tiktok_enabled", True),
                rate_limit=self.config.get("tiktok_rate_limit", 80),
                categories=["comedy", "dance", "education"]
            ),
            "twitter": PlatformConfig(
                name="twitter",
                enabled=self.config.get("twitter_enabled", True),
                rate_limit=self.config.get("twitter_rate_limit", 300),
                categories=["technology", "politics", "sports"]
            ),
            "reddit": PlatformConfig(
                name="reddit",
                enabled=self.config.get("reddit_enabled", False),
                rate_limit=self.config.get("reddit_rate_limit", 60),
                categories=["all"]
            )
        }
    
    async def start(self) -> None:
        """Start the research agent"""
        self.logger.info("Starting research agent")
        self.state = AgentState.IDLE
        await self._run_research_cycle()
    
    async def stop(self) -> None:
        """Stop the research agent"""
        self.logger.info("Stopping research agent")
        self.state = AgentState.IDLE
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def fetch_trends(self, request: FetchTrendsRequest) -> List[Trend]:
        """
        Fetch trends from multiple platforms
        
        Args:
            request: FetchTrendsRequest with parameters
            
        Returns:
            List of Trend objects
        """
        with tracer.start_as_current_span("research.fetch_trends") as span:
            span.set_attribute("platforms", request.platforms)
            span.set_attribute("time_window", request.time_window)
            
            self.state = AgentState.FETCHING
            self.logger.info(
                "Fetching trends",
                platforms=request.platforms,
                time_window=request.time_window
            )
            
            all_trends = []
            
            # Fetch from each platform in parallel
            fetch_tasks = []
            for platform in request.platforms:
                if platform in self.platform_configs:
                    config = self.platform_configs[platform]
                    if config.enabled:
                        task = self._fetch_platform_trends(
                            platform, config, request
                        )
                        fetch_tasks.append(task)
            
            # Wait for all fetches to complete
            platform_results = await asyncio.gather(
                *fetch_tasks, return_exceptions=True
            )
            
            # Process results
            for platform, result in zip(request.platforms, platform_results):
                if isinstance(result, Exception):
                    self.logger.error(
                        "Platform fetch failed",
                        platform=platform,
                        error=str(result)
                    )
                    self.stats["platform_errors"] += 1
                    span.record_exception(result)
                elif result:
                    all_trends.extend(result)
                    self.logger.info(
                        "Platform trends fetched",
                        platform=platform,
                        count=len(result)
                    )
            
            self.stats["trends_fetched"] += len(all_trends)
            self.state = AgentState.ANALYZING
            
            # Analyze trends
            analyzed_trends = await self._analyze_trends(all_trends)
            
            # Detect correlations
            correlated_trends = await self._detect_correlations(analyzed_trends)
            
            span.set_attribute("trends.count", len(correlated_trends))
            return correlated_trends
    
    async def _fetch_platform_trends(
        self,
        platform: str,
        config: PlatformConfig,
        request: FetchTrendsRequest
    ) -> List[Trend]:
        """Fetch trends from a specific platform"""
        # Use skill if available, otherwise use direct implementation
        skill_name = f"skill_fetch_{platform}_trends"
        
        if self.skills and hasattr(self.skills, skill_name):
            skill = getattr(self.skills, skill_name)
            result = await skill.execute({
                "time_window": request.time_window,
                "categories": request.categories or config.categories,
                "geo_target": request.geo_target
            })
            
            trends = []
            for trend_data in result.get("trends", []):
                trend = Trend(
                    external_id=trend_data["id"],
                    platform=platform,
                    title=trend_data["title"],
                    description=trend_data.get("description"),
                    engagement_score=trend_data.get("engagement_score", 0.0),
                    discovered_at=datetime.utcnow(),
                    raw_metadata=trend_data.get("metadata", {})
                )
                trends.append(trend)
            
            return trends
        
        else:
            # Fallback to direct implementation
            self.logger.warning(
                "Skill not found, using fallback",
                skill=skill_name
            )
            # Implementation would go here
            return []
    
    async def _analyze_trends(self, trends: List[Trend]) -> List[Trend]:
        """Analyze trends for insights"""
        with tracer.start_as_current_span("research.analyze_trends"):
            self.logger.info(
                "Analyzing trends",
                count=len(trends)
            )
            
            analyzed_trends = []
            for trend in trends:
                analysis = self.trend_analyzer.analyze(trend)
                
                # Update trend with analysis
                trend.metrics = TrendMetric(
                    virality_score=analysis.virality_score,
                    sentiment_score=analysis.sentiment_score,
                    novelty_score=analysis.novelty_score,
                    competition_score=analysis.competition_score
                )
                
                trend.tags = analysis.recommended_tags
                trend.estimated_reach = analysis.estimated_reach
                
                analyzed_trends.append(trend)
            
            return analyzed_trends
    
    async def _detect_correlations(
        self,
        trends: List[Trend]
    ) -> List[Trend]:
        """Detect correlations between trends"""
        with tracer.start_as_current_span("research.detect_correlations"):
            self.state = AgentState.CORRELATING
            
            correlations = self.correlation_detector.detect(trends)
            
            # Update trends with correlation data
            for trend in trends:
                trend.correlations = correlations.get(trend.id, [])
            
            self.stats["correlations_found"] += len(correlations)
            self.state = AgentState.REPORTING
            
            return trends
    
    async def generate_report(self, trends: List[Trend]) -> Dict[str, Any]:
        """Generate research report"""
        with tracer.start_as_current_span("research.generate_report"):
            self.logger.info(
                "Generating research report",
                trends=len(trends)
            )
            
            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "summary": {
                    "total_trends": len(trends),
                    "platforms_analyzed": list(set(t.platform for t in trends)),
                    "time_range": f"Last {self.config.get('time_window', '24h')}"
                },
                "top_trends": sorted(
                    trends,
                    key=lambda x: x.metrics.virality_score if x.metrics else 0,
                    reverse=True
                )[:10],
                "insights": self._extract_insights(trends),
                "recommendations": self._generate_recommendations(trends),
                "agent_stats": self.stats.copy()
            }
            
            # Reset for next cycle
            self.state = AgentState.IDLE
            
            return report
    
    def _extract_insights(self, trends: List[Trend]) -> List[Dict[str, Any]]:
        """Extract insights from trends"""
        insights = []
        
        # Platform comparison
        platform_stats = {}
        for trend in trends:
            platform = trend.platform
            if platform not in platform_stats:
                platform_stats[platform] = {
                    "count": 0,
                    "avg_engagement": 0.0,
                    "top_category": ""
                }
            platform_stats[platform]["count"] += 1
        
        if platform_stats:
            insights.append({
                "type": "platform_distribution",
                "title": "Platform Activity Distribution",
                "data": platform_stats
            })
        
        # Category trends
        category_counts = {}
        for trend in trends:
            if hasattr(trend, 'category') and trend.category:
                category_counts[trend.category] = \
                    category_counts.get(trend.category, 0) + 1
        
        if category_counts:
            top_category = max(category_counts.items(), key=lambda x: x[1])
            insights.append({
                "type": "category_analysis",
                "title": f"Top Category: {top_category[0]}",
                "data": {"top_category": top_category}
            })
        
        return insights
    
    def _generate_recommendations(
        self,
        trends: List[Trend]
    ) -> List[Dict[str, Any]]:
        """Generate content recommendations"""
        recommendations = []
        
        # Top viral trends for content creation
        viral_trends = sorted(
            [t for t in trends if t.metrics and t.metrics.virality_score > 0.7],
            key=lambda x: x.metrics.virality_score,
            reverse=True
        )[:5]
        
        if viral_trends:
            recommendations.append({
                "type": "content_creation",
                "priority": "high",
                "trends": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "platform": t.platform,
                        "virality_score": t.metrics.virality_score,
                        "suggested_angle": self._suggest_content_angle(t)
                    }
                    for t in viral_trends
                ]
            })
        
        # Platform-specific recommendations
        platform_recommendations = {}
        for trend in trends:
            platform = trend.platform
            if platform not in platform_recommendations:
                platform_recommendations[platform] = []
            platform_recommendations[platform].append(trend)
        
        for platform, platform_trends in platform_recommendations.items():
            if len(platform_trends) >= 3:  # Minimum for platform-specific insight
                recommendations.append({
                    "type": "platform_optimization",
                    "platform": platform,
                    "suggestions": self._platform_specific_suggestions(
                        platform, platform_trends
                    )
                })
        
        return recommendations
    
    def _suggest_content_angle(self, trend: Trend) -> str:
        """Suggest content angle for a trend"""
        angles = [
            "Explainer video",
            "Trend analysis",
            "How-to guide",
            "Reaction video",
            "Deep dive analysis",
            "Comparison with related trends"
        ]
        
        # Simple heuristic based on trend characteristics
        if hasattr(trend, 'category'):
            if trend.category == "technology":
                return "Technical breakdown and future implications"
            elif trend.category == "entertainment":
                return "Reaction and commentary"
        
        return angles[hash(trend.id) % len(angles)]
    
    def _platform_specific_suggestions(
        self,
        platform: str,
        trends: List[Trend]
    ) -> List[str]:
        """Generate platform-specific suggestions"""
        suggestions = []
        
        if platform == "youtube":
            avg_duration = 600  # 10 minutes
            suggestions.append(
                f"Create {avg_duration//60}:{avg_duration%60:02d} "
                f"minute explainer videos"
            )
            suggestions.append("Use YouTube Shorts for quick trend coverage")
        
        elif platform == "tiktok":
            suggestions.append("Focus on 15-60 second engaging clips")
            suggestions.append("Use trending sounds and effects")
        
        elif platform == "twitter":
            suggestions.append("Thread format for detailed analysis")
            suggestions.append("Use relevant hashtags and @mentions")
        
        return suggestions
    
    async def _run_research_cycle(self) -> None:
        """Main research cycle"""
        while self.state != AgentState.ERROR:
            try:
                # Fetch configuration
                time_window = self.config.get("research_interval", "4h")
                
                # Create request
                request = FetchTrendsRequest(
                    platforms=[
                        p for p, config in self.platform_configs.items()
                        if config.enabled
                    ],
                    time_window=time_window,
                    categories=self.config.get("default_categories"),
                    geo_target=self.config.get("geo_target")
                )
                
                # Fetch and analyze trends
                trends = await self.fetch_trends(request)
                
                # Generate report
                report = await self.generate_report(trends)
                
                # Publish report (to event bus or storage)
                await self._publish_report(report)
                
                # Wait for next cycle
                interval = self._parse_time_window(time_window)
                self.logger.info(
                    "Research cycle completed",
                    trends=len(trends),
                    next_run_in=f"{interval} seconds"
                )
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(
                    "Research cycle failed",
                    error=str(e),
                    exc_info=True
                )
                self.state = AgentState.ERROR
                # Exponential backoff on error
                await asyncio.sleep(60)
                self.state = AgentState.IDLE
    
    async def _publish_report(self, report: Dict[str, Any]) -> None:
        """Publish research report"""
        # Implementation would publish to event bus or storage
        self.logger.info(
            "Research report ready",
            report_id=report.get("timestamp"),
            trends=report["summary"]["total_trends"]
        )
    
    def _parse_time_window(self, time_window: str) -> int:
        """Parse time window string to seconds"""
        if time_window.endswith('h'):
            hours = int(time_window[:-1])
            return hours * 3600
        elif time_window.endswith('d'):
            days = int(time_window[:-1])
            return days * 86400
        return 14400  # Default 4 hours
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "agent_id": self.agent_id,
            "type": "research",
            "state": self.state.value,
            "stats": self.stats.copy(),
            "platforms": {
                name: {
                    "enabled": config.enabled,
                    "rate_limit": config.rate_limit
                }
                for name, config in self.platform_configs.items()
            },
            "last_updated": datetime.utcnow().isoformat()
        }