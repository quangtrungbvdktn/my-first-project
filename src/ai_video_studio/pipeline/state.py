from enum import StrEnum

from pydantic import BaseModel, Field


class StageName(StrEnum):
    IMPORTED = "imported"
    TRANSCRIBED = "transcribed"
    TRANSLATED = "translated"
    SYNTHESIZED = "synthesized"
    EXPORTED = "exported"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineCheckpoint(BaseModel):
    stage: StageName
    status: StageStatus = StageStatus.PENDING
    completed_segment_ids: set[str] = Field(default_factory=set)
    error_code: str | None = None
    error_message: str | None = None
