# Purpose: Reserve bounded local AI generation budgets before dispatching provider work.
"""Per-process admission only, NOT a global multi-worker quota.

Counts attempts, including failures/ambiguous outcomes; never refunds or retries.
An external shared limiter and provider spend controls require operator review.
"""
import threading
import time
from contextlib import contextmanager
from app.integrations.ai.base import AIClientError,AIFailureCategory

# Group the state and operations for local generation budget in the limits module.
class LocalGenerationBudget:
    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self):
        self.lock=threading.Lock();self.active=0;self.count=0;self.started=time.monotonic()

    # Reserve generation capacity under the local budget before the provider request is dispatched.
    @contextmanager
    def reserve(self,config):
        with self.lock:
            now=time.monotonic()
            if now-self.started>=getattr(config,'AI_USAGE_WINDOW_SECONDS',3600):self.started=now;self.count=0
            if self.active>=getattr(config,'AI_MAX_CONCURRENT_GENERATIONS',2) or self.count>=getattr(config,'AI_MAX_GENERATIONS_PER_WINDOW',60):
                raise AIClientError(AIFailureCategory.RATE_LIMITED)
            self.active+=1;self.count+=1
        try:yield
        finally:
            with self.lock:self.active-=1

budget=LocalGenerationBudget()
