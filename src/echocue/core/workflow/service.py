"""Workflow domain services."""

from uuid import UUID

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from echocue.shared import CustomService

from .model import WorkflowRunsModel
from .schema import WorkflowRunStruct

__all__ = ("WorkflowRunService",)


class WorkflowRunService(CustomService[WorkflowRunsModel]):
    """Workflow run database service."""

    class _Repository(SQLAlchemyAsyncRepository[WorkflowRunsModel]):
        """Workflow run model repository."""

        model_type: type[WorkflowRunsModel] = WorkflowRunsModel

    repository_type = _Repository

    async def get_by_id(self, workflow_run_id: UUID) -> WorkflowRunStruct | None:
        """Get a workflow run by primary key."""

        workflow_run = await self.get_one_or_none(id=workflow_run_id)

        return workflow_run.to_struct() if workflow_run else None
