from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.gmail.models  # noqa: F401
import app.printing.models  # noqa: F401
from app.config import get_settings
from app.db import Base

config = context.config

# The test suite sets configure_logger=False so migrations do not replace the app's logging.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

# Import every models module here so autogenerate can see its tables.
target_metadata = Base.metadata

database_url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
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
