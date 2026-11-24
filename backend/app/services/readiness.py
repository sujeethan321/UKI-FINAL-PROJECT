# Purpose: Probe database readiness with bounded waiting so health checks do not block indefinitely.
"""One bounded readiness worker per process; timed-out probes never queue up."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.core.database import DATABASE_URL, connection_options

options = connection_options(settings)
options.update(connect_timeout=settings.READINESS_DB_TIMEOUT_SECONDS,
               read_timeout=settings.READINESS_DB_TIMEOUT_SECONDS,
               write_timeout=settings.READINESS_DB_TIMEOUT_SECONDS)
probe_engine = create_engine(DATABASE_URL, poolclass=NullPool, hide_parameters=True,
                             echo=False, connect_args=options)


# Query database available data for the readiness workflow.
def database_available():
    # No application session/pool checkout, schema scan, data mutation or migration.
    with probe_engine.connect() as connection:
        return connection.scalar(text('SELECT 1')) == 1


# Group the state and operations for readiness probe in the readiness module.
class ReadinessProbe:
    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self, operation, timeout=3):
        self.operation, self.timeout = operation, timeout
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='readiness')
        self.busy = threading.Lock()

    # Run a bounded database probe while preventing overlapping readiness work.
    async def check(self):
        if not self.busy.acquire(blocking=False):
            return False
        try:
            future = self.executor.submit(self.operation)
        except Exception:
            self.busy.release()
            return False
        future.add_done_callback(lambda _: self.busy.release())
        try:
            return bool(await asyncio.wait_for(asyncio.wrap_future(future), self.timeout))
        except Exception:
            # Never log raw driver errors or propagate credentials to responses.
            return False


probe = ReadinessProbe(database_available, settings.READINESS_TIMEOUT_SECONDS)
