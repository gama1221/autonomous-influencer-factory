# utils/telemetry/tracer.py
"""
OpenTelemetry tracing integration for Project Chimera.
"""
from typing import Optional, Dict, Any, Callable
import functools
from contextlib import contextmanager
import uuid

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.context import Context
    from opentelemetry.propagate import inject, extract
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

from ..logging import get_logger, LoggingContext, get_correlation_id, set_mcp_trace_id

logger = get_logger("telemetry.tracer")

class ChimeraTracer:
    """Tracer for Project Chimera agents and skills."""
    
    def __init__(self, service_name: str = "chimera-factory"):
        self.service_name = service_name
        self.tracer = None
        
        if OPENTELEMETRY_AVAILABLE:
            self._setup_opentelemetry()
        else:
            logger.warning("OpenTelemetry not available. Using no-op tracer.")
    
    def _setup_opentelemetry(self) -> None:
        """Setup OpenTelemetry tracing."""
        # Create tracer provider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        
        # Add console exporter for development
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        
        # Add OTLP exporter if configured
        otlp_endpoint = None  # Should come from config
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        self.tracer = trace.get_tracer(self.service_name)
    
    def start_span(
        self,
        name: str,
        kind: str = "INTERNAL",
        attributes: Optional[Dict[str, Any]] = None,
        parent_context: Optional[Context] = None
    ) -> "ChimeraSpan":
        """Start a new span."""
        if not self.tracer:
            return NoOpSpan(name)
        
        span_kind = getattr(trace.SpanKind, kind.upper(), trace.SpanKind.INTERNAL)
        
        span = self.tracer.start_span(
            name=name,
            kind=span_kind,
            attributes=attributes or {},
            context=parent_context
        )
        
        return OpenTelemetrySpan(span)
    
    @contextmanager
    def span(
        self,
        name: str,
        kind: str = "INTERNAL",
        attributes: Optional[Dict[str, Any]] = None,
        record_exception: bool = True
    ):
        """Context manager for creating spans."""
        span = self.start_span(name, kind, attributes)
        
        try:
            yield span
            span.set_status("OK")
        except Exception as e:
            if record_exception:
                span.record_exception(e)
            span.set_status("ERROR", str(e))
            raise
        finally:
            span.end()
    
    def trace_agent_execution(
        self,
        agent_id: str,
        agent_type: str,
        input_data: Optional[Dict] = None
    ):
        """Decorator to trace agent execution."""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.span(
                    f"agent.{agent_type}.execute",
                    kind="INTERNAL",
                    attributes={
                        "agent.id": agent_id,
                        "agent.type": agent_type,
                        "agent.input.size": len(str(input_data)) if input_data else 0
                    }
                ) as span:
                    # Add correlation ID to span
                    correlation_id = get_correlation_id() or str(uuid.uuid4())
                    span.set_attribute("correlation.id", correlation_id)
                    
                    # Set MCP trace ID
                    set_mcp_trace_id(span.get_trace_id())
                    
                    # Log start
                    logger.info(
                        f"Agent execution started",
                        extra={
                            "agent_id": agent_id,
                            "agent_type": agent_type,
                            "correlation_id": correlation_id,
                            "trace_id": span.get_trace_id()
                        }
                    )
                    
                    try:
                        result = func(*args, **kwargs)
                        
                        # Log success
                        logger.info(
                            f"Agent execution completed",
                            extra={
                                "agent_id": agent_id,
                                "agent_type": agent_type,
                                "correlation_id": correlation_id,
                                "trace_id": span.get_trace_id()
                            }
                        )
                        
                        return result
                    except Exception as e:
                        # Log failure
                        logger.error(
                            f"Agent execution failed",
                            extra={
                                "agent_id": agent_id,
                                "agent_type": agent_type,
                                "correlation_id": correlation_id,
                                "trace_id": span.get_trace_id(),
                                "error": str(e)
                            },
                            exc_info=True
                        )
                        raise
            
            return wrapper
        return decorator
    
    def trace_skill_execution(
        self,
        skill_name: str,
        skill_version: str = "1.0.0"
    ):
        """Decorator to trace skill execution."""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.span(
                    f"skill.{skill_name}.execute",
                    kind="INTERNAL",
                    attributes={
                        "skill.name": skill_name,
                        "skill.version": skill_version
                    }
                ) as span:
                    # Add correlation ID
                    correlation_id = get_correlation_id() or str(uuid.uuid4())
                    span.set_attribute("correlation.id", correlation_id)
                    
                    # Log skill execution
                    logger.debug(
                        f"Skill execution started",
                        extra={
                            "skill_name": skill_name,
                            "skill_version": skill_version,
                            "correlation_id": correlation_id,
                            "trace_id": span.get_trace_id()
                        }
                    )
                    
                    try:
                        result = func(*args, **kwargs)
                        
                        # Add output size attribute
                        if result:
                            span.set_attribute("skill.output.size", len(str(result)))
                        
                        logger.debug(
                            f"Skill execution completed",
                            extra={
                                "skill_name": skill_name,
                                "skill_version": skill_version,
                                "correlation_id": correlation_id,
                                "trace_id": span.get_trace_id(),
                                "output_size": len(str(result)) if result else 0
                            }
                        )
                        
                        return result
                    except Exception as e:
                        logger.error(
                            f"Skill execution failed",
                            extra={
                                "skill_name": skill_name,
                                "skill_version": skill_version,
                                "correlation_id": correlation_id,
                                "trace_id": span.get_trace_id(),
                                "error": str(e)
                            },
                            exc_info=True
                        )
                        raise
            
            return wrapper
        return decorator
    
    def get_trace_context(self) -> Dict[str, str]:
        """Get trace context for propagation."""
        if not OPENTELEMETRY_AVAILABLE:
            return {}
        
        context = {}
        inject(context)
        return context
    
    def extract_trace_context(self, carrier: Dict[str, str]) -> Optional[Context]:
        """Extract trace context from carrier."""
        if not OPENTELEMETRY_AVAILABLE:
            return None
        
        try:
            return extract(carrier)
        except Exception as e:
            logger.warning(f"Failed to extract trace context: {e}")
            return None

# Abstract span interface
class ChimeraSpan:
    """Abstract span interface."""
    
    def __init__(self, name: str):
        self.name = name
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Set span attribute."""
        pass
    
    def set_status(self, status: str, description: str = "") -> None:
        """Set span status."""
        pass
    
    def record_exception(self, exception: Exception) -> None:
        """Record exception in span."""
        pass
    
    def end(self) -> None:
        """End the span."""
        pass
    
    def get_trace_id(self) -> str:
        """Get trace ID."""
        return "no-op-trace-id"

# OpenTelemetry implementation
class OpenTelemetrySpan(ChimeraSpan):
    """OpenTelemetry span implementation."""
    
    def __init__(self, span):
        super().__init__(span.name)
        self._span = span
    
    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)
    
    def set_status(self, status: str, description: str = "") -> None:
        if status.upper() == "OK":
            self._span.set_status(Status(StatusCode.OK))
        else:
            self._span.set_status(Status(StatusCode.ERROR, description))
    
    def record_exception(self, exception: Exception) -> None:
        self._span.record_exception(exception)
    
    def end(self) -> None:
        self._span.end()
    
    def get_trace_id(self) -> str:
        return format(self._span.get_span_context().trace_id, '032x')

# No-op implementation
class NoOpSpan(ChimeraSpan):
    """No-op span for when OpenTelemetry is not available."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self._trace_id = str(uuid.uuid4())
    
    def get_trace_id(self) -> str:
        return self._trace_id

# Global tracer instance
_tracer_instance = None

def get_tracer() -> ChimeraTracer:
    """Get the global tracer instance."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = ChimeraTracer()
    return _tracer_instance