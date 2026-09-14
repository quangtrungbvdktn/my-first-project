# Phase 3 — Quick Video Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fast non-destructive video transforms, subtitle-preserving flips, metadata removal, timed overlays/watermarks, presets, batch processing, and safe FFmpeg export.

**Architecture:** Represent every edit as a typed operation stored in the project, compile operations into a deterministic layer/filter graph, and render previews/final files through the Phase 2 media runner. Subtitle layers are composed after picture transforms; burned-in subtitles use the approved OCR-mask/reconstruction workflow.

**Tech Stack:** Python 3.11+, PySide6, Pydantic, FFmpeg/ffprobe, Pillow, pytest

**Spec:** `docs/superpowers/specs/2026-09-14-ai-video-translator-design.md`

## Global Constraints

- Never overwrite or mutate source media.
- Preserve readable subtitle orientation when flipping video.
- Use one encoding pass whenever compatible operations permit it.
- Remove nonessential metadata while preserving playback-critical rotation/color data.
- Keep all overlay coordinates normalized to the output canvas.
- CPU-first Windows behavior; preview rendering must be cancellable and cached.

---

### Task 1: Typed non-destructive edit operations

**Files:**
- Create: `src/ai_video_studio/video_edits/models.py`
- Create: `src/ai_video_studio/video_edits/__init__.py`
- Modify: `src/ai_video_studio/domain/models.py`
- Create: `tests/video_edits/test_models.py`

**Interfaces:**
- Produces: `FlipEdit`, `RotateEdit`, `CropEdit`, `ResizeEdit`, `TrimEdit`, `SpeedEdit`, `AudioEdit`, `OverlayEdit`, `MetadataEdit`, `VideoEditProject`

- [ ] Write validation tests for normalized boxes, positive time ranges, legal speed range 0.25–4.0, opacity 0–1, unique edit IDs, and deterministic z-order.
- [ ] Run `python -m pytest tests/video_edits/test_models.py -q`; expect missing-module failure.
- [ ] Implement discriminated Pydantic unions using a `kind` field and immutable source reference.
- [ ] Add `video_edits: list[VideoEdit]` and `edit_revision: int` to project data.
- [ ] Test JSON round-trip with Vietnamese and Chinese overlay text; expect PASS.
- [ ] Commit: `git commit -m "feat: model non-destructive video edits"`.

### Task 2: Canvas, crop, rotation, flip, and aspect-ratio compiler

**Files:**
- Create: `src/ai_video_studio/video_edits/compiler.py`
- Create: `tests/video_edits/test_transform_compiler.py`

**Interfaces:**
- Produces: `EditCompiler.compile(edits, media_info, output_profile) -> CompiledEditGraph`

- [ ] Add exact filter-graph tests for horizontal/vertical flip, 90° rotation, arbitrary rotation, crop, resize, and 9:16/16:9/1:1 output.
- [ ] Test blurred-background composition uses a duplicated scaled background plus centered foreground.
- [ ] Implement normalized-to-pixel coordinate conversion after rotation and before overlay composition.
- [ ] Ensure picture transforms occur before subtitle and watermark layers.
- [ ] Run transform tests; expect PASS.
- [ ] Commit: `git commit -m "feat: compile video transforms"`.

### Task 3: Trim, speed, mute, and replacement-audio compiler

**Files:**
- Modify: `src/ai_video_studio/video_edits/compiler.py`
- Create: `tests/video_edits/test_timing_audio.py`

**Interfaces:**
- Extends: `CompiledEditGraph.video_filters`, `audio_filters`, `input_args`, `map_args`

- [ ] Test head/tail trim, PTS speed conversion, atempo chains for the full 0.25–4.0 range, mute, replacement audio, and audio-shorter-than-video behavior.
- [ ] Implement trim timestamps without shell interpolation.
- [ ] Map replacement audio explicitly and require user choice between trim, loop, and pad.
- [ ] Recompute overlay/subtitle times after trim and speed edits.
- [ ] Run timing/audio tests; expect PASS.
- [ ] Commit: `git commit -m "feat: add quick timing and audio edits"`.

### Task 4: Subtitle-preserving flip pipeline

**Files:**
- Create: `src/ai_video_studio/video_edits/subtitle_preservation.py`
- Create: `tests/video_edits/test_subtitle_preservation.py`

**Interfaces:**
- Produces: `SubtitlePreservationPlanner.plan(project, flip) -> SubtitlePreservationPlan`

- [ ] Test external/application subtitles are rendered after flip with unchanged text coordinates relative to the output canvas.
- [ ] Test burned-in subtitles require OCR regions, masks before transform, and reconstructed cues after transform.
- [ ] Test low OCR confidence produces `ReviewRequired` and blocks final export but permits preview.
- [ ] Implement three strategies: `none`, `render_after_transform`, and `mask_transform_reconstruct`.
- [ ] Verify Unicode text and ASS styles remain unchanged.
- [ ] Run subtitle-preservation tests; expect PASS.
- [ ] Commit: `git commit -m "feat: preserve subtitles across video flips"`.

### Task 5: Timed overlay and watermark layers

**Files:**
- Create: `src/ai_video_studio/video_edits/overlays.py`
- Create: `tests/video_edits/test_overlays.py`

**Interfaces:**
- Produces: `OverlayCompiler.compile(overlays, canvas) -> list[FilterNode]`

- [ ] Test text/image/video overlays, normalized position, scale, opacity, enable time range, and stable z-order.
- [ ] Test safe-zone snapping and corner/edge/center alignment.
- [ ] Implement simple linear position and opacity keyframes with FFmpeg expressions.
- [ ] Escape drawtext content through generated UTF-8 text files rather than embedding user text in shell arguments.
- [ ] Allow explicit watermark placement above or below subtitles.
- [ ] Run overlay tests; expect PASS.
- [ ] Commit: `git commit -m "feat: add timed overlays and watermarks"`.

### Task 6: Metadata policy and safe exporter

**Files:**
- Create: `src/ai_video_studio/video_edits/metadata.py`
- Create: `src/ai_video_studio/video_edits/exporter.py`
- Create: `tests/video_edits/test_exporter.py`

**Interfaces:**
- Produces: `MetadataPolicy.build_args(media_info) -> list[str]`; `QuickVideoExporter.export(request) -> Path`

- [ ] Test `-map_metadata -1`, chapter removal, optional technical color metadata, and normalized rotation after physical rotation.
- [ ] Test stream copy is selected only for metadata-only or compatible remux operations.
- [ ] Test every visual/audio filter forces re-encoding exactly once.
- [ ] Render to a temporary sibling file, validate with ffprobe, atomically rename, and reject source/output path equality.
- [ ] Test cancellation removes only the incomplete temporary output.
- [ ] Run exporter tests; expect PASS.
- [ ] Commit: `git commit -m "feat: export sanitized edited video"`.

### Task 7: Reusable presets and batch queue

**Files:**
- Create: `src/ai_video_studio/video_edits/presets.py`
- Create: `src/ai_video_studio/video_edits/batch.py`
- Create: `tests/video_edits/test_batch.py`

**Interfaces:**
- Produces: `PresetRepository`; `BatchVideoJob`; `BatchQueue.run_next()`

- [ ] Test preset save/load/versioning, missing overlay assets, per-video output naming, pause/resume, and one-file failure isolation.
- [ ] Store presets as UTF-8 JSON without API keys or absolute temporary paths.
- [ ] Resolve watermark assets when applying a preset and request replacement if missing.
- [ ] Process one CPU-heavy encode at a time by default; expose configurable concurrency.
- [ ] Persist queue status after every file.
- [ ] Run batch tests; expect PASS.
- [ ] Commit: `git commit -m "feat: add reusable edit presets and batch queue"`.

### Task 8: Quick Video Tools desktop UI

**Files:**
- Create: `src/ai_video_studio/ui/quick_video_tools.py`
- Create: `src/ai_video_studio/ui/overlay_editor.py`
- Modify: `src/ai_video_studio/ui/main_window.py`
- Create: `tests/ui/test_quick_video_tools.py`

**Interfaces:**
- Produces: `QuickVideoToolsWidget`; signals for edit, undo, redo, preview, export, preset, and batch actions

- [ ] Test undo/redo, edit ordering, disabled export without source, subtitle-preservation warning, and metadata-removal default.
- [ ] Add transform, aspect ratio, trim/speed/audio, overlay, watermark, metadata, preset, and batch panels.
- [ ] Add draggable/resizable preview overlays with z-order controls and safe-zone snapping.
- [ ] Add low-resolution cached preview with debounce and cancellation.
- [ ] Display whether export will stream-copy or re-encode and show the new output path.
- [ ] Run offscreen UI tests; expect PASS.
- [ ] Commit: `git commit -m "feat: add Quick Video Tools workspace"`.

### Task 9: End-to-end safe edit fixture

**Files:**
- Create: `tests/integration/test_quick_video_tools.py`
- Create: `tests/fixtures/edit_project.json`
- Modify: `README.md`
- Modify: `docs/development.md`

**Interfaces:**
- Validates project → compile → preview → export → reload with deterministic fake media runner.

- [ ] Build a portrait fixture with horizontal flip, burned-in subtitle reconstruction, blurred 9:16 background, timed watermark, speed change, and metadata removal.
- [ ] Assert filter ordering: mask → picture transform → reconstructed subtitle → watermark.
- [ ] Assert source hash is unchanged and export filename is different.
- [ ] Assert reload preserves normalized positions, keyframes, z-order, preset ID, and batch status.
- [ ] Document supported quick edits, subtitle behavior, stream-copy limits, metadata policy, and CPU performance expectations.
- [ ] Run `python -m ruff check . && python -m pytest -q`; expect PASS.
- [ ] Commit: `git commit -m "test: verify safe Quick Video Tools workflow"`.
