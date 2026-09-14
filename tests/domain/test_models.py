from pathlib import Path

from pydantic import ValidationError
import pytest

from ai_video_studio.domain.languages import LanguageCode
from ai_video_studio.domain.models import ProjectSettings, Segment, StudioProject


def test_supported_primary_language_codes():
    assert {code.value for code in LanguageCode} >= {"vi", "en", "zh-CN", "zh-TW"}


def test_segment_rejects_backwards_timing():
    with pytest.raises(ValidationError):
        Segment(id="s1", start_ms=2000, end_ms=1000, source_text="Xin chào")


def test_project_keeps_source_as_read_only_reference(tmp_path: Path):
    source = tmp_path / "source.mp4"
    project = StudioProject(
        id="p1",
        name="Demo",
        root_dir=tmp_path / "project",
        source_media=source,
        settings=ProjectSettings(source_language=LanguageCode.VI, target_language=LanguageCode.EN),
    )
    assert project.source_media == source
    assert project.export_dir != source.parent
