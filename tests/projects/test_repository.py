from pathlib import Path

from ai_video_studio.domain.languages import LanguageCode
from ai_video_studio.domain.models import ProjectSettings, StudioProject
from ai_video_studio.pipeline.state import PipelineCheckpoint, StageName, StageStatus
from ai_video_studio.projects.repository import ProjectRepository


def project_at(root: Path) -> StudioProject:
    return StudioProject(
        id="p1",
        name="Demo",
        root_dir=root,
        source_media=root.parent / "input.mp4",
        settings=ProjectSettings(source_language=LanguageCode.VI, target_language=LanguageCode.EN),
        checkpoints=[
            PipelineCheckpoint(
                stage=StageName.TRANSLATED,
                status=StageStatus.SUCCEEDED,
                completed_segment_ids={"s1"},
            )
        ],
    )


def test_save_and_load_round_trip(tmp_path: Path):
    repo = ProjectRepository()
    original = project_at(tmp_path / "demo")

    repo.create(original)

    loaded = repo.load(original.root_dir)
    assert loaded == original
    assert (original.root_dir / "project.json").exists()
    assert (original.root_dir / "exports").is_dir()


def test_save_leaves_no_partial_file(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")

    repo.create(project)

    assert not (project.root_dir / "project.json.tmp").exists()


def test_checkpoint_round_trip_preserves_completed_segments(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")

    repo.create(project)

    checkpoint = repo.load(project.root_dir).checkpoints[0]
    assert checkpoint.status == StageStatus.SUCCEEDED
    assert checkpoint.completed_segment_ids == {"s1"}
