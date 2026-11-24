# Purpose: Create the shared SQLAlchemy engine and request-scoped sessions, applying the configured database TLS policy.

import ssl

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# Build the URL structurally so special characters in database credentials are escaped correctly.
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=settings.MYSQL_USER,
    password=settings.MYSQL_PASSWORD,
    host=settings.MYSQL_HOST,
    port=settings.MYSQL_PORT,
    database=settings.MYSQL_DATABASE,
)


def connection_options(config):
    """Preserve verified TLS; explicitly require encryption for local viva data."""
    options = {"connect_timeout": getattr(config, 'MYSQL_CONNECT_TIMEOUT_SECONDS', 5)}
    if getattr(config, 'MYSQL_TLS_MODE', 'default') == 'local_viva_required' or getattr(config,'MYSQL_DATABASE',None) == 'lankapex_viva_db':
        # Defense in depth for callers supplying an object other than Settings.
        if (config.APP_ENV != 'development' or config.MYSQL_HOST != '127.0.0.1'
                or config.MYSQL_PORT != 3306
                or config.MYSQL_DATABASE != 'lankapex_viva_db'
                ):
            raise ValueError('Local viva TLS requires the exact approved target')
        from app.core.viva_tls import context
        options['ssl'] = context(config.MYSQL_SSL_CA)
    elif config.APP_ENV == "production" or config.MYSQL_SSL_CA is not None:
        options['ssl'] = ssl.create_default_context(cafile=config.MYSQL_SSL_CA)
    return options


# Reuse pooled connections, check stale connections before use, and avoid echoing SQL parameters into logs.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
    hide_parameters=True,
    connect_args=connection_options(settings),
)

if DATABASE_URL.database == 'lankapex_viva_db':
    @event.listens_for(engine,'connect')
    def verify_viva_peer(dbapi_connection,connection_record):
        from app.core.viva_tls import verify_socket
        verify_socket(getattr(dbapi_connection,'_sock',None))


# Leave flush/commit decisions explicit so services and routers control transaction boundaries.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Group the state and operations for base in the database module.
class Base(DeclarativeBase):
    pass


# Yield one database session per dependency scope and close it even when the request fails.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        # Return the connection to the pool even if endpoint validation or application processing raises.
        db.close()
