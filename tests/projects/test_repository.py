from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import copytree

import pytest
from pydantic import ValidationError

import ai_video_studio.projects.repository as repository_module
from ai_video_studio.domain.languages import LanguageCode
from ai_video_studio.domain.models import ProjectSettings, StudioProject
from ai_video_studio.pipeline.state import PipelineCheckpoint, StageName, StageStatus
from ai_video_studio.projects.repository import ProjectRepository, StaleProjectError


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


def checkpoint(project: StudioProject, stage: StageName) -> PipelineCheckpoint:
    return next(item for item in project.checkpoints if item.stage == stage)


def test_save_and_load_round_trip(tmp_path: Path):
    repo = ProjectRepository()
    original = project_at(tmp_path / "demo")

    repo.create(original)

    loaded = repo.load(original.root_dir)
    assert loaded == original
    assert (original.root_dir / "project.json").exists()
    assert (original.root_dir / "exports").is_dir()


def test_save_replaces_existing_project_json(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    project.name = "Updated"

    repo.save(project)

    assert repo.load(project.root_dir).name == "Updated"


def test_save_allows_checkpoint_invalidation_to_clear_completed_segments(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    invalidated = repo.load(project.root_dir)
    stage = checkpoint(invalidated, StageName.TRANSLATED)
    stage.status = StageStatus.PENDING
    stage.completed_segment_ids.clear()
    stage.error_code = None
    stage.error_message = None

    repo.save(invalidated)

    saved = checkpoint(repo.load(project.root_dir), StageName.TRANSLATED)
    assert saved.status == StageStatus.PENDING
    assert saved.completed_segment_ids == set()


def test_stale_full_project_save_is_rejected(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    first = repo.load(project.root_dir)
    stale = repo.load(project.root_dir)
    first.name = "First update"

    repo.save(first)

    stale.name = "Stale update"
    with pytest.raises(StaleProjectError):
        repo.save(stale)

    assert repo.load(project.root_dir).name == "First update"


def test_temp_write_failure_preserves_existing_json(monkeypatch, tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    original_payload = (project.root_dir / "project.json").read_text(encoding="utf-8")

    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(repo, "_write_temp", fail_write)
    with pytest.raises(OSError, match="disk full"):
        repo.save(project)

    assert (project.root_dir / "project.json").read_text(encoding="utf-8") == original_payload
    assert not list(project.root_dir.glob(".project.json.*.tmp"))


def test_replace_failure_preserves_existing_json_and_cleans_temp(monkeypatch, tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    original_payload = (project.root_dir / "project.json").read_text(encoding="utf-8")

    def fail_replace(*_args, **_kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        repo.save(project)

    assert (project.root_dir / "project.json").read_text(encoding="utf-8") == original_payload
    assert not list(project.root_dir.glob(".project.json.*.tmp"))


def test_load_uses_opened_directory_as_project_root(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    copied_root = tmp_path / "copied"
    copytree(project.root_dir, copied_root)

    loaded = repo.load(copied_root)
    loaded.name = "Copied"

    repo.save(loaded)

    assert loaded.root_dir == copied_root
    assert repo.load(copied_root).name == "Copied"
    assert repo.load(project.root_dir).name == "Demo"


def test_checkpoint_round_trip_preserves_completed_segments(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")

    repo.create(project)

    loaded = repo.load(project.root_dir)
    assert checkpoint(loaded, StageName.TRANSLATED).status == StageStatus.SUCCEEDED
    assert checkpoint(loaded, StageName.TRANSLATED).completed_segment_ids == {"s1"}


def test_project_rejects_duplicate_checkpoint_stages(tmp_path: Path):
    with pytest.raises(ValidationError, match="checkpoint stages must be unique"):
        StudioProject(
            id="p1",
            name="Demo",
            root_dir=tmp_path / "demo",
            source_media=tmp_path / "input.mp4",
            settings=ProjectSettings(target_language=LanguageCode.EN),
            checkpoints=[
                PipelineCheckpoint(stage=StageName.TRANSLATED),
                PipelineCheckpoint(stage=StageName.TRANSLATED),
            ],
        )


def test_explicit_segment_completion_unions_completed_ids(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)

    repo.complete_checkpoint_segments(project.root_dir, StageName.TRANSLATED, {"s2"})
    repo.complete_checkpoint_segments(project.root_dir, StageName.TRANSLATED, {"s3"})

    saved = checkpoint(repo.load(project.root_dir), StageName.TRANSLATED)
    assert saved.completed_segment_ids == {"s1", "s2", "s3"}


def test_invalidate_checkpoint_explicitly_clears_completion(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)

    repo.invalidate_checkpoint(project.root_dir, StageName.TRANSLATED)

    saved = checkpoint(repo.load(project.root_dir), StageName.TRANSLATED)
    assert saved.status == StageStatus.PENDING
    assert saved.completed_segment_ids == set()


def test_transactional_updates_preserve_concurrent_status_and_error_changes(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    project.checkpoints.append(PipelineCheckpoint(stage=StageName.SYNTHESIZED))
    repo.create(project)

    def fail_translation(current: StudioProject) -> None:
        stage = checkpoint(current, StageName.TRANSLATED)
        stage.status = StageStatus.FAILED
        stage.error_code = "quota"
        stage.error_message = "Quota exhausted"

    def cancel_synthesis(current: StudioProject) -> None:
        stage = checkpoint(current, StageName.SYNTHESIZED)
        stage.status = StageStatus.CANCELLED
        stage.error_code = "cancelled"
        stage.error_message = "Cancelled by user"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(repo.update, project.root_dir, mutation)
            for mutation in (fail_translation, cancel_synthesis)
        ]
        for future in futures:
            future.result()

    saved = repo.load(project.root_dir)
    translated = checkpoint(saved, StageName.TRANSLATED)
    synthesized = checkpoint(saved, StageName.SYNTHESIZED)
    assert (translated.status, translated.error_code) == (StageStatus.FAILED, "quota")
    assert (synthesized.status, synthesized.error_code) == (StageStatus.CANCELLED, "cancelled")
