
from logging.config import fileConfig

from alembic import context

from app.core.database import (
    Base,
    DATABASE_URL,
    engine,
)

# Import all models so Alembic can discover them.
import app.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline():
    """Generate SQL without connecting to MySQL."""

    context.configure(
        url=DATABASE_URL.render_as_string(
            hide_password=False
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations using our existing engine."""

    supplied = config.attributes.get('connection')
    if supplied is not None:
        # Dedicated clean/legacy verification only. Never bypass normal settings
        # to migrate a development or production target through this test hook.
        from app.core.config import settings
        from app.core.db_maintenance import validate_target, verify_identity
        target = validate_target(settings.APP_ENV, supplied.engine.url.database, 'migration')
        verify_identity(supplied, target)
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
