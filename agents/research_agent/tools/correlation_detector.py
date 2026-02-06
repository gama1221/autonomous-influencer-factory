"""
Correlation Detector - Identifies relationships between trends across platforms
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from utils.logging.structured_logger import get_logger


@dataclass
class CorrelationResult:
    """Result of correlation detection"""
    trend_a_id: str
    trend_b_id: str
    correlation_type: str  # 'direct', 'thematic', 'causal', 'competitive', 'complementary'
    confidence: float  # 0-1
    evidence: List[Dict[str, Any]]
    implications: Dict[str, Any]
    detected_at: datetime


class CorrelationDetector:
    """
    Detects correlations between social media trends
    """
    
    def __init__(self, min_confidence: float = 0.7):
        self.logger = get_logger("correlation_detector")
        self.min_confidence = min_confidence
        self.trend_graph = nx.Graph()
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words='english',
            ngram_range=(1, 3)
        )
        self.correlation_history = []
        
    def detect(self, trends: List[Dict[str, Any]]) -> Dict[str, List[CorrelationResult]]:
        """
        Detect correlations between trends
        
        Args:
            trends: List of trend dictionaries
            
        Returns:
            Dictionary mapping trend_id to list of correlations
        """
        self.logger.info(
            "Starting correlation detection",
            trends_count=len(trends)
        )
        
        # Prepare trend data
        trend_data = self._prepare_trend_data(trends)
        
        # Calculate similarities
        similarities = self._calculate_similarities(trend_data)
        
        # Detect correlations
        correlations = self._detect_correlations(trend_data, similarities)
        
        # Update graph
        self._update_correlation_graph(correlations)
        
        # Cluster related trends
        clusters = self._cluster_correlated_trends(correlations)
        
        # Generate insights
        insights = self._generate_insights(correlations, clusters)
        
        self.logger.info(
            "Correlation detection completed",
            correlations_found=len(correlations),
            clusters=len(clusters)
        )
        
        # Format results
        results = defaultdict(list)
        for corr in correlations:
            results[corr.trend_a_id].append(corr)
            results[corr.trend_b_id].append(corr)
        
        return dict(results)
    
    def _prepare_trend_data(self, trends: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Prepare trend data for analysis"""
        trend_data = {}
        
        for trend in trends:
            trend_id = trend.get('id', str(hash(str(trend))))
            
            # Extract features
            features = {
                'id': trend_id,
                'title': trend.get('title', ''),
                'description': trend.get('description', ''),
                'platform': trend.get('platform', 'unknown'),
                'category': trend.get('category', 'unknown'),
                'engagement': trend.get('engagement', {}),
                'timestamp': trend.get('timestamp') or datetime.utcnow(),
                'keywords': self._extract_keywords(
                    f"{trend.get('title', '')} {trend.get('description', '')}"
                ),
                'entities': trend.get('metadata', {}).get('entities', []),
                'hashtags': trend.get('metadata', {}).get('hashtags', [])
            }
            
            # Calculate temporal features
            features['temporal_score'] = self._calculate_temporal_score(features['timestamp'])
            
            trend_data[trend_id] = features
        
        return trend_data
    
    def _calculate_similarities(self, trend_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Calculate pairwise similarities between trends"""
        similarities = defaultdict(dict)
        trend_ids = list(trend_data.keys())
        
        # Text similarity
        texts = [f"{data['title']} {data['description']}" for data in trend_data.values()]
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            text_similarities = cosine_similarity(tfidf_matrix)
            
            for i, trend_a_id in enumerate(trend_ids):
                for j, trend_b_id in enumerate(trend_ids):
                    if i < j:  # Only calculate once per pair
                        similarity = text_similarities[i, j]
                        if similarity > 0.1:  # Minimum threshold
                            similarities[trend_a_id][trend_b_id] = similarity
                            similarities[trend_b_id][trend_a_id] = similarity
        except Exception as e:
            self.logger.warning("TF-IDF similarity calculation failed", error=str(e))
        
        # Temporal similarity
        for trend_a_id, data_a in trend_data.items():
            for trend_b_id, data_b in trend_data.items():
                if trend_a_id < trend_b_id:
                    time_diff = abs((data_a['timestamp'] - data_b['timestamp']).total_seconds())
                    temporal_sim = 1 / (1 + time_diff / 3600)  # Decay over hours
                    
                    if temporal_sim > 0.3:
                        if trend_b_id not in similarities[trend_a_id]:
                            similarities[trend_a_id][trend_b_id] = 0
                        similarities[trend_a_id][trend_b_id] += temporal_sim * 0.3
                        
                        if trend_a_id not in similarities[trend_b_id]:
                            similarities[trend_b_id][trend_a_id] = 0
                        similarities[trend_b_id][trend_a_id] += temporal_sim * 0.3
        
        # Platform similarity
        for trend_a_id, data_a in trend_data.items():
            for trend_b_id, data_b in trend_data.items():
                if trend_a_id < trend_b_id:
                    if data_a['platform'] == data_b['platform']:
                        if trend_b_id not in similarities[trend_a_id]:
                            similarities[trend_a_id][trend_b_id] = 0
                        similarities[trend_a_id][trend_b_id] += 0.2
                        
                        if trend_a_id not in similarities[trend_b_id]:
                            similarities[trend_b_id][trend_a_id] = 0
                        similarities[trend_b_id][trend_a_id] += 0.2
        
        return dict(similarities)
    
    def _detect_correlations(
        self,
        trend_data: Dict[str, Dict[str, Any]],
        similarities: Dict[str, Dict[str, float]]
    ) -> List[CorrelationResult]:
        """Detect correlations based on calculated similarities"""
        correlations = []
        
        for trend_a_id in similarities:
            for trend_b_id, similarity in similarities[trend_a_id].items():
                if trend_a_id < trend_b_id and similarity >= self.min_confidence:
                    correlation = self._analyze_correlation(
                        trend_data[trend_a_id],
                        trend_data[trend_b_id],
                        similarity
                    )
                    
                    if correlation:
                        correlations.append(correlation)
        
        return correlations
    
    def _analyze_correlation(
        self,
        trend_a: Dict[str, Any],
        trend_b: Dict[str, Any],
        similarity: float
    ) -> Optional[CorrelationResult]:
        """Analyze specific correlation between two trends"""
        # Determine correlation type
        correlation_type = self._determine_correlation_type(trend_a, trend_b, similarity)
        
        if not correlation_type:
            return None
        
        # Gather evidence
        evidence = self._gather_correlation_evidence(trend_a, trend_b, similarity)
        
        # Calculate confidence
        confidence = self._calculate_correlation_confidence(trend_a, trend_b, evidence)
        
        # Generate implications
        implications = self._generate_correlation_implications(
            trend_a, trend_b, correlation_type
        )
        
        correlation = CorrelationResult(
            trend_a_id=trend_a['id'],
            trend_b_id=trend_b['id'],
            correlation_type=correlation_type,
            confidence=confidence,
            evidence=evidence,
            implications=implications,
            detected_at=datetime.utcnow()
        )
        
        # Store in history
        self.correlation_history.append(correlation)
        
        return correlation
    
    def _determine_correlation_type(
        self,
        trend_a: Dict[str, Any],
        trend_b: Dict[str, Any],
        similarity: float
    ) -> Optional[str]:
        """Determine the type of correlation"""
        
        # Check for direct correlation (same topic, similar timing)
        text_a = f"{trend_a['title']} {trend_a['description']}".lower()
        text_b = f"{trend_b['title']} {trend_b['description']}".lower()
        
        # Keyword overlap
        keywords_a = set(trend_a['keywords'])
        keywords_b = set(trend_b['keywords'])
        keyword_overlap = len(keywords_a.intersection(keywords_b))
        
        # Temporal proximity
        time_diff = abs((trend_a['timestamp'] - trend_b['timestamp']).total_seconds() / 3600)
        
        # Platform consideration
        same_platform = trend_a['platform'] == trend_b['platform']
        
        # Determine correlation type
        if keyword_overlap >= 3 and time_diff < 24:
            if same_platform:
                return 'direct'
            else:
                return 'cross_platform'
        
        elif keyword_overlap >= 2 or similarity > 0.8:
            return 'thematic'
        
        # Check for competitive correlation (similar topics, different angles)
        elif keyword_overlap >= 2 and self._has_competitive_indicators(text_a, text_b):
            return 'competitive'
        
        # Check for complementary correlation (different but related topics)
        elif self._has_complementary_indicators(text_a, text_b):
            return 'complementary'
        
        # Check for causal relationship (time difference suggests causation)
        elif time_diff < 12 and self._suggests_causation(trend_a, trend_b):
            return 'causal'
        
        return None
    
    def _gather_correlation_evidence(
        self,
        trend_a: Dict[str, Any],
        trend_b: Dict[str, Any],
        similarity: float
    ) -> List[Dict[str, Any]]:
        """Gather evidence for correlation"""
        evidence = []
        
        # Text similarity evidence
        evidence.append({
            'type': 'text_similarity',
            'description': f'Text similarity score: {similarity:.2f}',
            'strength': float(similarity)
        })
        
        # Keyword overlap
        keywords_a = set(trend_a['keywords'])
        keywords_b = set(trend_b['keywords'])
        keyword_overlap = keywords_a.intersection(keywords_b)
        
        if keyword_overlap:
            evidence.append({
                'type': 'keyword_overlap',
                'description': f'Shared keywords: {", ".join(list(keyword_overlap)[:5])}',
                'strength': len(keyword_overlap) / max(len(keywords_a), len(keywords_b))
            })
        
        # Temporal proximity
        time_diff_hours = abs((trend_a['timestamp'] - trend_b['timestamp']).total_seconds() / 3600)
        if time_diff_hours < 48:
            evidence.append({
                'type': 'temporal_proximity',
                'description': f'Time difference: {time_diff_hours:.1f} hours',
                'strength': max(0, 1 - time_diff_hours / 48)
            })
        
        # Platform evidence
        if trend_a['platform'] == trend_b['platform']:
            evidence.append({
                'type': 'platform_same',
                'description': f'Same platform: {trend_a["platform"]}',
                'strength': 0.8
            })
        
        # Engagement pattern evidence
        eng_a = trend_a.get('engagement', {})
        eng_b = trend_b.get('engagement', {})
        
        if eng_a and eng_b:
            engagement_similarity = self._compare_engagement_patterns(eng_a, eng_b)
            if engagement_similarity > 0.5:
                evidence.append({
                    'type': 'engagement_pattern',
                    'description': 'Similar engagement patterns',
                    'strength': engagement_similarity
                })
        
        return evidence
    
    def _calculate_correlation_confidence(
        self,
        trend_a: Dict[str, Any],
        trend_b: Dict[str, Any],
        evidence: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence in correlation"""
        if not evidence:
            return 0.0
        
        # Average evidence strength
        strengths = [e['strength'] for e in evidence]
        avg_strength = sum(strengths) / len(strengths)
        
        # Adjust based on data quality
        data_quality = self._assess_data_quality(trend_a, trend_b)
        
        # Calculate final confidence
        confidence = avg_strength * data_quality
        
        # Apply minimum threshold
        return max(confidence, 0.0)
    
    def _generate_correlation_implications(
        self,
        trend_a: Dict[str, Any],
        trend_b: Dict[str, Any],
        correlation_type: str
    ) -> Dict[str, Any]:
        """Generate implications of correlation"""
        implications = {
            'content_creation': [],
            'audience_growth': [],
            'timing_optimization': [],
            'risk_mitigation': []
        }
        
        if correlation_type == 'direct':
            implications['content_creation'].append(
                'Create combined coverage addressing both trends'
            )
            implications['timing_optimization'].append(
                'Schedule content to leverage cross-trend interest'
            )
        
        elif correlation_type == 'cross_platform':
            implications['content_creation'].append(
                'Adapt content format for each platform'
            )
            implications['audience_growth'].append(
                'Cross-promote content across platforms'
            )
        
        elif correlation_type == 'thematic':
            implications['content_creation'].append(
                'Create series exploring related themes'
            )
            implications['audience_growth'].append(
                'Target audiences interested in the broader theme'
            )
        
        elif correlation_type == 'competitive':
            implications['content_creation'].append(
                'Create comparative analysis content'
            )
            implications['risk_mitigation'].append(
                'Differentiate clearly to avoid confusion'
            )
        
        elif correlation_type == 'complementary':
            implications['content_creation'].append(
                'Create bundled content packages'
            )
            implications['audience_growth'].append(
                'Cross-sell to audiences of complementary trends'
            )
        
        elif correlation_type == 'causal':
            implications['content_creation'].append(
                'Create content explaining the causal relationship'
            )
            implications['timing_optimization'].append(
                f'Release content after {trend_a["id"]} but before trend peaks'
            )
        
        return implications
    
    def _update_correlation_graph(self, correlations: List[CorrelationResult]) -> None:
        """Update correlation graph with new correlations"""
        for correlation in correlations:
            # Add nodes
            self.trend_graph.add_node(correlation.trend_a_id)
            self.trend_graph.add_node(correlation.trend_b_id)
            
            # Add edge with correlation metadata
            self.trend_graph.add_edge(
                correlation.trend_a_id,
                correlation.trend_b_id,
                correlation_type=correlation.correlation_type,
                confidence=correlation.confidence,
                detected_at=correlation.detected_at
            )
    
    def _cluster_correlated_trends(self, correlations: List[CorrelationResult]) -> List[List[str]]:
        """Cluster trends based on correlations"""
        if not correlations:
            return []
        
        # Create subgraph with high-confidence correlations
        high_conf_edges = [
            (c.trend_a_id, c.trend_b_id)
            for c in correlations
            if c.confidence >= 0.8
        ]
        
        if not high_conf_edges:
            return []
        
        high_conf_graph = nx.Graph()
        high_conf_graph.add_edges_from(high_conf_edges)
        
        # Find connected components (clusters)
        clusters = list(nx.connected_components(high_conf_graph))
        
        # Convert to list of lists
        return [list(cluster) for cluster in clusters]
    
    def _generate_insights(
        self,
        correlations: List[CorrelationResult],
        clusters: List[List[str]]
    ) -> Dict[str, Any]:
        """Generate insights from correlations and clusters"""
        insights = {
            'summary': {
                'total_correlations': len(correlations),
                'high_confidence_correlations': len([c for c in correlations if c.confidence >= 0.8]),
                'clusters_found': len(clusters),
                'avg_cluster_size': np.mean([len(c) for c in clusters]) if clusters else 0
            },
            'cluster_analysis': [],
            'trend_network_metrics': {}
        }
        
        # Analyze clusters
        for i, cluster in enumerate(clusters):
            if len(cluster) >= 3:  # Only analyze significant clusters
                cluster_insight = {
                    'cluster_id': f'cluster_{i}',
                    'size': len(cluster),
                    'themes': self._extract_cluster_themes(cluster),
                    'key_trends': cluster[:3]  # First 3 trends
                }
                insights['cluster_analysis'].append(cluster_insight)
        
        # Calculate network metrics if graph is populated
        if self.trend_graph.number_of_nodes() > 0:
            insights['trend_network_metrics'] = {
                'density': nx.density(self.trend_graph),
                'average_clustering': nx.average_clustering(self.trend_graph),
                'central_trends': self._identify_central_trends()
            }
        
        return insights
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Simple keyword extraction
        import re
        from collections import Counter
        
        # Remove special characters and convert to lowercase
        text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Tokenize and remove stopwords
        stopwords = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        words = [word for word in text_clean.split() if word not in stopwords and len(word) > 2]
        
        # Count and return top keywords
        word_counts = Counter(words)
        return [word for word, _ in word_counts.most_common(10)]
    
    def _calculate_temporal_score(self, timestamp: datetime) -> float:
        """Calculate temporal score based on recency"""
        now = datetime.utcnow()
        hours_old = (now - timestamp).total_seconds() / 3600
        
        # Exponential decay: score = e^(-hours/24)
        return np.exp(-hours_old / 24)
    
    def _has_competitive_indicators(self, text_a: str, text_b: str) -> bool:
        """Check if texts suggest competitive relationship"""
        competitive_indicators = [
            'vs', 'versus', 'better than', 'worse than',
            'comparison', 'alternative', 'competitor'
        ]
        
        return any(indicator in text_a or indicator in text_b 
                  for indicator in competitive_indicators)
    
    def _has_complementary_indicators(self, text_a: str, text_b: str) -> bool:
        """Check if texts suggest complementary relationship"""
        complementary_indicators = [
            'and', 'also', 'plus', 'with', 'together',
            'combined', 'bundle', 'package'
        ]
        
        # Check if texts mention each other or related concepts
        words_a = set(text_a.split())
        words_b = set(text_b.split())
        
        # If they share few words but are in similar context
        shared_words = words_a.intersection(words_b)
        return len(shared_words) >= 1 and len(shared_words) <= 3
    
    def _suggests_causation(self, trend_a: Dict[str, Any], trend_b: Dict[str, Any]) -> bool:
        """Check if trends suggest causal relationship"""
        # Simple heuristic: if trend_a mentions something that could cause trend_b
        text_a = f"{trend_a['title']} {trend_a['description']}".lower()
        text_b = f"{trend_b['title']} {trend_b['description']}".lower()
        
        causal_indicators = ['causes', 'leads to', 'results in', 'triggers', 'because of']
        
        return any(indicator in text_a or indicator in text_b 
                  for indicator in causal_indicators)
    
    def _compare_engagement_patterns(self, eng_a: Dict[str, Any], eng_b: Dict[str, Any]) -> float:
        """Compare engagement patterns between trends"""
        metrics = ['views', 'likes', 'comments', 'shares']
        similarities = []
        
        for metric in metrics:
            val_a = eng_a.get(metric, 0)
            val_b = eng_b.get(metric, 0)
            
            if val_a > 0 and val_b > 0:
                # Calculate similarity of engagement rates
                ratio = min(val_a, val_b) / max(val_a, val_b)
                similarities.append(ratio)
        
        return np.mean(similarities) if similarities else 0.0
    
    def _assess_data_quality(self, trend_a: Dict[str, Any], trend_b: Dict[str, Any]) -> float:
        """Assess quality of trend data"""
        quality_score = 0.5  # Base score
        
        # Text completeness
        has_title_a = bool(trend_a.get('title'))
        has_title_b = bool(trend_b.get('title'))
        has_desc_a = bool(trend_a.get('description'))
        has_desc_b = bool(trend_b.get('description'))
        
        text_completeness = (has_title_a + has_title_b + has_desc_a + has_desc_b) / 4
        quality_score += text_completeness * 0.3
        
        # Engagement data
        has_engagement_a = bool(trend_a.get('engagement'))
        has_engagement_b = bool(trend_b.get('engagement'))
        
        if has_engagement_a and has_engagement_b:
            quality_score += 0.2
        
        return min(quality_score, 1.0)
    
    def _extract_cluster_themes(self, cluster: List[str]) -> List[str]:
        """Extract common themes from a cluster of trend IDs"""
        # In production, would analyze trend content
        # For now, return placeholder
        return ['technology', 'innovation', 'future']
    
    def _identify_central_trends(self) -> List[str]:
        """Identify central trends in the correlation graph"""
        if self.trend_graph.number_of_nodes() == 0:
            return []
        
        # Calculate betweenness centrality
        centrality = nx.betweenness_centrality(self.trend_graph)
        
        # Get top 3 central trends
        central_trends = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return [trend_id for trend_id, _ in central_trends]
    
    def get_correlation_summary(self) -> Dict[str, Any]:
        """Get summary of correlation detection"""
        return {
            'total_correlations_detected': len(self.correlation_history),
            'graph_nodes': self.trend_graph.number_of_nodes(),
            'graph_edges': self.trend_graph.number_of_edges(),
            'avg_confidence': np.mean([c.confidence for c in self.correlation_history]) 
                           if self.correlation_history else 0,
            'correlation_types': self._get_correlation_type_distribution()
        }
    
    def _get_correlation_type_distribution(self) -> Dict[str, int]:
        """Get distribution of correlation types"""
        distribution = {}
        for correlation in self.correlation_history:
            corr_type = correlation.correlation_type
            distribution[corr_type] = distribution.get(corr_type, 0) + 1
        
        return distribution