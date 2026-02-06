"""
Trend Model with Business Logic

Extended trend model with business logic and methods.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import event
from sqlalchemy.orm import Session

from . import Base, Trend as BaseTrend
from utils.logging.structured_logger import get_logger

logger = get_logger("models.trend")


class Trend(BaseTrend):
    """
    Extended Trend model with business logic.
    
    This class adds methods and properties to the base SQLAlchemy model.
    """
    
    __mapper_args__ = {
        'polymorphic_identity': 'trend'
    }
    
    @property
    def age_hours(self) -> float:
        """Get trend age in hours"""
        if not self.discovered_at:
            return 0.0
        age = datetime.utcnow() - self.discovered_at
        return age.total_seconds() / 3600
    
    @property
    def is_expired(self) -> bool:
        """Check if trend is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_fresh(self) -> bool:
        """Check if trend is fresh (less than 24 hours old)"""
        return self.age_hours < 24
    
    @property
    def is_viral(self) -> bool:
        """Check if trend is viral"""
        return self.virality_score >= 70.0
    
    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate"""
        if self.views == 0:
            return 0.0
        total_engagement = self.likes + self.comments + self.shares
        return total_engagement / self.views
    
    @classmethod
    def find_by_external_id(cls, session: Session, external_id: str, platform: str) -> Optional['Trend']:
        """
        Find trend by external ID and platform.
        
        Args:
            session: Database session
            external_id: External platform ID
            platform: Platform name
            
        Returns:
            Trend if found, None otherwise
        """
        return session.query(cls).filter(
            cls.external_id == external_id,
            cls.platform == platform
        ).first()
    
    @classmethod
    def find_viral_trends(cls, session: Session, hours: int = 24, limit: int = 100) -> List['Trend']:
        """
        Find viral trends from the last N hours.
        
        Args:
            session: Database session
            hours: Lookback window in hours
            limit: Maximum results
            
        Returns:
            List of viral trends
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        return session.query(cls).filter(
            cls.discovered_at >= cutoff,
            cls.virality_score >= 70.0
        ).order_by(
            cls.virality_score.desc()
        ).limit(limit).all()
    
    @classmethod
    def find_trends_by_category(cls, session: Session, category: str, limit: int = 50) -> List['Trend']:
        """
        Find trends by category.
        
        Args:
            session: Database session
            category: Trend category
            limit: Maximum results
            
        Returns:
            List of trends in category
        """
        return session.query(cls).filter(
            cls.category == category,
            cls.expires_at > datetime.utcnow()
        ).order_by(
            cls.virality_score.desc()
        ).limit(limit).all()
    
    def update_metrics(self, new_metrics: Dict[str, Any]) -> None:
        """
        Update trend metrics.
        
        Args:
            new_metrics: Dictionary of new metrics
        """
        # Update engagement metrics
        if 'engagement_score' in new_metrics:
            self.engagement_score = new_metrics['engagement_score']
        
        if 'views' in new_metrics:
            self.views = new_metrics['views']
        
        if 'likes' in new_metrics:
            self.likes = new_metrics['likes']
        
        if 'comments' in new_metrics:
            self.comments = new_metrics['comments']
        
        if 'shares' in new_metrics:
            self.shares = new_metrics['shares']
        
        # Update analysis scores
        if 'virality_score' in new_metrics:
            self.virality_score = new_metrics['virality_score']
        
        if 'sentiment_score' in new_metrics:
            self.sentiment_score = new_metrics['sentiment_score']
        
        if 'novelty_score' in new_metrics:
            self.novelty_score = new_metrics['novelty_score']
        
        if 'competition_score' in new_metrics:
            self.competition_score = new_metrics['competition_score']
        
        # Update metadata
        if 'metadata' in new_metrics:
            self.metadata.update(new_metrics['metadata'])
        
        if 'tags' in new_metrics:
            self.tags = list(set(self.tags + new_metrics['tags']))
        
        # Update timestamp
        self.last_updated = datetime.utcnow()
        
        logger.debug(
            "Trend metrics updated",
            trend_id=str(self.id),
            platform=self.platform,
            engagement_score=self.engagement_score
        )
    
    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """
        Convert trend to dictionary.
        
        Args:
            include_relationships: Whether to include related objects
            
        Returns:
            Trend as dictionary
        """
        data = {
            'id': str(self.id),
            'external_id': self.external_id,
            'platform': self.platform,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'engagement_score': self.engagement_score,
            'views': self.views,
            'likes': self.likes,
            'comments': self.comments,
            'shares': self.shares,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'virality_score': self.virality_score,
            'sentiment_score': self.sentiment_score,
            'novelty_score': self.novelty_score,
            'competition_score': self.competition_score,
            'tags': self.tags,
            'metadata': self.metadata,
            'age_hours': self.age_hours,
            'is_expired': self.is_expired,
            'is_fresh': self.is_fresh,
            'is_viral': self.is_viral,
            'engagement_rate': self.engagement_rate
        }
        
        if include_relationships and self.content_briefs:
            data['content_briefs'] = [
                {
                    'id': str(brief.id),
                    'status': brief.status,
                    'created_at': brief.created_at.isoformat()
                }
                for brief in self.content_briefs[:5]  # Limit to 5
            ]
        
        return data
    
    def get_content_suggestions(self) -> List[Dict[str, Any]]:
        """
        Generate content suggestions based on trend analysis.
        
        Returns:
            List of content suggestions
        """
        suggestions = []
        
        # Basic suggestion based on platform
        if self.platform == 'youtube':
            suggestions.append({
                'type': 'video',
                'format': 'explainer',
                'duration': '8-12 minutes',
                'title_template': f"The Truth About {self.title}",
                'description_template': f"In this video, we explore {self.title} and what it means for...",
                'tags': self.tags + ['explainer', 'tutorial']
            })
        
        elif self.platform == 'tiktok':
            suggestions.append({
                'type': 'short_video',
                'format': 'quick_take',
                'duration': '15-60 seconds',
                'title_template': f"Quick take on {self.title}",
                'description_template': f"#shorts #{self.category}",
                'tags': self.tags + ['shorts', 'quicktake']
            })
        
        elif self.platform == 'twitter':
            suggestions.append({
                'type': 'thread',
                'format': 'analysis',
                'tweet_count': '5-10 tweets',
                'title_template': f"🧵 Thread: {self.title}",
                'description_template': f"A deep dive into {self.title}...",
                'tags': self.tags + ['thread', 'analysis']
            })
        
        # Add suggestion based on sentiment
        if self.sentiment_score > 0.5:
            suggestions.append({
                'type': 'positive_angle',
                'description': f"Positive spin on {self.title}",
                'angle': 'focus on benefits and opportunities'
            })
        elif self.sentiment_score < -0.5:
            suggestions.append({
                'type': 'critical_angle',
                'description': f"Critical analysis of {self.title}",
                'angle': 'address concerns and provide solutions'
            })
        
        # Add suggestion based on virality
        if self.is_viral:
            suggestions.append({
                'type': 'viral_opportunity',
                'description': 'Capitalize on viral trend',
                'urgency': 'high',
                'action': 'Create content within 24 hours'
            })
        
        return suggestions
    
    def estimate_reach(self, content_quality: str = 'standard') -> Dict[str, Any]:
        """
        Estimate potential reach for content based on this trend.
        
        Args:
            content_quality: Content quality level
            
        Returns:
            Reach estimation
        """
        base_reach = self.views * 0.01  # 1% of trend viewers
        
        # Adjust based on content quality
        quality_multipliers = {
            'low': 0.5,
            'standard': 1.0,
            'high': 1.5,
            'premium': 2.0
        }
        
        multiplier = quality_multipliers.get(content_quality, 1.0)
        estimated_reach = int(base_reach * multiplier)
        
        # Adjust based on trend age
        if self.age_hours > 48:
            estimated_reach *= 0.5  # 50% reduction for older trends
        
        # Adjust based on virality
        if self.is_viral:
            estimated_reach *= 1.5
        
        return {
            'estimated_reach': estimated_reach,
            'confidence': min(0.9, self.engagement_score),
            'factors': {
                'trend_views': self.views,
                'content_quality': content_quality,
                'trend_age_hours': self.age_hours,
                'is_viral': self.is_viral
            }
        }
    
    def validate_for_content(self) -> Dict[str, Any]:
        """
        Validate trend for content creation.
        
        Returns:
            Validation result
        """
        issues = []
        warnings = []
        
        # Check expiration
        if self.is_expired:
            issues.append('Trend has expired')
        
        # Check engagement
        if self.engagement_score < 0.3:
            issues.append('Low engagement score')
        elif self.engagement_score < 0.6:
            warnings.append('Moderate engagement score')
        
        # Check virality
        if self.virality_score < 50.0:
            warnings.append('Low virality potential')
        
        # Check sentiment
        if self.sentiment_score < -0.7:
            issues.append('Highly negative sentiment')
        elif self.sentiment_score < -0.3:
            warnings.append('Negative sentiment')
        
        # Check data completeness
        if not self.title or len(self.title.strip()) < 5:
            issues.append('Incomplete title')
        
        if not self.description or len(self.description.strip()) < 20:
            warnings.append('Incomplete description')
        
        is_valid = len(issues) == 0
        
        return {
            'is_valid': is_valid,
            'issues': issues,
            'warnings': warnings,
            'score': self._calculate_validation_score(issues, warnings)
        }
    
    def _calculate_validation_score(self, issues: List[str], warnings: List[str]) -> float:
        """Calculate validation score"""
        base_score = 100.0
        
        # Deduct for issues
        base_score -= len(issues) * 20
        
        # Deduct for warnings
        base_score -= len(warnings) * 5
        
        return max(0.0, base_score)
    
    def __repr__(self):
        return f"<Trend(id={self.id}, platform='{self.platform}', title='{self.title[:30]}...', score={self.engagement_score:.2f})>"


# Event listeners
@event.listens_for(Trend, 'before_insert')
def before_trend_insert(mapper, connection, target):
    """Before insert hook for Trend"""
    if not target.discovered_at:
        target.discovered_at = datetime.utcnow()
    
    if not target.last_updated:
        target.last_updated = datetime.utcnow()
    
    # Set default expiration (72 hours from discovery)
    if not target.expires_at:
        target.expires_at = target.discovered_at + timedelta(hours=72)
    
    logger.debug(
        "Trend before insert",
        trend_id=str(target.id),
        platform=target.platform,
        discovered_at=target.discovered_at
    )


@event.listens_for(Trend, 'before_update')
def before_trend_update(mapper, connection, target):
    """Before update hook for Trend"""
    target.last_updated = datetime.utcnow()
    
    logger.debug(
        "Trend before update",
        trend_id=str(target.id),
        platform=target.platform,
        last_updated=target.last_updated
    )


# Export
__all__ = ['Trend']