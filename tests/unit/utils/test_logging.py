# tests/unit/utils/test_logging.py
"""
Tests for structured logging module.
These tests should FAIL initially - they define the contract.
"""
import json
import pytest
import logging
from unittest.mock import Mock, patch
from utils.logging import (
    StructuredFormatter, AgentLogger, get_logger,
    set_correlation_id, get_correlation_id, LoggingContext
)

class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_structured_formatter_outputs_json(self):
        """Test that formatter outputs valid JSON."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # This should fail until formatter is implemented
        assert False, "Structured formatter not implemented"
        
        # When implemented, it should output valid JSON
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed
    
    def test_correlation_id_propagation(self):
        """Test that correlation IDs propagate through context."""
        # This test defines the expected behavior
        correlation_id = "test-correlation-123"
        
        # Should be able to set and get correlation ID
        set_correlation_id(correlation_id)
        retrieved = get_correlation_id()
        
        assert retrieved == correlation_id, "Correlation ID not properly propagated"
    
    def test_logging_context_manager(self):
        """Test the logging context manager."""
        # This test will fail until context manager is implemented
        with LoggingContext(correlation_id="ctx-123") as ctx:
            current_id = get_correlation_id()
            assert current_id == "ctx-123", "Context manager not setting correlation ID"
        
        # Should restore previous value
        assert get_correlation_id() is None, "Context manager not restoring previous state"
    
    def test_agent_logger_injects_context(self):
        """Test that AgentLogger injects agent context."""
        mock_logger = Mock(spec=logging.Logger)
        adapter = AgentLogger(mock_logger, agent_id="agent-001")
        
        # This test defines the expected behavior
        msg, kwargs = adapter.process("Test message", {})
        
        assert "agent_id" in kwargs.get("extra", {}), "AgentLogger not injecting agent_id"
        assert kwargs["extra"]["agent_id"] == "agent-001", "AgentLogger not setting correct agent_id"

@pytest.mark.performance
class TestLoggingPerformance:
    """Performance tests for logging."""
    
    def test_logging_latency(self):
        """Test that logging doesn't introduce significant latency."""
        import time
        # tests/unit/utils/test_logging.py
"""
Tests for structured logging module.
These tests should FAIL initially - they define the contract.
"""
import json
import pytest
import logging
from unittest.mock import Mock, patch
from utils.logging import (
    StructuredFormatter, AgentLogger, get_logger,
    set_correlation_id, get_correlation_id, LoggingContext
)

class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_structured_formatter_outputs_json(self):
        """Test that formatter outputs valid JSON."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # This should fail until formatter is implemented
        assert False, "Structured formatter not implemented"
        
        # When implemented, it should output valid JSON
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed
    
    def test_correlation_id_propagation(self):
        """Test that correlation IDs propagate through context."""
        # This test defines the expected behavior
        correlation_id = "test-correlation-123"
        
        # Should be able to set and get correlation ID
        set_correlation_id(correlation_id)
        retrieved = get_correlation_id()
        
        assert retrieved == correlation_id, "Correlation ID not properly propagated"
    
    def test_logging_context_manager(self):
        """Test the logging context manager."""
        # This test will fail until context manager is implemented
        with LoggingContext(correlation_id="ctx-123") as ctx:
            current_id = get_correlation_id()
            assert current_id == "ctx-123", "Context manager not setting correlation ID"
        
        # Should restore previous value
        assert get_correlation_id() is None, "Context manager not restoring previous state"
    
    def test_agent_logger_injects_context(self):
        """Test that AgentLogger injects agent context."""
        mock_logger = Mock(spec=logging.Logger)
        adapter = AgentLogger(mock_logger, agent_id="agent-001")
        
        # This test defines the expected behavior
        msg, kwargs = adapter.process("Test message", {})
        
        assert "agent_id" in kwargs.get("extra", {}), "AgentLogger not injecting agent_id"
        assert kwargs["extra"]["agent_id"] == "agent-001", "AgentLogger not setting correct agent_id"

@pytest.mark.performance
class TestLoggingPerformance:
    """Performance tests for logging."""
    
    def test_logging_latency(self):
        """Test that logging doesn't introduce significant latency."""
        import time
        
        logger = get_logger("performance_test")
        iterations = 1000
        
        start_time = time.time()
        for i in range(iterations):
            logger.info(f"Test message {i}")
        end_time = time.time()
        
        avg_time = (end_time - start_time) / iterations
        
        # Should be less than 1ms per log message
        assert avg_time < 0.001, f"Logging too slow: {avg_time * 1000:.2f}ms per message"
        logger = get_logger("performance_test")
        iterations = 1000
        
        start_time = time.time()
        for i in range(iterations):
            logger.info(f"Test message {i}")
        end_time = time.time()
        
        avg_time = (end_time - start_time) / iterations
        
        # Should be less than 1ms per log message
        assert avg_time < 0.001, f"Logging too slow: {avg_time * 1000:.2f}ms per message"