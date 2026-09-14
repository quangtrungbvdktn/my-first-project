from pathlib import Path

from pydantic import BaseModel, Field, computed_field, model_validator

from ai_video_studio.domain.languages import LanguageCode
from ai_video_studio.pipeline.state import PipelineCheckpoint


class Segment(BaseModel):
    id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    speaker_id: str | None = None
    source_text: str
    translated_text: str = ""

    @model_validator(mode="after")
    def timing_is_forward(self) -> "Segment":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class Speaker(BaseModel):
    id: str
    display_name: str
    color: str = "#8B5CF6"
    voice_provider: str | None = None
    voice_id: str | None = None


class ProjectSettings(BaseModel):
    source_language: LanguageCode = LanguageCode.AUTO
    target_language: LanguageCode
    allow_paid_models: bool = False


class StudioProject(BaseModel):
    id: str
    name: str
    root_dir: Path
    source_media: Path
    settings: ProjectSettings
    segments: list[Segment] = Field(default_factory=list)
    speakers: list[Speaker] = Field(default_factory=list)
    checkpoints: list[PipelineCheckpoint] = Field(default_factory=list)

    @computed_field
    @property
    def export_dir(self) -> Path:
        return self.root_dir / "exports"
