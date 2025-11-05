"""Retry logic with exponential backoff."""
import time
import asyncio
from typing import Callable, Any, Optional
from app.config import settings


class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, max_retries: Optional[int] = None, backoff_multiplier: Optional[float] = None):
        self.max_retries = max_retries or settings.max_retries
        self.backoff_multiplier = backoff_multiplier or settings.retry_backoff_multiplier
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[Any, bool, Optional[str]]:
        """Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Tuple of (result, success, error_message)
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return result, True, None
            except Exception as e:
                last_error = str(e)
                
                if attempt < self.max_retries:
                    # Calculate backoff delay
                    delay = (self.backoff_multiplier ** attempt)
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    return None, False, last_error
        
        return None, False, last_error
    
    def execute_with_retry_sync(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[Any, bool, Optional[str]]:
        """Execute function with retry logic (synchronous version).
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Tuple of (result, success, error_message)
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                return result, True, None
            except Exception as e:
                last_error = str(e)
                
                if attempt < self.max_retries:
                    # Calculate backoff delay
                    delay = (self.backoff_multiplier ** attempt)
                    time.sleep(delay)
                else:
                    # All retries exhausted
                    return None, False, last_error
        
        return None, False, last_error

