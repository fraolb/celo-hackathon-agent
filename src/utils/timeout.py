"""
Timeout utilities for function execution.
"""

import signal
from typing import Callable, Any


class TimeoutError(Exception):
    """Raised when a function execution times out."""
    pass


class GitHubAccessError(Exception):
    """Raised when there's an issue accessing the GitHub API."""
    pass


class AIAnalysisError(Exception):
    """Raised when there's an issue with AI-based analysis."""
    pass


class RepositoryAnalysisError(Exception):
    """Raised when there's an issue analyzing a repository."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for function timeouts."""
    raise TimeoutError("Function execution timed out")


def with_timeout(seconds: int):
    """
    Decorator to add timeout functionality to functions.
    
    Args:
        seconds: Number of seconds before timing out
        
    Returns:
        Decorated function with timeout capability
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            # Set the timeout handler (only works on Unix systems)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Disable the alarm
                return result
            except TimeoutError:
                print(f"Function {func.__name__} timed out after {seconds} seconds")
                return None
            finally:
                signal.alarm(0)  # Ensure the alarm is disabled
        return wrapper
    return decorator