# utils/telemetry/metrics.py
"""
Metrics collection for Project Chimera.
"""
import time
from typing import Dict, Any, Optional, Callable
import functools
from datetime import datetime, timezone
from enum import Enum
import threading
from collections import defaultdict

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary,
        start_http_server, generate_latest, REGISTRY
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from ..logging import get_logger, log_execution

logger = get_logger("telemetry.metrics")

class MetricType(Enum):
    """Type of metric."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

class ChimeraMetric:
    """Base class for Chimera metrics."""
    
    def __init__(self, name: str, description: str, labels: Optional[list] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.metric = None
    
    def observe(self, value: float = 1.0, **label_values) -> None:
        """Observe a metric value."""
        pass
    
    def inc(self, amount: float = 1.0, **label_values) -> None:
        """Increment a counter metric."""
        pass
    
    def dec(self, amount: float = 1.0, **label_values) -> None:
        """Decrement a gauge metric."""
        pass
    
    def set(self, value: float, **label_values) -> None:
        """Set a gauge metric value."""
        pass
    
    def time(self) -> Callable:
        """Context manager/decorator to time operations."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    self.observe(duration, **kwargs.get('metric_labels', {}))
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.observe(duration, **kwargs.get('metric_labels', {}))
                    raise
            return wrapper
        return decorator

class PrometheusMetric(ChimeraMetric):
    """Prometheus implementation of metrics."""
    
    def __init__(self, name: str, description: str, metric_type: MetricType, labels: Optional[list] = None, **kwargs):
        super().__init__(name, description, labels)
        
        if not PROMETHEUS_AVAILABLE:
            logger.warning(f"Prometheus not available. Metric {name} will be no-op.")
            return
        
        if metric_type == MetricType.COUNTER:
            self.metric = Counter(name, description, labels, **kwargs)
        elif metric_type == MetricType.GAUGE:
            self.metric = Gauge(name, description, labels, **kwargs)
        elif metric_type == MetricType.HISTOGRAM:
            self.metric = Histogram(name, description, labels, **kwargs)
        elif metric_type == MetricType.SUMMARY:
            self.metric = Summary(name, description, labels, **kwargs)
    
    def observe(self, value: float = 1.0, **label_values) -> None:
        if self.metric and isinstance(self.metric, (Histogram, Summary)):
            self.metric.observe(value)
    
    def inc(self, amount: float = 1.0, **label_values) -> None:
        if self.metric:
            if isinstance(self.metric, Counter):
                self.metric.inc(amount)
            elif isinstance(self.metric, Gauge):
                self.metric.inc(amount)
    
    def dec(self, amount: float = 1.0, **label_values) -> None:
        if self.metric and isinstance(self.metric, Gauge):
            self.metric.dec(amount)
    
    def set(self, value: float, **label_values) -> None:
        if self.metric and isinstance(self.metric, Gauge):
            self.metric.set(value)

class NoOpMetric(ChimeraMetric):
    """No-op implementation when Prometheus is not available."""
    pass

class MetricsRegistry:
    """Registry for managing all metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, ChimeraMetric] = {}
        self.lock = threading.Lock()
    
    def register(self, metric: ChimeraMetric) -> None:
        """Register a metric."""
        with self.lock:
            if metric.name in self.metrics:
                logger.warning(f"Metric {metric.name} already registered. Overwriting.")
            self.metrics[metric.name] = metric
    
    def get(self, name: str) -> Optional[ChimeraMetric]:
        """Get a metric by name."""
        return self.metrics.get(name)
    
    def export_metrics(self) -> bytes:
        """Export metrics in Prometheus format."""
        if not PROMETHEUS_AVAILABLE:
            return b"# Metrics not available (Prometheus not installed)\n"
        
        try:
            return generate_latest()
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return b""

# Global registry instance
_registry = MetricsRegistry()

class ChimeraMetrics:
    """Main metrics class for Project Chimera."""
    
    def __init__(self, registry: MetricsRegistry = _registry):
        self.registry = registry
        self._setup_metrics()
    
    def _setup_metrics(self) -> None:
        """Setup all required metrics."""
        
        # Agent metrics
        self.agent_execution_time = self._create_metric(
            "chimera_agent_execution_time_seconds",
            "Time taken for agent execution in seconds",
            MetricType.HISTOGRAM,
            labels=["agent_type", "agent_id", "status"]
        )
        
        self.agent_execution_count = self._create_metric(
            "chimera_agent_execution_count",
            "Total number of agent executions",
            MetricType.COUNTER,
            labels=["agent_type", "agent_id", "status"]
        )
        
        self.agent_concurrent_executions = self._create_metric(
            "chimera_agent_concurrent_executions",
            "Current number of concurrent agent executions",
            MetricType.GAUGE,
            labels=["agent_type"]
        )
        
        # Skill metrics
        self.skill_execution_time = self._create_metric(
            "chimera_skill_execution_time_seconds",
            "Time taken for skill execution in seconds",
            MetricType.HISTOGRAM,
            labels=["skill_name", "skill_version", "status"]
        )
        
        self.skill_execution_count = self._create_metric(
            "chimera_skill_execution_count",
            "Total number of skill executions",
            MetricType.COUNTER,
            labels=["skill_name", "skill_version", "status"]
        )
        
        self.skill_success_rate = self._create_metric(
            "chimera_skill_success_rate",
            "Success rate of skill executions",
            MetricType.GAUGE,
            labels=["skill_name", "skill_version"]
        )
        
        # System metrics
        self.system_cpu_usage = self._create_metric(
            "chimera_system_cpu_usage_percent",
            "System CPU usage percentage",
            MetricType.GAUGE
        )
        
        self.system_memory_usage = self._create_metric(
            "chimera_system_memory_usage_bytes",
            "System memory usage in bytes",
            MetricType.GAUGE
        )
        
        # OpenClaw integration metrics
        self.openclaw_messages_sent = self._create_metric(
            "chimera_openclaw_messages_sent",
            "Number of messages sent to OpenClaw network",
            MetricType.COUNTER,
            labels=["message_type", "status"]
        )
        
        self.openclaw_messages_received = self._create_metric(
            "chimera_openclaw_messages_received",
            "Number of messages received from OpenClaw network",
            MetricType.COUNTER,
            labels=["message_type", "status"]
        )
    
    def _create_metric(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        labels: Optional[list] = None
    ) -> ChimeraMetric:
        """Create and register a metric."""
        if PROMETHEUS_AVAILABLE:
            metric = PrometheusMetric(name, description, metric_type, labels)
        else:
            metric = NoOpMetric(name, description, labels)
        
        self.registry.register(metric)
        return metric
    
    @log_execution(logger_name="metrics", log_args=False)
    def record_agent_execution(
        self,
        agent_type: str,
        agent_id: str,
        execution_time: float,
        success: bool = True
    ) -> None:
        """Record agent execution metrics."""
        status = "success" if success else "failure"
        
        # Record execution time
        self.agent_execution_time.observe(
            execution_time,
            agent_type=agent_type,
            agent_id=agent_id,
            status=status
        )
        
        # Increment execution count
        self.agent_execution_count.inc(
            agent_type=agent_type,
            agent_id=agent_id,
            status=status
        )
        
        # Update success rate (simplified - in reality would need more sophisticated tracking)
        if success:
            logger.debug(f"Recorded successful agent execution: {agent_type}.{agent_id}")
        else:
            logger.warning(f"Recorded failed agent execution: {agent_type}.{agent_id}")
    
    @log_execution(logger_name="metrics", log_args=False)
    def record_skill_execution(
        self,
        skill_name: str,
        skill_version: str,
        execution_time: float,
        success: bool = True
    ) -> None:
        """Record skill execution metrics."""
        status = "success" if success else "failure"
        
        # Record execution time
        self.skill_execution_time.observe(
            execution_time,
            skill_name=skill_name,
            skill_version=skill_version,
            status=status
        )
        
        # Increment execution count
        self.skill_execution_count.inc(
            skill_name=skill_name,
            skill_version=skill_version,
            status=status
        )
        
        # Calculate and set success rate
        # Note: This is a simplified calculation - in production you'd want
        # to maintain a rolling window or use a different approach
        if success:
            logger.debug(f"Recorded successful skill execution: {skill_name}.{skill_version}")
        else:
            logger.warning(f"Recorded failed skill execution: {skill_name}.{skill_version}")
    
    def update_system_metrics(self) -> None:
        """Update system metrics."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.used)
            
        except ImportError:
            logger.warning("psutil not installed. System metrics not available.")
    
    def record_openclaw_message(self, message_type: str, success: bool = True) -> None:
        """Record OpenClaw message metrics."""
        status = "success" if success else "failure"
        
        if success:
            self.openclaw_messages_sent.inc(
                message_type=message_type,
                status=status
            )
        else:
            self.openclaw_messages_received.inc(
                message_type=message_type,
                status=status
            )
    
    def start_metrics_server(self, port: int = 9090) -> None:
        """Start Prometheus metrics server."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus not available. Metrics server not started.")
            return
        
        try:
            start_http_server(port)
            logger.info(f"Metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

# Global metrics instance
_metrics_instance = None

def get_metrics() -> ChimeraMetrics:
    """Get the global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ChimeraMetrics()
    return _metrics_instance