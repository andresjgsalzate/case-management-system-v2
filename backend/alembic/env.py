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
# Phase 3
from backend.src.modules.classification.infrastructure.models import CaseClassificationModel, ClassificationRuleModel, ClassificationCriterionModel, ClassificationThresholdModel
from backend.src.modules.sla.infrastructure.models import SLAPolicyModel, SLARecordModel, SLAHolidayModel, SLAWorkScheduleModel
# Phase 4
from backend.src.modules.chat.infrastructure.models import ChatMessageModel
from backend.src.modules.notes.infrastructure.models import CaseNoteModel
from backend.src.modules.attachments.infrastructure.models import CaseAttachmentModel
from backend.src.modules.todos.infrastructure.models import CaseTodoModel
from backend.src.modules.time_entries.infrastructure.models import TimeEntryModel, ActiveTimerModel
# Phase 5
from backend.src.modules.dispositions.infrastructure.models import DispositionCategoryModel, DispositionModel
# Phase 6
from backend.src.modules.knowledge_base.infrastructure.models import (
    KBTagModel, KBArticleModel, KBArticleTagModel,
    KBArticleVersionModel, KBReviewEventModel, KBFavoriteModel, KBFeedbackModel,
)
# Phase 7
from backend.src.modules.notifications.infrastructure.models import NotificationModel, NotificationTemplateModel
from backend.src.modules.audit.infrastructure.models import AuditLogModel
from backend.src.modules.automation.infrastructure.models import AutomationRuleModel
from backend.src.modules.tenants.infrastructure.models import TenantModel

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
