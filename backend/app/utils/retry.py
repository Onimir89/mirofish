"""Retry with exponential backoff."""
import time
import logging

logger = logging.getLogger(__name__)


def retry_with_backoff(fn, max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,)):
    """Call fn with exponential backoff on failure."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except exceptions as e:
            if attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Attempt {attempt+1} failed: {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
