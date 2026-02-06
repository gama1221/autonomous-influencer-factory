"""
Research Agent Module

Responsible for trend discovery, analysis, and correlation detection
across multiple social platforms.
"""

from .agent import ResearchAgent
from .tools.trend_analyzer import TrendAnalyzer
from .tools.correlation_detector import CorrelationDetector

__version__ = "1.0.0"
__all__ = ["ResearchAgent", "TrendAnalyzer", "CorrelationDetector"]