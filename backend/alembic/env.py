import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Add project root to sys.path so "backend.src.core" imports work
# (Alembic runs from backend/, so we go up one level to the repo root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.core.config import get_settings
from backend.src.core.database import Base

# Import all models so Alembic can detect them
from backend.src.modules.roles.infrastructure.models import RoleModel, PermissionModel
from backend.src.modules.teams.infrastructure.models import TeamModel, TeamMemberModel
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.auth.infrastructure.models import UserSessionModel
# Phase 2
from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
from backend.src.modules.applications.infrastructure.models import ApplicationModel
from backend.src.modules.origins.infrastructure.models import OriginModel
from backend.src.modules.cases.infrastructure.models import CaseNumberSequenceModel, CaseModel
from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
from backend.src.modules.activity.infrastructure.models import ActivityEntryModel

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata from our models
target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
