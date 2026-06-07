from src.logger import setup_logging
import logging

def test_setup_logging_creation():
    """Test that setup_logging configures root logger."""
    setup_logging()
    logger = logging.getLogger()
    assert logger.level == logging.INFO

def test_setup_logging_handlers():
    """Test that setup_logging attaches the correct handlers."""
    setup_logging()
    logger = logging.getLogger()
    assert len(logger.handlers) > 0
    
    # Check if there is at least a stream handler (console)
    has_stream_handler = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    assert has_stream_handler is True
