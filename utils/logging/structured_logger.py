# utils/logging/structured_logger.py
"""
Extended structured logging functionality.
"""
import functools
import time
from typing import Any, Callable, Optional, TypeVar, cast
from contextlib import contextmanager
from . import get_logger, set_correlation_id, get_correlation_id, set_skill_id

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

class LoggingContext:
    """Context manager for logging context."""
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        mcp_trace_id: Optional[str] = None
    ):
        self.correlation_id = correlation_id
        self.agent_id = agent_id
        self.skill_id = skill_id
        self.mcp_trace_id = mcp_trace_id
        self._prev_correlation_id = None
        self._prev_agent_id = None
        self._prev_skill_id = None
        self._prev_mcp_trace_id = None
    
    def __enter__(self):
        # Store previous values
        self._prev_correlation_id = get_correlation_id()
        self._prev_agent_id = get_agent_id()
        self._prev_skill_id = get_skill_id()
        self._prev_mcp_trace_id = get_mcp_trace_id()
        
        # Set new values
        if self.correlation_id:
            set_correlation_id(self.correlation_id)
        if self.agent_id:
            set_agent_id(self.agent_id)
        if self.skill_id:
            set_skill_id(self.skill_id)
        if self.mcp_trace_id:
            set_mcp_trace_id(self.mcp_trace_id)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous values
        if self._prev_correlation_id:
            set_correlation_id(self._prev_correlation_id)
        if self._prev_agent_id:
            set_agent_id(self._prev_agent_id)
        if self._prev_skill_id:
            set_skill_id(self._prev_skill_id)
        if self._prev_mcp_trace_id:
            set_mcp_trace_id(self._prev_mcp_trace_id)

def log_execution(
    logger_name: str = "execution",
    level: int = logging.INFO,
    log_args: bool = True,
    log_result: bool = False,
    log_exceptions: bool = True
):
    """
    Decorator to log function execution.
    
    Args:
        logger_name: Name of the logger to use
        level: Log level for execution messages
        log_args: Whether to log function arguments
        log_result: Whether to log function return value
        log_exceptions: Whether to log exceptions
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = func.__name__
            
            # Log start of execution
            start_time = time.time()
            log_data = {
                "function": func_name,
                "status": "started"
            }
            
            if log_args:
                # Mask sensitive arguments
                masked_kwargs = {
                    k: "***" if any(s in k.lower() for s in ["pass", "secret", "key", "token"]) else v
                    for k, v in kwargs.items()
                }
                log_data["args"] = str(args)
                log_data["kwargs"] = masked_kwargs
            
            logger.log(level, f"Executing {func_name}", extra=log_data)
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log successful completion
                log_data.update({
                    "status": "completed",
                    "execution_time_seconds": execution_time
                })
                
                if log_result:
                    log_data["result"] = str(result)
                
                logger.log(level, f"Completed {func_name}", extra=log_data)
                
                return result
                
            except Exception as e:
                if log_exceptions:
                    execution_time = time.time() - start_time
                    logger.error(
                        f"Failed {func_name}: {str(e)}",
                        extra={
                            "function": func_name,
                            "status": "failed",
                            "execution_time_seconds": execution_time,
                            "exception": str(e),
                            "exception_type": type(e).__name__
                        },
                        exc_info=True
                    )
                raise
        
        return cast(F, wrapper)
    
    return decorator

@contextmanager
def log_operation(
    operation_name: str,
    logger_name: str = "operation",
    level: int = logging.INFO,
    **context_kwargs
):
    """
    Context manager for logging operations.
    
    Args:
        operation_name: Name of the operation
        logger_name: Name of the logger to use
        level: Log level for operation messages
        **context_kwargs: Additional context for the operation
    """
    logger = get_logger(logger_name)
    start_time = time.time()
    
    # Log operation start
    logger.log(
        level,
        f"Starting operation: {operation_name}",
        extra={
            "operation": operation_name,
            "status": "started",
            **context_kwargs
        }
    )
    
    try:
        yield
        execution_time = time.time() - start_time
        
        # Log operation success
        logger.log(
            level,
            f"Completed operation: {operation_name}",
            extra={
                "operation": operation_name,
                "status": "completed",
                "execution_time_seconds": execution_time,
                **context_kwargs
            }
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        # Log operation failure
        logger.error(
            f"Failed operation: {operation_name}",
            extra={
                "operation": operation_name,
                "status": "failed",
                "execution_time_seconds": execution_time,
                "exception": str(e),
                "exception_type": type(e).__name__,
                **context_kwargs
            },
            exc_info=True
        )
        raise

def create_correlation_context() -> LoggingContext:
    """Create a new logging context with a generated correlation ID."""
    correlation_id = str(uuid.uuid4())
    return LoggingContext(correlation_id=correlation_id)