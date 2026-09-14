from pathlib import Path

from ai_video_studio.domain.models import StudioProject


class ProjectRepository:
    filename = "project.json"

    def create(self, project: StudioProject) -> None:
        project.root_dir.mkdir(parents=True, exist_ok=False)
        for directory in ("cache", "audio", "exports", "logs"):
            (project.root_dir / directory).mkdir()
        self.save(project)

    def save(self, project: StudioProject) -> None:
        target = project.root_dir / self.filename
        temporary = project.root_dir / f"{self.filename}.tmp"
        temporary.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def load(self, root_dir: Path) -> StudioProject:
        payload = (root_dir / self.filename).read_text(encoding="utf-8")
        return StudioProject.model_validate_json(payload)
