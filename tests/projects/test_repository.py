from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import copytree

import pytest
from pydantic import ValidationError

import ai_video_studio.projects.repository as repository_module
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


def test_save_replaces_existing_project_json(tmp_path: Path):
    repo = ProjectRepository()
    project = project_at(tmp_path / "demo")
    repo.create(project)
    project.name = "Updated"

    repo.save(project)

    assert repo.load(project.root_dir).name == "Updated"


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

    checkpoint = repo.load(project.root_dir).checkpoints[0]
    assert checkpoint.status == StageStatus.SUCCEEDED
    assert checkpoint.completed_segment_ids == {"s1"}


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


def test_overlapping_saves_merge_completed_checkpoint_segments(tmp_path: Path):
    creator = ProjectRepository()
    project = project_at(tmp_path / "demo")
    creator.create(project)

    first = creator.load(project.root_dir)
    second = creator.load(project.root_dir)
    first.checkpoints[0].completed_segment_ids.add("s2")
    second.checkpoints[0].completed_segment_ids.add("s3")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(ProjectRepository().save, candidate)
            for candidate in (first, second)
        ]
        for future in futures:
            future.result()

    checkpoint = creator.load(project.root_dir).checkpoints[0]
    assert checkpoint.completed_segment_ids == {"s1", "s2", "s3"}
