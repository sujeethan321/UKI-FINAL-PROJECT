
import ssl

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


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
    if getattr(config, 'MYSQL_TLS_MODE', 'default') == 'local_viva_required':
        # Defense in depth for callers supplying an object other than Settings.
        if (config.APP_ENV != 'development' or config.MYSQL_HOST != '127.0.0.1'
                or config.MYSQL_PORT != 3306
                or config.MYSQL_DATABASE != 'lankapex_viva_db'
                or config.MYSQL_SSL_CA is not None):
            raise ValueError('Local viva TLS requires the exact approved target')
        # Synthetic local demonstration only: encryption without server identity.
        # An explicit context makes installed PyMySQL require TLS, not PREFERRED.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        options['ssl'] = context
    elif config.APP_ENV == "production" or config.MYSQL_SSL_CA is not None:
        options['ssl'] = ssl.create_default_context(cafile=config.MYSQL_SSL_CA)
    return options


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
    hide_parameters=True,
    connect_args=connection_options(settings),
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
