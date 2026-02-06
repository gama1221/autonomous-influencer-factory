
## 2. Implementation of Utility Modules

"""
Structured logging module for Project Chimera.
Provides JSON-formatted logging with context propagation.
"""
import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from contextvars import ContextVar
import inspect

# Context variable for correlation ID
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
_agent_id: ContextVar[Optional[str]] = ContextVar('agent_id', default=None)
_skill_id: ContextVar[Optional[str]] = ContextVar('skill_id', default=None)
_mcp_trace_id: ContextVar[Optional[str]] = ContextVar('mcp_trace_id', default=None)

def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return _correlation_id.get()

def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id.set(correlation_id)

def get_agent_id() -> Optional[str]:
    """Get the current agent ID."""
    return _agent_id.get()

def set_agent_id(agent_id: str) -> None:
    """Set the agent ID for the current context."""
    _agent_id.set(agent_id)

def get_skill_id() -> Optional[str]:
    """Get the current skill ID."""
    return _skill_id.get()

def set_skill_id(skill_id: str) -> None:
    """Set the skill ID for the current context."""
    _skill_id.set(skill_id)

def get_mcp_trace_id() -> Optional[str]:
    """Get the current MCP trace ID."""
    return _mcp_trace_id.get()

def set_mcp_trace_id(trace_id: str) -> None:
    """Set the MCP trace ID for the current context."""
    _mcp_trace_id.set(trace_id)

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get calling module and function
        frame = inspect.currentframe()
        try:
            while frame:
                frame = frame.f_back
                if frame and frame.f_code.co_name == '_log':
                    # Found the logging call frame
                    caller_frame = frame.f_back
                    if caller_frame:
                        module = caller_frame.f_globals.get('__name__', 'unknown')
                        function = caller_frame.f_code.co_name
                        break
                elif not frame:
                    module = 'unknown'
                    function = 'unknown'
                    break
        finally:
            del frame
        
        # Build structured log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": module,
            "function": function,
            "correlation_id": get_correlation_id(),
            "agent_id": get_agent_id(),
            "skill_id": get_skill_id(),
            "mcp_trace_id": get_mcp_trace_id(),
            "message": record.getMessage(),
            "extra": {}
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, 'extra'):
            log_entry["extra"].update(record.extra)
        
        return json.dumps(log_entry, default=str)

class AgentLogger(logging.LoggerAdapter):
    """Logger adapter that injects agent context."""
    
    def __init__(self, logger: logging.Logger, agent_id: Optional[str] = None):
        super().__init__(logger, {})
        self.agent_id = agent_id
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Process log message and inject context."""
        extra = kwargs.get('extra', {})
        
        # Inject context
        if self.agent_id:
            extra['agent_id'] = self.agent_id
        
        correlation_id = get_correlation_id()
        if correlation_id:
            extra['correlation_id'] = correlation_id
        
        skill_id = get_skill_id()
        if skill_id:
            extra['skill_id'] = skill_id
        
        mcp_trace_id = get_mcp_trace_id()
        if mcp_trace_id:
            extra['mcp_trace_id'] = mcp_trace_id
        
        kwargs['extra'] = extra
        return msg, kwargs

def setup_logging(config_path: Optional[str] = None) -> None:
    """Setup structured logging configuration."""
    if config_path:
        with open(config_path, 'r') as f:
            import yaml
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    else:
        # Default configuration
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        
        # Set specific log levels for our modules
        logging.getLogger("chimera").setLevel(logging.DEBUG)

def get_logger(name: str, agent_id: Optional[str] = None) -> AgentLogger:
    """Get a logger with agent context."""
    logger = logging.getLogger(f"chimera.{name}")
    return AgentLogger(logger, agent_id)

# Default logger
logger = get_logger("utils.logging")