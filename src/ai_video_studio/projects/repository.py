import os
import tempfile
import threading
from pathlib import Path

from ai_video_studio.domain.models import PipelineCheckpoint, StudioProject


class ProjectRepository:
    filename = "project.json"
    _locks_guard = threading.Lock()
    _project_locks: dict[Path, threading.RLock] = {}

    def create(self, project: StudioProject) -> None:
        project.root_dir.mkdir(parents=True, exist_ok=False)
        for directory in ("cache", "audio", "exports", "logs"):
            (project.root_dir / directory).mkdir()
        self.save(project)

    def save(self, project: StudioProject) -> None:
        root_dir = project.root_dir
        with self._lock_for(root_dir):
            target = root_dir / self.filename
            self._merge_persisted_checkpoints(project, target)
            temporary = self._temporary_path(root_dir)
            try:
                self._write_temp(temporary, project.model_dump_json(indent=2))
                os.replace(temporary, target)
            finally:
                self._remove_temporary(temporary)

    def load(self, root_dir: Path) -> StudioProject:
        root_dir = Path(root_dir)
        payload = (root_dir / self.filename).read_text(encoding="utf-8")
        project = StudioProject.model_validate_json(payload)
        return project.model_copy(update={"root_dir": root_dir})

    @classmethod
    def _lock_for(cls, root_dir: Path) -> threading.RLock:
        key = root_dir.resolve()
        with cls._locks_guard:
            return cls._project_locks.setdefault(key, threading.RLock())

    def _merge_persisted_checkpoints(self, project: StudioProject, target: Path) -> None:
        if not target.exists():
            return

        persisted = StudioProject.model_validate_json(target.read_text(encoding="utf-8"))
        previous_by_stage = {checkpoint.stage: checkpoint for checkpoint in persisted.checkpoints}
        requested_stages = {checkpoint.stage for checkpoint in project.checkpoints}
        merged = [
            self._merge_checkpoint(checkpoint, previous_by_stage.get(checkpoint.stage))
            for checkpoint in project.checkpoints
        ]
        merged.extend(
            checkpoint
            for checkpoint in persisted.checkpoints
            if checkpoint.stage not in requested_stages
        )
        project.checkpoints = merged

    @staticmethod
    def _merge_checkpoint(
        requested: PipelineCheckpoint, persisted: PipelineCheckpoint | None
    ) -> PipelineCheckpoint:
        if persisted is None:
            return requested

        merged = requested.model_copy(deep=True)
        merged.completed_segment_ids.update(persisted.completed_segment_ids)
        return merged

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
