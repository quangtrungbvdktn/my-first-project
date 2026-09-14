# Phase 1 — Foundation and Quick Dub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable Windows-oriented desktop shell and a testable Quick Dub vertical slice that creates a local project, discovers free OpenRouter models, translates segments, generates draft speech, and persists resumable pipeline state.

**Architecture:** Build a small Python package with domain models isolated from PySide6 and provider code. All external processes and HTTP calls sit behind protocols so the orchestration layer remains deterministic under tests. Phase 1 uses JSON project storage and simulated media stages; production FFmpeg/Whisper processing follows in Phase 2.

**Tech Stack:** Python 3.11+, PySide6 6.7+, Pydantic 2.8+, httpx 0.27+, keyring 25+, pytest 8+, pytest-asyncio 0.23+, respx 0.21+, Ruff 0.6+

**Spec:** `docs/superpowers/specs/2026-09-14-ai-video-translator-design.md`

## Global Constraints

- Target Windows desktop systems without a required NVIDIA GPU.
- Primary languages are Vietnamese, English, Simplified Chinese, and Traditional Chinese.
- Never overwrite original media.
- Store API keys through Windows Credential Manager via `keyring`, never in project JSON or logs.
- Never silently route to a paid OpenRouter model.
- Standard TTS must not be labeled as voice cloning.
- Preserve completed pipeline stages after cancellation or restart.
- Keep provider implementations replaceable behind typed protocols.
- Retain the repository's existing sample files.

## Delivery sequence beyond this plan

1. Phase 1: foundation and Quick Dub vertical slice — this plan.
2. Phase 2: FFmpeg, Faster-Whisper CPU, diarization, source separation, and timing.
3. Phase 3: Quick Video Tools, subtitle-preserving transforms, overlays, watermark, metadata removal, and batch presets.
4. Phase 4: Studio transcript editor, speaker timeline, voice manager, preview, and invalidation.
5. Phase 5: authorized voice cloning, cloud lip-sync, experimental CPU fallbacks, export hardening, and Windows installer.

---

### Task 1: Python package, quality gates, and application entry point

**Files:**
- Create: `pyproject.toml`
- Create: `src/ai_video_studio/__init__.py`
- Create: `src/ai_video_studio/__main__.py`
- Create: `src/ai_video_studio/app.py`
- Create: `tests/test_app.py`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: none
- Produces: `ai_video_studio.app.build_app(argv: list[str]) -> QApplication`; `python -m ai_video_studio`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_app.py
from ai_video_studio.app import build_app


def test_build_app_sets_product_name(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = build_app([])
    assert app.applicationName() == "AI Video Translator & Dubbing Studio"
    app.quit()
```

- [ ] **Step 2: Run the test and verify import failure**

Run: `python -m pytest tests/test_app.py -q`  
Expected: FAIL with `ModuleNotFoundError: ai_video_studio`.

- [ ] **Step 3: Add package metadata and dependencies**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "ai-video-translator-studio"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "PySide6>=6.7,<7",
  "pydantic>=2.8,<3",
  "httpx>=0.27,<1",
  "keyring>=25,<26",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.23,<1",
  "respx>=0.21,<1",
  "ruff>=0.6,<1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/ai_video_studio"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100
```

- [ ] **Step 4: Implement the entry point**

```python
# src/ai_video_studio/app.py
from PySide6.QtWidgets import QApplication


def build_app(argv: list[str]) -> QApplication:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(argv)
    app.setApplicationName("AI Video Translator & Dubbing Studio")
    app.setOrganizationName("AI Video Studio")
    return app
```

```python
# src/ai_video_studio/__main__.py
import sys
from ai_video_studio.app import build_app


def main() -> int:
    app = build_app(sys.argv)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Add CI commands**

Configure `.github/workflows/ci.yml` on Windows and Ubuntu with Python 3.11 to run:

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest -q
```

- [ ] **Step 6: Run quality gates**

Run: `python -m ruff check . && python -m pytest -q`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src tests .github README.md
git commit -m "chore: bootstrap desktop application"
```

---

### Task 2: Project domain models and language rules

**Files:**
- Create: `src/ai_video_studio/domain/languages.py`
- Create: `src/ai_video_studio/domain/models.py`
- Create: `src/ai_video_studio/domain/__init__.py`
- Create: `tests/domain/test_models.py`

**Interfaces:**
- Consumes: Pydantic
- Produces: `LanguageCode`, `Segment`, `Speaker`, `ProjectSettings`, `StudioProject`

- [ ] **Step 1: Write failing language and project tests**

```python
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
```

- [ ] **Step 2: Run tests and verify missing domain modules**

Run: `python -m pytest tests/domain/test_models.py -q`  
Expected: FAIL on missing imports.

- [ ] **Step 3: Implement exact domain types**

```python
# src/ai_video_studio/domain/languages.py
from enum import StrEnum


class LanguageCode(StrEnum):
    AUTO = "auto"
    VI = "vi"
    EN = "en"
    ZH_CN = "zh-CN"
    ZH_TW = "zh-TW"
```

```python
# src/ai_video_studio/domain/models.py
from pathlib import Path
from pydantic import BaseModel, Field, computed_field, model_validator
from ai_video_studio.domain.languages import LanguageCode


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
    segments: list[Segment] = []
    speakers: list[Speaker] = []

    @computed_field
    @property
    def export_dir(self) -> Path:
        return self.root_dir / "exports"
```

- [ ] **Step 4: Run domain tests**

Run: `python -m pytest tests/domain/test_models.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_video_studio/domain tests/domain
git commit -m "feat: define project domain model"
```

---

### Task 3: Atomic project persistence and resumable stage state

**Files:**
- Create: `src/ai_video_studio/projects/repository.py`
- Create: `src/ai_video_studio/projects/__init__.py`
- Create: `src/ai_video_studio/pipeline/state.py`
- Create: `src/ai_video_studio/pipeline/__init__.py`
- Create: `tests/projects/test_repository.py`

**Interfaces:**
- Consumes: `StudioProject`
- Produces: `ProjectRepository.create(project)`, `save(project)`, `load(root_dir)`; `PipelineCheckpoint`

- [ ] **Step 1: Write failing persistence tests**

```python
from pathlib import Path
from ai_video_studio.domain.languages import LanguageCode
from ai_video_studio.domain.models import ProjectSettings, StudioProject
from ai_video_studio.projects.repository import ProjectRepository


def project_at(root: Path) -> StudioProject:
    return StudioProject(
        id="p1",
        name="Demo",
        root_dir=root,
        source_media=root.parent / "input.mp4",
        settings=ProjectSettings(source_language=LanguageCode.VI, target_language=LanguageCode.EN),
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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/projects/test_repository.py -q`  
Expected: FAIL on missing repository.

- [ ] **Step 3: Implement atomic JSON persistence**

```python
# src/ai_video_studio/projects/repository.py
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
```

- [ ] **Step 4: Define stage checkpoint types**

Create `StageName(StrEnum)` with `IMPORTED`, `TRANSCRIBED`, `TRANSLATED`, `SYNTHESIZED`, and `EXPORTED`. Create `StageStatus(StrEnum)` with `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, and `CANCELLED`. Define:

```python
class PipelineCheckpoint(BaseModel):
    stage: StageName
    status: StageStatus = StageStatus.PENDING
    completed_segment_ids: set[str] = set()
    error_code: str | None = None
    error_message: str | None = None
```

Add `checkpoints: list[PipelineCheckpoint] = []` to `StudioProject`.

- [ ] **Step 5: Run all tests**

Run: `python -m pytest -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_video_studio/projects src/ai_video_studio/pipeline src/ai_video_studio/domain tests
git commit -m "feat: persist resumable studio projects"
```

---

### Task 4: Secret storage and provider protocols

**Files:**
- Create: `src/ai_video_studio/providers/base.py`
- Create: `src/ai_video_studio/providers/secrets.py`
- Create: `src/ai_video_studio/providers/__init__.py`
- Create: `tests/providers/test_secrets.py`

**Interfaces:**
- Consumes: `LanguageCode`, `Segment`
- Produces: `TranslationProvider`, `SpeechProvider`, `ModelInfo`, `SecretStore`

- [ ] **Step 1: Write failing secret tests**

```python
from ai_video_studio.providers.secrets import SecretStore


class FakeKeyring:
    values: dict[tuple[str, str], str] = {}

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def get_password(self, service, username):
        return self.values.get((service, username))

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_openrouter_key_round_trip():
    store = SecretStore(backend=FakeKeyring())
    store.set("openrouter", "secret")
    assert store.get("openrouter") == "secret"
    store.delete("openrouter")
    assert store.get("openrouter") is None
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/providers/test_secrets.py -q`  
Expected: FAIL on missing module.

- [ ] **Step 3: Define provider contracts**

```python
# src/ai_video_studio/providers/base.py
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from ai_video_studio.domain.languages import LanguageCode
from ai_video_studio.domain.models import Segment


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]
    is_free: bool
    available: bool


class TranslationProvider(Protocol):
    async def translate(
        self,
        segments: list[Segment],
        source: LanguageCode,
        target: LanguageCode,
        glossary: dict[str, str],
    ) -> list[str]: ...


class SpeechProvider(Protocol):
    async def synthesize(
        self,
        text: str,
        language: LanguageCode,
        voice_id: str,
        output_path: Path,
    ) -> Path: ...
```

- [ ] **Step 4: Implement keyring-backed storage**

```python
# src/ai_video_studio/providers/secrets.py
import keyring


class SecretStore:
    service = "ai-video-translator-studio"

    def __init__(self, backend=keyring):
        self.backend = backend

    def set(self, provider: str, value: str) -> None:
        self.backend.set_password(self.service, provider, value)

    def get(self, provider: str) -> str | None:
        return self.backend.get_password(self.service, provider)

    def delete(self, provider: str) -> None:
        self.backend.delete_password(self.service, provider)
```

- [ ] **Step 5: Run tests and scan persisted models**

Run: `python -m pytest -q`  
Expected: PASS.

Run: `python -c "from ai_video_studio.domain.models import StudioProject; print(StudioProject.model_json_schema())"`  
Expected: schema contains no API key field.

- [ ] **Step 6: Commit**

```bash
git add src/ai_video_studio/providers tests/providers
git commit -m "feat: add secure provider boundaries"
```

---

### Task 5: OpenRouter free-model discovery and paid-route guard

**Files:**
- Create: `src/ai_video_studio/providers/openrouter/catalog.py`
- Create: `src/ai_video_studio/providers/openrouter/client.py`
- Create: `src/ai_video_studio/providers/openrouter/__init__.py`
- Create: `tests/providers/openrouter/test_catalog.py`
- Create: `tests/providers/openrouter/test_client.py`

**Interfaces:**
- Consumes: `ModelInfo`, OpenRouter API key
- Produces: `OpenRouterCatalog.free_models(output_modality)`; `OpenRouterClient.complete_json(...)`; `PaidModelBlocked`

- [ ] **Step 1: Write failing catalog filtering test**

```python
from ai_video_studio.providers.openrouter.catalog import OpenRouterCatalog


def test_audio_catalog_returns_only_available_free_models():
    payload = {
        "data": [
            {"id": "free-audio", "name": "Free Audio", "architecture": {
                "input_modalities": ["text"], "output_modalities": ["audio"]
            }, "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "paid-audio", "name": "Paid Audio", "architecture": {
                "input_modalities": ["text"], "output_modalities": ["audio"]
            }, "pricing": {"prompt": "0.001", "completion": "0.002"}},
            {"id": "free-text", "name": "Free Text", "architecture": {
                "input_modalities": ["text"], "output_modalities": ["text"]
            }, "pricing": {"prompt": "0", "completion": "0"}},
        ]
    }
    models = OpenRouterCatalog.from_payload(payload).free_models("audio")
    assert [model.id for model in models] == ["free-audio"]
```

- [ ] **Step 2: Write failing paid-route guard test**

```python
import pytest
from ai_video_studio.providers.openrouter.client import OpenRouterClient, PaidModelBlocked


@pytest.mark.asyncio
async def test_paid_model_is_blocked_before_network_call():
    client = OpenRouterClient(api_key="x", allow_paid_models=False)
    with pytest.raises(PaidModelBlocked):
        await client.complete_json(model_id="paid-model", is_free=False, messages=[])
```

- [ ] **Step 3: Run tests and verify failure**

Run: `python -m pytest tests/providers/openrouter -q`  
Expected: FAIL on missing implementation.

- [ ] **Step 4: Implement catalog parsing**

`OpenRouterCatalog.from_payload(payload)` maps every item to `ModelInfo`. Pricing is free only when both prompt and completion prices parse as decimal zero. `free_models(output_modality)` returns models where `is_free`, `available`, and the requested modality is present.

- [ ] **Step 5: Implement guarded HTTP client**

```python
class PaidModelBlocked(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, api_key: str, allow_paid_models: bool = False, transport=None):
        self.api_key = api_key
        self.allow_paid_models = allow_paid_models
        self.http = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )

    async def complete_json(self, model_id: str, is_free: bool, messages: list[dict]) -> dict:
        if not is_free and not self.allow_paid_models:
            raise PaidModelBlocked(model_id)
        response = await self.http.post(
            "/chat/completions",
            json={"model": model_id, "messages": messages, "response_format": {"type": "json_object"}},
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 6: Add mocked catalog/client success and quota tests**

Use `respx` to verify:

- Authorization header is present.
- `GET /models` is parsed.
- HTTP 429 is normalized to `ProviderQuotaError(provider="openrouter")`.
- The next free model can be selected after quota failure.
- No network request occurs for a blocked paid model.

- [ ] **Step 7: Run provider tests**

Run: `python -m pytest tests/providers/openrouter -q`  
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/ai_video_studio/providers/openrouter tests/providers/openrouter
git commit -m "feat: discover safe OpenRouter free models"
```

---

### Task 6: Translation service with glossary and free-model fallback

**Files:**
- Create: `src/ai_video_studio/services/translation.py`
- Create: `src/ai_video_studio/services/__init__.py`
- Create: `tests/services/test_translation.py`

**Interfaces:**
- Consumes: `OpenRouterCatalog`, `OpenRouterClient`, segments, language codes, glossary
- Produces: `TranslationService.translate_segments(request) -> list[TranslatedSegment]`

- [ ] **Step 1: Write failing fallback test**

```python
import pytest
from ai_video_studio.services.translation import TranslationRequest, TranslationService


@pytest.mark.asyncio
async def test_translation_falls_back_to_second_free_model(fake_client, two_free_text_models):
    fake_client.fail_quota_for.add(two_free_text_models[0].id)
    service = TranslationService(fake_client, two_free_text_models)
    result = await service.translate_segments(
        TranslationRequest(
            segments=[{"id": "s1", "text": "Xin chào"}],
            source="vi",
            target="en",
            glossary={"Codex": "Codex"},
        )
    )
    assert result[0].text == "Hello"
    assert fake_client.called_models == [model.id for model in two_free_text_models]
```

- [ ] **Step 2: Run test and verify missing service**

Run: `python -m pytest tests/services/test_translation.py -q`  
Expected: FAIL on missing module.

- [ ] **Step 3: Implement request/result models**

Define:

```python
class TranslationInput(BaseModel):
    id: str
    text: str


class TranslationRequest(BaseModel):
    segments: list[TranslationInput]
    source: LanguageCode
    target: LanguageCode
    glossary: dict[str, str] = {}


class TranslatedSegment(BaseModel):
    id: str
    text: str
    model_id: str
```

- [ ] **Step 4: Implement structured translation prompt and fallback**

The system prompt must instruct the model to:

- Return JSON `{"segments":[{"id":"...","text":"..."}]}`.
- Preserve segment IDs and count.
- Preserve glossary values exactly.
- Produce `zh-CN` or `zh-TW` according to target.
- Preserve proper nouns, URLs, product codes, and brand names.
- Return no commentary outside JSON.

For each free text-output model, call the client. Continue only on quota, timeout, or provider-unavailable errors. Reject responses with missing, duplicate, or extra segment IDs.

- [ ] **Step 5: Add tests for Vietnamese and Chinese behavior**

Test exact prompt assertions for:

- `vi -> en`
- `vi -> zh-CN`
- `vi -> zh-TW`
- glossary preservation
- mismatched response IDs
- all free models exhausted without selecting a paid model

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/services/test_translation.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ai_video_studio/services tests/services
git commit -m "feat: translate segments with free-model fallback"
```

---

### Task 7: Draft speech service with OpenRouter and Edge TTS fallback

**Files:**
- Create: `src/ai_video_studio/services/speech.py`
- Create: `src/ai_video_studio/providers/edge_tts.py`
- Create: `tests/services/test_speech.py`

**Interfaces:**
- Consumes: free audio-capable `ModelInfo`, `SpeechProvider`, segment text
- Produces: `SpeechService.render_preview(request) -> SpeechArtifact`

- [ ] **Step 1: Write failing fallback test**

```python
import pytest
from ai_video_studio.services.speech import SpeechRequest, SpeechService


@pytest.mark.asyncio
async def test_edge_tts_is_used_after_free_openrouter_models_fail(
    failing_openrouter_speech, successful_edge_speech, tmp_path
):
    service = SpeechService(
        openrouter=failing_openrouter_speech,
        edge=successful_edge_speech,
        free_audio_models=["free-a", "free-b"],
    )
    artifact = await service.render_preview(
        SpeechRequest(
            segment_id="s1",
            text="Xin chào",
            language="vi",
            voice_id="vi-VN-HoaiMyNeural",
            output_dir=tmp_path,
        )
    )
    assert artifact.provider == "edge-tts"
    assert artifact.path.exists()
    assert failing_openrouter_speech.called_models == ["free-a", "free-b"]
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/services/test_speech.py -q`  
Expected: FAIL on missing service.

- [ ] **Step 3: Implement speech request and artifact types**

```python
class SpeechRequest(BaseModel):
    segment_id: str
    text: str
    language: LanguageCode
    voice_id: str
    output_dir: Path


class SpeechArtifact(BaseModel):
    segment_id: str
    provider: str
    model_id: str
    path: Path
```

- [ ] **Step 4: Implement deterministic fallback order**

`SpeechService.render_preview` must:

1. Try each discovered free OpenRouter audio model.
2. Continue on quota, timeout, or unavailable errors.
3. Use Edge TTS after all free OpenRouter options fail.
4. Write to `<output_dir>/<segment_id>-preview.mp3`.
5. Never invoke a paid model unless `allow_paid_models=True` and a separate approval token is present.
6. Label results `tts`, never `voice_clone`.

- [ ] **Step 5: Add Edge TTS process adapter**

Wrap the executable call behind `AsyncProcessRunner.run(args: list[str]) -> ProcessResult`. Build arguments as a list, never a shell string:

```python
[
    "edge-tts",
    "--voice", voice_id,
    "--text", text,
    "--write-media", str(output_path),
]
```

Reject empty text, missing output files, and non-zero exit codes with typed errors.

- [ ] **Step 6: Run speech tests**

Run: `python -m pytest tests/services/test_speech.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ai_video_studio/services src/ai_video_studio/providers/edge_tts.py tests/services
git commit -m "feat: add free draft speech fallback"
```

---

### Task 8: Resumable Quick Dub orchestrator

**Files:**
- Create: `src/ai_video_studio/pipeline/orchestrator.py`
- Create: `tests/pipeline/test_orchestrator.py`

**Interfaces:**
- Consumes: `ProjectRepository`, `TranslationService`, `SpeechService`, `StudioProject`
- Produces: `QuickDubOrchestrator.run(project, through_stage, cancel_token) -> StudioProject`

- [ ] **Step 1: Write failing resume test**

```python
import pytest
from ai_video_studio.pipeline.orchestrator import QuickDubOrchestrator
from ai_video_studio.pipeline.state import StageName, StageStatus


@pytest.mark.asyncio
async def test_resume_skips_completed_translation(
    saved_project, repository, translation_service, speech_service
):
    saved_project.mark_stage(StageName.TRANSLATED, StageStatus.SUCCEEDED)
    repository.save(saved_project)
    orchestrator = QuickDubOrchestrator(repository, translation_service, speech_service)

    result = await orchestrator.run(saved_project, through_stage=StageName.SYNTHESIZED)

    assert translation_service.calls == 0
    assert speech_service.calls == len(saved_project.segments)
    assert result.stage(StageName.SYNTHESIZED).status == StageStatus.SUCCEEDED
```

- [ ] **Step 2: Write failing cancellation test**

```python
@pytest.mark.asyncio
async def test_cancel_preserves_completed_segments(
    saved_project, repository, translation_service, cancelling_speech_service
):
    orchestrator = QuickDubOrchestrator(repository, translation_service, cancelling_speech_service)
    result = await orchestrator.run(saved_project, through_stage=StageName.SYNTHESIZED)
    checkpoint = result.stage(StageName.SYNTHESIZED)
    assert checkpoint.status == StageStatus.CANCELLED
    assert checkpoint.completed_segment_ids == {"s1"}
    assert repository.load(saved_project.root_dir).stage(StageName.SYNTHESIZED) == checkpoint
```

- [ ] **Step 3: Run tests and verify failure**

Run: `python -m pytest tests/pipeline/test_orchestrator.py -q`  
Expected: FAIL on missing orchestrator.

- [ ] **Step 4: Implement ordered, resumable orchestration**

For each stage:

1. Read current checkpoint.
2. Skip a succeeded stage.
3. Mark running and persist.
4. Execute only incomplete segment IDs.
5. Persist after every segment.
6. Mark succeeded, failed, or cancelled.
7. Raise no generic provider exception without first persisting normalized error code and message.

- [ ] **Step 5: Add invalidation rules**

When source text changes, invalidate `TRANSLATED`, `SYNTHESIZED`, and `EXPORTED`. When translated text or voice changes, invalidate `SYNTHESIZED` and `EXPORTED`. Never invalidate `IMPORTED` unless the source media reference changes.

- [ ] **Step 6: Run pipeline and full suites**

Run: `python -m pytest tests/pipeline/test_orchestrator.py -q`  
Expected: PASS.

Run: `python -m ruff check . && python -m pytest -q`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ai_video_studio/pipeline tests/pipeline
git commit -m "feat: orchestrate resumable quick dubbing"
```

---

### Task 9: Desktop shell and Quick Dub project screen

**Files:**
- Create: `src/ai_video_studio/ui/main_window.py`
- Create: `src/ai_video_studio/ui/quick_dub.py`
- Create: `src/ai_video_studio/ui/theme.py`
- Create: `src/ai_video_studio/ui/__init__.py`
- Modify: `src/ai_video_studio/app.py`
- Create: `tests/ui/test_quick_dub.py`

**Interfaces:**
- Consumes: `ProjectRepository`, `QuickDubOrchestrator`, language enum
- Produces: `MainWindow`, `QuickDubWidget`, visible project creation and processing states

- [ ] **Step 1: Write failing UI state test**

```python
from ai_video_studio.ui.quick_dub import QuickDubWidget


def test_start_is_disabled_without_video(qtbot):
    widget = QuickDubWidget()
    qtbot.addWidget(widget)
    assert widget.start_button.isEnabled() is False
    widget.set_source_media("C:/video/demo.mp4")
    assert widget.start_button.isEnabled() is True
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/ui/test_quick_dub.py -q`  
Expected: FAIL on missing UI module.

- [ ] **Step 3: Build the Quick Dub form**

Include:

- Drag/drop media area and file picker
- Source language: Auto, Vietnamese, English, Chinese
- Target language: Vietnamese, English, Simplified Chinese, Traditional Chinese
- Provider summary showing OpenRouter free and Edge TTS fallback
- Pipeline stage list with pending/running/succeeded/failed/cancelled states
- Start, cancel, resume, and open-project-folder actions
- Warning that cloud media upload requires confirmation
- No voice-cloning controls in Phase 1

Use Qt signals to emit `source_selected(Path)`, `start_requested(QuickDubOptions)`, and `cancel_requested()`.

- [ ] **Step 4: Build main window layout**

Create a left navigation rail with Quick Dub, Studio (disabled with “Phase 3”), Projects, Queue, and Settings. Set a dark palette and a minimum window size of 1180×720. The central area hosts `QuickDubWidget`.

- [ ] **Step 5: Connect app entry point**

Update `build_app` dependencies through a separate `build_main_window()` factory so tests can supply fake services. Show the main window only from `__main__.py`.

- [ ] **Step 6: Add UI tests**

Verify:

- Source and target cannot be the same non-auto language.
- Start is disabled without media.
- Cancel is visible only while running.
- Paid-model toggle defaults off.
- Studio navigation is visibly disabled.
- Vietnamese and Chinese labels render without replacement characters.

- [ ] **Step 7: Run quality gates**

Run: `python -m ruff check . && python -m pytest -q`  
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/ai_video_studio/ui src/ai_video_studio/app.py src/ai_video_studio/__main__.py tests/ui
git commit -m "feat: add Quick Dub desktop experience"
```

---

### Task 10: Phase 1 integration fixture and documentation

**Files:**
- Create: `tests/integration/test_quick_dub_flow.py`
- Create: `tests/fixtures/openrouter_models.json`
- Modify: `README.md`
- Create: `docs/development.md`
- Create: `LICENSE`
- Create: `NOTICE.md`

**Interfaces:**
- Consumes: all Phase 1 interfaces
- Produces: reproducible mocked end-to-end test and contributor instructions

- [ ] **Step 1: Write the integration test**

The test must:

1. Create a project referencing a fake `input.mp4`.
2. Seed two Vietnamese segments and two speakers.
3. Return a catalog with two free text models and one free audio model.
4. Force quota failure on the first translation model.
5. Translate via the second model.
6. Force OpenRouter audio failure and synthesize via fake Edge TTS.
7. Persist after every segment.
8. Reload the project and verify translated text, artifact paths, checkpoint states, and `allow_paid_models=False`.

- [ ] **Step 2: Run the integration test and verify initial failure**

Run: `python -m pytest tests/integration/test_quick_dub_flow.py -q`  
Expected: FAIL until all fixtures and dependency wiring are correct.

- [ ] **Step 3: Add the deterministic fixture and minimal wiring fixes**

Use fixed JSON responses from `tests/fixtures/openrouter_models.json`. Do not access the network or invoke FFmpeg/Edge TTS in this test.

- [ ] **Step 4: Document setup and Phase 1 boundaries**

README instructions:

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m ai_video_studio
```

Document that Phase 1 validates UI, persistence, provider discovery, translation/TTS fallback, and resumability using simulated media segments. State explicitly that real FFmpeg/Whisper processing begins in Phase 2.

- [ ] **Step 5: Add license and attribution**

Use GPL-3.0-or-later for the derivative application. `NOTICE.md` must name pyVideoTrans as the architectural/source foundation and retain upstream notices for any imported components.

- [ ] **Step 6: Run final Phase 1 verification**

Run: `python -m ruff check .`  
Expected: PASS.

Run: `python -m pytest -q`  
Expected: PASS.

Run on Windows: `python -m ai_video_studio`  
Expected: main window opens; Quick Dub form accepts a media path; paid models remain disabled by default.

- [ ] **Step 7: Commit**

```bash
git add tests/integration tests/fixtures README.md docs/development.md LICENSE NOTICE.md
git commit -m "test: verify Phase 1 quick dub workflow"
```
