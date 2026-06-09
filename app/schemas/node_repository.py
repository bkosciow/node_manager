"""Pydantic schemas for NodeRepository (repo-to-node assignments)."""

from datetime import datetime

from pydantic import BaseModel


class RepoAssignmentCreate(BaseModel):
    repository_id: int


class RepoAssignmentResponse(BaseModel):
    id: int
    device_id: int
    repository_id: int
    repo_type: str
    assigned_at: datetime

    model_config = {"from_attributes": True}
