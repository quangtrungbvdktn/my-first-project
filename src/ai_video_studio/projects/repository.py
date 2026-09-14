import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from ai_video_studio.domain.models import StudioProject
from ai_video_studio.pipeline.state import PipelineCheckpoint, StageName, StageStatus


class StaleProjectError(RuntimeError):
    """Raised when a full-project save would overwrite a newer revision."""


ProjectMutation = Callable[[StudioProject], StudioProject | None]


class ProjectRepository:
    filename = "project.json"
    _locks_guard: ClassVar[threading.Lock] = threading.Lock()
    _project_locks: ClassVar[dict[Path, threading.RLock]] = {}

    def create(self, project: StudioProject) -> None:
        project.root_dir.mkdir(parents=True, exist_ok=False)
        for directory in ("cache", "audio", "exports", "logs"):
            (project.root_dir / directory).mkdir()
        self.save(project)

    def save(self, project: StudioProject) -> None:
        with self._lock_for(project.root_dir):
            self._save_locked(project, expected_revision=project.revision)

    def update(self, root_dir: Path, mutation: ProjectMutation) -> StudioProject:
        root_dir = Path(root_dir)
        with self._lock_for(root_dir):
            current = self._load_from_target(root_dir / self.filename)
            updated = mutation(current) or current
            if updated.root_dir != root_dir:
                updated = updated.model_copy(update={"root_dir": root_dir})
            self._save_locked(updated, expected_revision=current.revision)
            return updated

    def complete_checkpoint_segments(
        self, root_dir: Path, stage: StageName, segment_ids: set[str]
    ) -> StudioProject:
        def complete(project: StudioProject) -> None:
            self._checkpoint(project, stage).completed_segment_ids.update(segment_ids)

        return self.update(root_dir, complete)

    def invalidate_checkpoint(self, root_dir: Path, stage: StageName) -> StudioProject:
        def invalidate(project: StudioProject) -> None:
            checkpoint = self._checkpoint(project, stage)
            checkpoint.status = StageStatus.PENDING
            checkpoint.completed_segment_ids.clear()
            checkpoint.error_code = None
            checkpoint.error_message = None

        return self.update(root_dir, invalidate)

    def load(self, root_dir: Path) -> StudioProject:
        root_dir = Path(root_dir)
        return self._load_from_target(root_dir / self.filename)

    @classmethod
    def _lock_for(cls, root_dir: Path) -> threading.RLock:
        key = root_dir.resolve()
        with cls._locks_guard:
            return cls._project_locks.setdefault(key, threading.RLock())

    @staticmethod
    def _checkpoint(project: StudioProject, stage: StageName) -> PipelineCheckpoint:
        for checkpoint in project.checkpoints:
            if checkpoint.stage == stage:
                return checkpoint
        raise ValueError(f"checkpoint not found for stage {stage}")

    def _save_locked(self, project: StudioProject, expected_revision: int) -> None:
        target = project.root_dir / self.filename
        if target.exists():
            persisted = self._load_from_target(target)
            if persisted.revision != expected_revision:
                raise StaleProjectError(
                    f"project revision {expected_revision} is stale; current revision is {persisted.revision}"
                )
        elif expected_revision != 0:
            raise StaleProjectError("project file is missing for a non-initial revision")

        if project.revision != expected_revision:
            raise StaleProjectError("project revision changed during the save operation")

        saved = project.model_copy(update={"revision": expected_revision + 1})
        self._write_atomic(target, saved.model_dump_json(indent=2))
        project.revision = saved.revision

    def _load_from_target(self, target: Path) -> StudioProject:
        payload = target.read_text(encoding="utf-8")
        project = StudioProject.model_validate_json(payload)
        return project.model_copy(update={"root_dir": target.parent})

    def _write_atomic(self, target: Path, payload: str) -> None:
        temporary = self._temporary_path(target.parent)
        try:
            self._write_temp(temporary, payload)
            os.replace(temporary, target)
        finally:
            self._remove_temporary(temporary)

    def _temporary_path(self, root_dir: Path) -> Path:
        descriptor, path = tempfile.mkstemp(
            prefix=f".{self.filename}.",
            suffix=".tmp",
            dir=root_dir,
        )
        os.close(descriptor)
        return Path(path)

    @staticmethod
    def _write_temp(temporary: Path, payload: str) -> None:
        with temporary.open("w", encoding="utf-8") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())

    @staticmethod
    def _remove_temporary(temporary: Path) -> None:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
