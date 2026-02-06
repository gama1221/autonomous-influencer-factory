"""
Trend Analyzer - Analyzes social media trends for virality and content potential
"""

import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
from scipy import stats
from textblob import TextBlob
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer

from utils.logging.structured_logger import get_logger

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('vader_lexicon', quiet=True)


class TrendCategory(Enum):
    """Categories for trend classification"""
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


@dataclass
class TrendAnalysisResult:
    """Results of trend analysis"""
    trend_id: str
    category: TrendCategory
    virality_score: float  # 0-100
    sentiment_score: float  # -1 to 1
    novelty_score: float  # 0-100
    competition_score: float  # 0-100
    estimated_reach: int
    recommended_tags: List[str]
    content_angles: List[str]
    risks: List[Dict[str, Any]]
    confidence: float


class TrendAnalyzer:
    """
    Advanced trend analyzer using NLP and statistical methods
    """
    
    def __init__(self):
        self.logger = get_logger("trend_analyzer")
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.trend_history = []
        self.category_keywords = self._load_category_keywords()
        
    def _load_category_keywords(self) -> Dict[TrendCategory, List[str]]:
        """Load category-specific keywords for classification"""
        return {
            TrendCategory.TECHNOLOGY: [
                'ai', 'artificial intelligence', 'machine learning', 'python',
                'programming', 'software', 'tech', 'innovation', 'startup',
                'coding', 'developer', 'algorithm', 'data science'
            ],
            TrendCategory.ENTERTAINMENT: [
                'movie', 'tv show', 'celebrity', 'music', 'concert',
                'netflix', 'youtube', 'tiktok', 'viral', 'meme',
                'entertainment', 'hollywood', 'streaming'
            ],
            TrendCategory.EDUCATION: [
                'learning', 'course', 'tutorial', 'education', 'school',
                'university', 'online course', 'skill', 'knowledge',
                'study', 'teaching', 'academic'
            ],
            TrendCategory.NEWS: [
                'breaking', 'news', 'update', 'latest', 'report',
                'headline', 'coverage', 'journalism', 'media',
                'current events', 'world news'
            ]
        }
    
    def analyze(self, trend_data: Dict[str, Any]) -> TrendAnalysisResult:
        """
        Analyze a trend for content creation potential
        
        Args:
            trend_data: Dictionary containing trend information
            
        Returns:
            TrendAnalysisResult with analysis scores
        """
        try:
            # Extract features
            features = self._extract_features(trend_data)
            
            # Calculate scores
            category = self._categorize_trend(features)
            virality_score = self._calculate_virality_score(features)
            sentiment_score = self._calculate_sentiment_score(features)
            novelty_score = self._calculate_novelty_score(features)
            competition_score = self._calculate_competition_score(features)
            estimated_reach = self._estimate_reach(features)
            
            # Generate recommendations
            recommended_tags = self._generate_tags(features, category)
            content_angles = self._suggest_content_angles(features, category)
            risks = self._identify_risks(features)
            
            # Calculate confidence
            confidence = self._calculate_confidence(features)
            
            result = TrendAnalysisResult(
                trend_id=trend_data.get('id', 'unknown'),
                category=category,
                virality_score=virality_score,
                sentiment_score=sentiment_score,
                novelty_score=novelty_score,
                competition_score=competition_score,
                estimated_reach=estimated_reach,
                recommended_tags=recommended_tags,
                content_angles=content_angles,
                risks=risks,
                confidence=confidence
            )
            
            # Store for historical analysis
            self.trend_history.append({
                'timestamp': datetime.utcnow(),
                'trend_id': result.trend_id,
                'virality_score': virality_score,
                'category': category.value
            })
            
            # Keep only last 1000 entries
            if len(self.trend_history) > 1000:
                self.trend_history = self.trend_history[-1000:]
            
            self.logger.info(
                "Trend analyzed",
                trend_id=result.trend_id,
                category=category.value,
                virality_score=virality_score,
                confidence=confidence
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Trend analysis failed",
                error=str(e),
                trend_data=trend_data.get('title', 'unknown')
            )
            raise
    
    def _extract_features(self, trend_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from trend data"""
        features = {
            'title': trend_data.get('title', ''),
            'description': trend_data.get('description', ''),
            'engagement': trend_data.get('engagement', {}),
            'metadata': trend_data.get('metadata', {}),
            'platform': trend_data.get('platform', 'unknown'),
            'timestamp': trend_data.get('timestamp') or datetime.utcnow()
        }
        
        # Calculate engagement velocity
        if 'engagement' in trend_data:
            engagement = trend_data['engagement']
            features['engagement_velocity'] = self._calculate_velocity(engagement)
        
        # Extract keywords
        text = f"{features['title']} {features['description']}"
        features['keywords'] = self._extract_keywords(text)
        
        # Calculate text complexity
        features['text_complexity'] = self._calculate_text_complexity(text)
        
        return features
    
    def _categorize_trend(self, features: Dict[str, Any]) -> TrendCategory:
        """Categorize trend based on content"""
        text = f"{features['title']} {features['description']}".lower()
        
        category_scores = {}
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            category_scores[category] = score
        
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])
            if best_category[1] > 0:
                return best_category[0]
        
        # Use NLP for classification if keyword matching fails
        return self._categorize_with_nlp(text)
    
    def _categorize_with_nlp(self, text: str) -> TrendCategory:
        """Use NLP to categorize trend when keywords don't match"""
        # Simple rule-based fallback
        tech_indicators = ['code', 'software', 'tech', 'ai', 'data']
        entertainment_indicators = ['funny', 'entertain', 'watch', 'show']
        
        text_lower = text.lower()
        
        if any(indicator in text_lower for indicator in tech_indicators):
            return TrendCategory.TECHNOLOGY
        elif any(indicator in text_lower for indicator in entertainment_indicators):
            return TrendCategory.ENTERTAINMENT
        else:
            return TrendCategory.OTHER
    
    def _calculate_virality_score(self, features: Dict[str, Any]) -> float:
        """Calculate virality score (0-100)"""
        score = 50.0  # Base score
        
        # Engagement factors
        engagement = features.get('engagement', {})
        if engagement:
            # Views factor
            views = engagement.get('views', 0)
            if views > 1000000:
                score += 20
            elif views > 100000:
                score += 15
            elif views > 10000:
                score += 10
            
            # Engagement rate factor
            likes = engagement.get('likes', 0)
            comments = engagement.get('comments', 0)
            shares = engagement.get('shares', 0)
            
            if views > 0:
                engagement_rate = (likes + comments * 2 + shares * 3) / views
                score += min(engagement_rate * 100, 20)
            
            # Velocity factor
            velocity = features.get('engagement_velocity', 0)
            score += min(velocity * 10, 15)
        
        # Text factors
        complexity = features.get('text_complexity', 0.5)
        # Moderate complexity is best for virality
        if 0.3 <= complexity <= 0.7:
            score += 10
        
        # Platform factor
        platform = features.get('platform', '').lower()
        platform_multipliers = {
            'tiktok': 1.2,
            'youtube': 1.1,
            'twitter': 1.0,
            'instagram': 1.05
        }
        score *= platform_multipliers.get(platform, 1.0)
        
        return min(max(score, 0), 100)
    
    def _calculate_sentiment_score(self, features: Dict[str, Any]) -> float:
        """Calculate sentiment score (-1 to 1)"""
        text = f"{features['title']} {features['description']}"
        
        # Use TextBlob for sentiment
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        # Use VADER for social media sentiment
        vader_scores = self.sentiment_analyzer.polarity_scores(text)
        vader_polarity = vader_scores['compound']
        
        # Average the two methods
        sentiment = (polarity + vader_polarity) / 2
        
        return float(sentiment)
    
    def _calculate_novelty_score(self, features: Dict[str, Any]) -> float:
        """Calculate novelty score based on historical trends"""
        if not self.trend_history:
            return 75.0  # Default if no history
        
        current_keywords = set(features.get('keywords', []))
        novelty_score = 100.0
        
        # Compare with recent trends
        recent_trends = self.trend_history[-100:]  # Last 100 trends
        
        for trend in recent_trends:
            # Calculate keyword overlap
            # (In practice, we'd store keywords with each trend)
            # For now, use a simplified approach
            novelty_score -= 0.1
        
        # Time-based novelty decay
        hours_old = (datetime.utcnow() - features['timestamp']).total_seconds() / 3600
        if hours_old > 24:
            novelty_score *= max(0, 1 - (hours_old - 24) / 100)
        
        return max(0, min(novelty_score, 100))
    
    def _calculate_competition_score(self, features: Dict[str, Any]) -> float:
        """Calculate competition score (lower is better)"""
        # This would typically query a database of existing content
        # For now, use a heuristic based on trend popularity
        
        engagement = features.get('engagement', {})
        views = engagement.get('views', 0)
        
        if views > 1000000:
            return 80  # High competition
        elif views > 100000:
            return 60  # Medium competition
        elif views > 10000:
            return 40  # Low competition
        else:
            return 20  # Very low competition
    
    def _estimate_reach(self, features: Dict[str, Any]) -> int:
        """Estimate potential reach for content on this trend"""
        engagement = features.get('engagement', {})
        views = engagement.get('views', 0)
        
        # Simple estimation based on current views
        if views > 0:
            # Assume 1-5% of trend viewers would watch related content
            conversion_rate = np.random.uniform(0.01, 0.05)
            estimated_reach = int(views * conversion_rate)
        else:
            # Base estimate for new trends
            estimated_reach = np.random.randint(1000, 10000)
        
        # Adjust based on platform
        platform = features.get('platform', '').lower()
        platform_multipliers = {
            'youtube': 1.5,
            'tiktok': 2.0,
            'twitter': 0.8,
            'instagram': 1.2
        }
        
        estimated_reach = int(estimated_reach * platform_multipliers.get(platform, 1.0))
        
        return estimated_reach
    
    def _generate_tags(self, features: Dict[str, Any], category: TrendCategory) -> List[str]:
        """Generate relevant tags for the trend"""
        tags = []
        
        # Category tag
        tags.append(category.value)
        
        # Platform tag
        platform = features.get('platform', '').lower()
        if platform:
            tags.append(platform)
        
        # Keyword-based tags
        keywords = features.get('keywords', [])
        tags.extend(keywords[:5])  # Top 5 keywords
        
        # Popular tags based on trend
        if features.get('engagement_velocity', 0) > 0.5:
            tags.append('trending')
            tags.append('viral')
        
        # Remove duplicates and limit
        unique_tags = list(dict.fromkeys(tags))
        return unique_tags[:10]
    
    def _suggest_content_angles(self, features: Dict[str, Any], category: TrendCategory) -> List[str]:
        """Suggest content angles for this trend"""
        angles = []
        
        # Base angles for all trends
        base_angles = [
            "Explainer video",
            "Quick overview",
            "Deep dive analysis",
            "Comparison with similar trends",
            "Future implications"
        ]
        
        angles.extend(base_angles)
        
        # Category-specific angles
        if category == TrendCategory.TECHNOLOGY:
            angles.extend([
                "Technical tutorial",
                "Code walkthrough",
                "Product review",
                "Industry impact analysis"
            ])
        elif category == TrendCategory.ENTERTAINMENT:
            angles.extend([
                "Reaction video",
                "Behind the scenes",
                "Creator interview",
                "Trend compilation"
            ])
        elif category == TrendCategory.EDUCATION:
            angles.extend([
                "Step-by-step guide",
                "Common mistakes to avoid",
                "Advanced techniques",
                "Learning roadmap"
            ])
        
        # Platform-specific angles
        platform = features.get('platform', '').lower()
        if platform == 'tiktok':
            angles.append("15-second breakdown")
            angles.append("Duet/Stitch reaction")
        elif platform == 'youtube':
            angles.append("10-minute deep dive")
            angles.append("Live Q&A session")
        
        return angles[:8]  # Return top 8 angles
    
    def _identify_risks(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify potential risks with this trend"""
        risks = []
        
        # Controversy risk
        sentiment = self._calculate_sentiment_score(features)
        if sentiment < -0.3:
            risks.append({
                'type': 'controversy',
                'severity': 'high',
                'description': 'Trend has negative sentiment',
                'mitigation': 'Approach with caution, focus on facts'
            })
        
        # Saturation risk
        novelty = self._calculate_novelty_score(features)
        if novelty < 30:
            risks.append({
                'type': 'saturation',
                'severity': 'medium',
                'description': 'Trend may be oversaturated',
                'mitigation': 'Find unique angle or wait for next trend'
            })
        
        # Platform policy risk
        text = f"{features['title']} {features['description']}".lower()
        policy_risks = ['hate', 'violence', 'harassment', 'misinformation']
        if any(risk_word in text for risk_word in policy_risks):
            risks.append({
                'type': 'platform_policy',
                'severity': 'high',
                'description': 'Content may violate platform policies',
                'mitigation': 'Review platform guidelines carefully'
            })
        
        return risks
    
    def _calculate_confidence(self, features: Dict[str, Any]) -> float:
        """Calculate confidence in analysis"""
        confidence = 0.7  # Base confidence
        
        # Data completeness factor
        has_engagement = 'engagement' in features and features['engagement']
        has_text = features.get('title') and features.get('description')
        
        if has_engagement and has_text:
            confidence += 0.2
        elif has_engagement or has_text:
            confidence += 0.1
        
        # Historical data factor
        if len(self.trend_history) > 100:
            confidence += 0.1
        
        return min(confidence, 0.95)
    
    def _calculate_velocity(self, engagement: Dict[str, Any]) -> float:
        """Calculate engagement velocity"""
        # Simplified velocity calculation
        # In production, would use time-series data
        views = engagement.get('views', 0)
        likes = engagement.get('likes', 0)
        comments = engagement.get('comments', 0)
        shares = engagement.get('shares', 0)
        
        total_engagement = likes + comments * 2 + shares * 3
        if views > 0:
            engagement_rate = total_engagement / views
        else:
            engagement_rate = 0
        
        return min(engagement_rate * 10, 1.0)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Remove special characters and convert to lowercase
        text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Tokenize
        words = text_clean.split()
        
        # Remove stopwords (simplified list)
        stopwords = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        
        # Count frequencies
        from collections import Counter
        word_counts = Counter(keywords)
        
        # Return top keywords
        return [word for word, _ in word_counts.most_common(10)]
    
    def _calculate_text_complexity(self, text: str) -> float:
        """Calculate text complexity score (0-1)"""
        if not text:
            return 0.5
        
        # Sentence count
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        # Word count
        words = text.split()
        word_count = len(words)
        
        # Average sentence length
        if sentence_count > 0:
            avg_sentence_length = word_count / sentence_count
        else:
            avg_sentence_length = 0
        
        # Unique word ratio
        unique_words = set(words)
        uniqueness_ratio = len(unique_words) / max(word_count, 1)
        
        # Calculate complexity (normalized to 0-1)
        complexity = (avg_sentence_length / 20 + uniqueness_ratio) / 2
        
        return min(max(complexity, 0), 1)
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """Get summary of recent analyses"""
        if not self.trend_history:
            return {}
        
        recent = self.trend_history[-100:]
        
        avg_virality = np.mean([t['virality_score'] for t in recent])
        category_dist = {}
        for trend in recent:
            cat = trend['category']
            category_dist[cat] = category_dist.get(cat, 0) + 1
        
        return {
            'total_analyzed': len(self.trend_history),
            'recent_avg_virality': float(avg_virality),
            'category_distribution': category_dist,
            'analysis_confidence': self._calculate_confidence({})
        }