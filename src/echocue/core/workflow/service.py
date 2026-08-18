"""Workflow domain services."""

from uuid import UUID

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from echocue.shared import CustomService

from .model import WorkflowRuns
from .schema import WorkflowRunStruct

__all__ = ("WorkflowRunService",)


class WorkflowRunService(CustomService[WorkflowRuns]):
    """Workflow run database service."""

    class _Repository(SQLAlchemyAsyncRepository[WorkflowRuns]):
        """Workflow run model repository."""

        model_type: type[WorkflowRuns] = WorkflowRuns

    repository_type = _Repository

    async def get_by_id(self, workflow_run_id: UUID) -> WorkflowRunStruct | None:
        """Get a workflow run by primary key."""

        workflow_run = await self.get_one_or_none(id=workflow_run_id)

        return workflow_run.to_struct() if workflow_run else None
