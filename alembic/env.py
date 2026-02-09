"""Alembic environment configuration.

Uses render_as_batch=True for SQLite ALTER TABLE support.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure project root is on sys.path so ``from src.models_sa`` works.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models_sa import metadata  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def _include_object(obj, name, type_, reflected, compare_to):
    """Filter out SQLite FK reflection noise for autogenerate.

    SQLite doesn't reflect ON DELETE CASCADE, causing Alembic to see
    every FK as needing recreation.  Skip FK comparison entirely.
    """
    if type_ == "foreign_key_constraint":
        return False
    return True


def _compare_type(ctx, inspected_column, metadata_column, inspected_type, metadata_type):
    """Suppress false type diffs caused by SQLite reflection."""
    return False


def _filter_autogenerate(context, revision, directives):
    """Remove false-positive modify_nullable ops from SQLite PK reflection.

    SQLite reflects PRIMARY KEY columns as nullable=True, which disagrees
    with SQLAlchemy metadata (primary_key=True implies nullable=False).
    """
    from alembic.operations.ops import AlterColumnOp, ModifyTableOps

    if not directives:
        return
    script = directives[0]
    if script.upgrade_ops is None:
        return

    def keep(op):
        if isinstance(op, ModifyTableOps):
            op.ops = [o for o in op.ops if keep(o)]
            return bool(op.ops)
        if isinstance(op, AlterColumnOp) and op.modify_nullable is not None:
            return False
        return True

    script.upgrade_ops.ops = [
        op for op in script.upgrade_ops.ops if keep(op)
    ]


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=_compare_type,
        include_object=_include_object,
        process_revision_directives=_filter_autogenerate,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect and apply."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=_compare_type,
            include_object=_include_object,
            process_revision_directives=_filter_autogenerate,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
