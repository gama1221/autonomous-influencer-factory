"""
Content Models with Business Logic

Extended content models with business logic and methods.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from sqlalchemy import event
from sqlalchemy.orm import Session, relationship

from . import Base, ContentBrief as BaseContentBrief, MediaAsset as BaseMediaAsset, Publication as BasePublication
from utils.logging.structured_logger import get_logger

logger = get_logger("models.content")


class ContentStatus(str, Enum):
    """Content status enumeration"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    GENERATING = "generating"
    GENERATED = "generated"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


class ContentType(str, Enum):
    """Content type enumeration"""
    VIDEO = "video"
    ARTICLE = "article"
    POST = "post"
    STORY = "story"
    REEL = "reel"
    TWEET = "tweet"
    THREAD = "thread"
    CAROUSEL = "carousel"


class ContentBrief(BaseContentBrief):
    """
    Extended ContentBrief model with business logic.
    """
    
    __mapper_args__ = {
        'polymorphic_identity': 'content_brief'
    }
    
    @property
    def age_days(self) -> float:
        """Get brief age in days"""
        if not self.created_at:
            return 0.0
        age = datetime.utcnow() - self.created_at
        return age.days + age.seconds / 86400
    
    @property
    def is_stale(self) -> bool:
        """Check if brief is stale (older than 7 days)"""
        return self.age_days > 7
    
    @property
    def is_scheduled(self) -> bool:
        """Check if brief is scheduled for publication"""
        return self.scheduled_for is not None and self.scheduled_for > datetime.utcnow()
    
    @property
    def is_overdue(self) -> bool:
        """Check if scheduled publication is overdue"""
        if not self.scheduled_for:
            return False
        return self.scheduled_for < datetime.utcnow() and self.status != ContentStatus.PUBLISHED.value
    
    @classmethod
    def find_by_status(cls, session: Session, status: str, limit: int = 100) -> List['ContentBrief']:
        """
        Find briefs by status.
        
        Args:
            session: Database session
            status: Brief status
            limit: Maximum results
            
        Returns:
            List of briefs
        """
        return session.query(cls).filter(
            cls.status == status
        ).order_by(
            cls.created_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def find_scheduled_briefs(cls, session: Session, hours_ahead: int = 24) -> List['ContentBrief']:
        """
        Find briefs scheduled for publication in the next N hours.
        
        Args:
            session: Database session
            hours_ahead: Hours to look ahead
            
        Returns:
            List of scheduled briefs
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)
        
        return session.query(cls).filter(
            cls.scheduled_for.between(now, cutoff),
            cls.status.in_([ContentStatus.APPROVED.value, ContentStatus.GENERATED.value])
        ).order_by(
            cls.scheduled_for.asc()
        ).all()
    
    def update_status(self, new_status: ContentStatus, reason: str = None) -> None:
        """
        Update brief status with logging.
        
        Args:
            new_status: New status
            reason: Reason for status change
        """
        old_status = self.status
        self.status = new_status.value
        self.updated_at = datetime.utcnow()
        
        logger.info(
            "Content brief status updated",
            brief_id=str(self.id),
            old_status=old_status,
            new_status=new_status.value,
            reason=reason
        )
    
    def schedule_publication(self, publish_time: datetime) -> None:
        """
        Schedule brief for publication.
        
        Args:
            publish_time: When to publish
        """
        self.scheduled_for = publish_time
        self.updated_at = datetime.utcnow()
        
        logger.info(
            "Content brief scheduled",
            brief_id=str(self.id),
            scheduled_for=publish_time.isoformat()
        )
    
    def generate_metadata(self) -> Dict[str, Any]:
        """
        Generate metadata for content generation.
        
        Returns:
            Content generation metadata
        """
        metadata = {
            'brief_id': str(self.id),
            'trend_id': self.trend_id,
            'target_platform': self.target_platform,
            'content_type': self.content_type,
            'title': self.title,
            'estimated_engagement': self.estimated_engagement,
            'brand_voice': self.brand_voice,
            'target_audience': self.target_audience,
            'keywords': self.keywords,
            'tags': self.tags,
            'generation_parameters': {
                'style': self.brand_voice,
                'tone': 'professional',
                'length': 'medium',
                'complexity': 'intermediate'
            }
        }
        
        # Add platform-specific parameters
        if self.target_platform == 'youtube':
            metadata['platform_specific'] = {
                'video_format': 'mp4',
                'resolution': '1080p',
                'aspect_ratio': '16:9',
                'max_duration': 600  # 10 minutes
            }
        elif self.target_platform == 'tiktok':
            metadata['platform_specific'] = {
                'video_format': 'mp4',
                'resolution': '1080x1920',
                'aspect_ratio': '9:16',
                'max_duration': 60  # 1 minute
            }
        
        return metadata
    
    def validate_for_generation(self) -> Dict[str, Any]:
        """
        Validate brief for content generation.
        
        Returns:
            Validation result
        """
        issues = []
        warnings = []
        
        # Check status
        if self.status not in [ContentStatus.APPROVED.value, ContentStatus.DRAFT.value]:
            issues.append(f'Invalid status for generation: {self.status}')
        
        # Check required fields
        if not self.title or len(self.title.strip()) < 5:
            issues.append('Title is too short or missing')
        
        if not self.script or len(self.script.strip()) < 100:
            warnings.append('Script may be too short')
        
        if not self.target_platform:
            issues.append('Target platform not specified')
        
        if not self.content_type:
            issues.append('Content type not specified')
        
        # Check safety
        if not self.safety_check_passed:
            warnings.append('Safety check not passed')
        
        is_valid = len(issues) == 0
        
        return {
            'is_valid': is_valid,
            'issues': issues,
            'warnings': warnings,
            'can_generate': is_valid and self.status == ContentStatus.APPROVED.value
        }
    
    def to_dict(self, include_assets: bool = False) -> Dict[str, Any]:
        """
        Convert brief to dictionary.
        
        Args:
            include_assets: Whether to include media assets
            
        Returns:
            Brief as dictionary
        """
        data = {
            'id': str(self.id),
            'trend_id': self.trend_id,
            'target_platform': self.target_platform,
            'content_type': self.content_type,
            'title': self.title,
            'status': self.status,
            'estimated_engagement': self.estimated_engagement,
            'brand_voice': self.brand_voice,
            'safety_check_passed': self.safety_check_passed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'age_days': self.age_days,
            'is_stale': self.is_stale,
            'is_scheduled': self.is_scheduled,
            'is_overdue': self.is_overdue
        }
        
        if include_assets and self.media_assets:
            data['media_assets'] = [
                asset.to_dict() for asset in self.media_assets
            ]
        
        return data


class MediaAsset(BaseMediaAsset):
    """
    Extended MediaAsset model with business logic.
    """
    
    __mapper_args__ = {
        'polymorphic_identity': 'media_asset'
    }
    
    @property
    def size_mb(self) -> float:
        """Get file size in MB"""
        return self.size / 1048576
    
    @property
    def is_video(self) -> bool:
        """Check if asset is video"""
        return self.asset_type == 'video' or self.content_type.startswith('video/')
    
    @property
    def is_image(self) -> bool:
        """Check if asset is image"""
        return self.asset_type == 'image' or self.content_type.startswith('image/')
    
    @property
    def is_audio(self) -> bool:
        """Check if asset is audio"""
        return self.asset_type == 'audio' or self.content_type.startswith('audio/')
    
    @classmethod
    def find_by_brief(cls, session: Session, brief_id: str, asset_type: str = None) -> List['MediaAsset']:
        """
        Find assets by brief ID.
        
        Args:
            session: Database session
            brief_id: Brief ID
            asset_type: Optional asset type filter
            
        Returns:
            List of assets
        """
        query = session.query(cls).filter(
            cls.brief_id == brief_id
        )
        
        if asset_type:
            query = query.filter(cls.asset_type == asset_type)
        
        return query.order_by(cls.created_at.desc()).all()
    
    def update_generation_status(self, status: str, quality_score: float = None) -> None:
        """
        Update generation status.
        
        Args:
            status: New generation status
            quality_score: Optional quality score
        """
        self.generation_status = status
        if quality_score is not None:
            self.quality_score = quality_score
        
        if status == 'completed':
            self.uploaded_at = datetime.utcnow()
        
        logger.debug(
            "Media asset status updated",
            asset_id=str(self.id),
            status=status,
            quality_score=quality_score
        )
    
    def validate_format(self) -> Dict[str, Any]:
        """
        Validate asset format and specifications.
        
        Returns:
            Validation result
        """
        issues = []
        warnings = []
        
        # Check file size
        max_size = 1073741824  # 1GB
        if self.size > max_size:
            issues.append(f'File size too large: {self.size_mb:.2f}MB > {max_size/1048576:.0f}MB')
        
        # Check dimensions for images/videos
        if self.is_video or self.is_image:
            if not self.dimensions:
                warnings.append('Dimensions not specified')
            else:
                width = self.dimensions.get('width', 0)
                height = self.dimensions.get('height', 0)
                
                if self.is_video and width < 1280:
                    warnings.append('Video width below HD standard')
                
                if self.is_image and width < 800:
                    warnings.append('Image width below recommended minimum')
        
        # Check duration for videos
        if self.is_video and self.duration:
            if self.duration > 3600:  # 1 hour
                warnings.append('Video duration exceeds 1 hour')
            elif self.duration < 3:  # 3 seconds
                warnings.append('Video duration too short')
        
        # Check bitrate for videos
        if self.is_video and self.bitrate:
            if self.bitrate < 1000:  # 1 Mbps
                warnings.append('Video bitrate may be too low for quality')
        
        is_valid = len(issues) == 0
        
        return {
            'is_valid': is_valid,
            'issues': issues,
            'warnings': warnings,
            'specifications': {
                'size_mb': self.size_mb,
                'dimensions': self.dimensions,
                'duration': self.duration,
                'bitrate': self.bitrate
            }
        }
    
    def get_download_url(self, expires_in: int = 3600) -> str:
        """
        Generate download URL (mock implementation).
        
        In production, this would generate a signed URL from cloud storage.
        
        Args:
            expires_in: URL expiration in seconds
            
        Returns:
            Download URL
        """
        # This is a mock implementation
        # In production, use: storage_client.generate_signed_url()
        base_url = "https://storage.chimera.example.com"
        return f"{base_url}/{self.storage_path}?expires={expires_in}"
    
    def to_dict(self, include_url: bool = False) -> Dict[str, Any]:
        """
        Convert asset to dictionary.
        
        Args:
            include_url: Whether to include download URL
            
        Returns:
            Asset as dictionary
        """
        data = {
            'id': str(self.id),
            'brief_id': str(self.brief_id) if self.brief_id else None,
            'filename': self.filename,
            'content_type': self.content_type,
            'asset_type': self.asset_type,
            'size_mb': self.size_mb,
            'generation_status': self.generation_status,
            'quality_score': self.quality_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'is_video': self.is_video,
            'is_image': self.is_image,
            'is_audio': self.is_audio,
            'specifications': {
                'duration': self.duration,
                'dimensions': self.dimensions,
                'bitrate': self.bitrate,
                'format_details': self.format_details
            }
        }
        
        if include_url:
            data['download_url'] = self.get_download_url()
        
        return data


class Publication(BasePublication):
    """
    Extended Publication model with business logic.
    """
    
    __mapper_args__ = {
        'polymorphic_identity': 'publication'
    }
    
    @property
    def is_live(self) -> bool:
        """Check if publication is live"""
        return self.status == 'published' and self.published_at is not None
    
    @property
    def is_scheduled(self) -> bool:
        """Check if publication is scheduled"""
        return self.status == 'scheduled' and self.scheduled_for is not None
    
    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate"""
        if self.views == 0:
            return 0.0
        total_engagement = self.likes + self.comments + self.shares
        return total_engagement / self.views
    
    @property
    def performance_score(self) -> float:
        """Calculate performance score"""
        if not self.is_live:
            return 0.0
        
        # Base score from engagement rate
        score = min(self.engagement_rate * 1000, 50)  # Max 50 from engagement
        
        # Add score for each engagement type
        score += min(self.likes / 1000, 10)  # Max 10 from likes
        score += min(self.comments / 100, 20)  # Max 20 from comments
        score += min(self.shares / 100, 20)  # Max 20 from shares
        
        return min(score, 100)
    
    @classmethod
    def find_by_platform(cls, session: Session, platform: str, status: str = None, limit: int = 100) -> List['Publication']:
        """
        Find publications by platform.
        
        Args:
            session: Database session
            platform: Platform name
            status: Optional status filter
            limit: Maximum results
            
        Returns:
            List of publications
        """
        query = session.query(cls).filter(
            cls.platform == platform
        )
        
        if status:
            query = query.filter(cls.status == status)
        
        return query.order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def find_scheduled_publications(cls, session: Session, hours_ahead: int = 24) -> List['Publication']:
        """
        Find publications scheduled in the next N hours.
        
        Args:
            session: Database session
            hours_ahead: Hours to look ahead
            
        Returns:
            List of scheduled publications
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)
        
        return session.query(cls).filter(
            cls.scheduled_for.between(now, cutoff),
            cls.status == 'scheduled'
        ).order_by(cls.scheduled_for.asc()).all()
    
    def publish(self, platform_content_id: str = None, url: str = None) -> None:
        """
        Mark publication as published.
        
        Args:
            platform_content_id: External platform ID
            url: Published content URL
        """
        self.status = 'published'
        self.published_at = datetime.utcnow()
        
        if platform_content_id:
            self.platform_content_id = platform_content_id
        
        if url:
            self.url = url
        
        self.updated_at = datetime.utcnow()
        
        logger.info(
            "Publication marked as published",
            publication_id=str(self.id),
            platform=self.platform,
            platform_content_id=platform_content_id
        )
    
    def fail(self, error_message: str) -> None:
        """
        Mark publication as failed.
        
        Args:
            error_message: Error description
        """
        self.status = 'failed'
        self.error_message = error_message
        self.updated_at = datetime.utcnow()
        
        logger.error(
            "Publication failed",
            publication_id=str(self.id),
            platform=self.platform,
            error_message=error_message
        )
    
    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Update publication metrics.
        
        Args:
            metrics: Dictionary of metrics
        """
        if 'views' in metrics:
            self.views = metrics['views']
        
        if 'likes' in metrics:
            self.likes = metrics['likes']
        
        if 'comments' in metrics:
            self.comments = metrics['comments']
        
        if 'shares' in metrics:
            self.shares = metrics['shares']
        
        if 'platform_metadata' in metrics:
            self.platform_metadata.update(metrics['platform_metadata'])
        
        self.updated_at = datetime.utcnow()
        
        logger.debug(
            "Publication metrics updated",
            publication_id=str(self.id),
            views=self.views,
            likes=self.likes,
            engagement_rate=self.engagement_rate
        )
    
    def get_analytics(self) -> Dict[str, Any]:
        """
        Get publication analytics.
        
        Returns:
            Analytics data
        """
        return {
            'publication_id': str(self.id),
            'platform': self.platform,
            'status': self.status,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'metrics': {
                'views': self.views,
                'likes': self.likes,
                'comments': self.comments,
                'shares': self.shares,
                'engagement_rate': self.engagement_rate,
                'performance_score': self.performance_score
            },
            'url': self.url,
            'platform_content_id': self.platform_content_id,
            'age_hours': self._get_age_hours()
        }
    
    def _get_age_hours(self) -> float:
        """Get publication age in hours"""
        if not self.published_at:
            return 0.0
        
        age = datetime.utcnow() - self.published_at
        return age.total_seconds() / 3600
    
    def to_dict(self, include_engagements: bool = False) -> Dict[str, Any]:
        """
        Convert publication to dictionary.
        
        Args:
            include_engagements: Whether to include engagement data
            
        Returns:
            Publication as dictionary
        """
        data = {
            'id': str(self.id),
            'asset_id': str(self.asset_id),
            'platform': self.platform,
            'status': self.status,
            'url': self.url,
            'platform_content_id': self.platform_content_id,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'views': self.views,
            'likes': self.likes,
            'comments': self.comments,
            'shares': self.shares,
            'engagement_rate': self.engagement_rate,
            'performance_score': self.performance_score,
            'is_live': self.is_live,
            'is_scheduled': self.is_scheduled,
            'error_message': self.error_message
        }
        
        if include_engagements and self.engagements:
            data['recent_engagements'] = [
                {
                    'type': engagement.engagement_type,
                    'content': engagement.content[:100] if engagement.content else None,
                    'engaged_at': engagement.engaged_at.isoformat()
                }
                for engagement in self.engagements[:10]  # Limit to 10
            ]
        
        return data


# Event listeners
@event.listens_for(ContentBrief, 'before_insert')
def before_brief_insert(mapper, connection, target):
    """Before insert hook for ContentBrief"""
    if not target.created_at:
        target.created_at = datetime.utcnow()
    
    if not target.updated_at:
        target.updated_at = datetime.utcnow()
    
    # Set default estimated engagement
    if target.estimated_engagement is None:
        target.estimated_engagement = 0.5
    
    logger.debug(
        "Content brief before insert",
        brief_id=str(target.id),
        target_platform=target.target_platform,
        status=target.status
    )


@event.listens_for(MediaAsset, 'before_insert')
def before_asset_insert(mapper, connection, target):
    """Before insert hook for MediaAsset"""
    if not target.created_at:
        target.created_at = datetime.utcnow()
    
    # Set default storage provider
    if not target.storage_provider:
        target.storage_provider = 's3'
    
    logger.debug(
        "Media asset before insert",
        asset_id=str(target.id),
        asset_type=target.asset_type,
        size=target.size
    )


@event.listens_for(Publication, 'before_insert')
def before_publication_insert(mapper, connection, target):
    """Before insert hook for Publication"""
    if not target.created_at:
        target.created_at = datetime.utcnow()
    
    if not target.updated_at:
        target.updated_at = datetime.utcnow()
    
    # Set default status
    if not target.status:
        target.status = 'scheduled'
    
    logger.debug(
        "Publication before insert",
        publication_id=str(target.id),
        platform=target.platform,
        status=target.status
    )


# Export
__all__ = [
    'ContentStatus',
    'ContentType',
    'ContentBrief',
    'MediaAsset',
    'Publication'
]