# Phase 2 — Automatic Subtitles and Media Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn imported video into editable source/translated captions, remove or obscure burned-in source subtitles, position styled translated captions, and export SRT/VTT/ASS and a new MP4.

**Architecture:** Add local media, transcription, caption-layout, OCR-mask, and render services behind protocols. Use Faster-Whisper word timestamps, OpenCV/Tesseract-compatible OCR adapters, and FFmpeg filter graphs; keep every generated asset and mask in the project workspace. UI edits operate on domain data, while render commands are pure builders covered by tests.

**Tech Stack:** Python 3.11+, faster-whisper, FFmpeg/ffprobe, PySide6, OpenCV, Pillow, optional Tesseract/PaddleOCR adapter, pytest

**Spec:** `docs/superpowers/specs/2026-09-14-ai-video-translator-design.md`

## Global Constraints

- CPU-first Windows operation; GPU is optional.
- Vietnamese, English, Simplified Chinese, and Traditional Chinese must render correctly.
- Never modify or overwrite source media.
- OCR masks and subtitle positions must remain manually editable.
- Gaussian blur is the default original-subtitle treatment.
- Inpainting is optional and must not block local export.
- Every media stage is resumable and invalidated only by relevant edits.

---

### Task 1: Media probe and safe FFmpeg process runner

**Files:**
- Create: `src/ai_video_studio/media/process.py`
- Create: `src/ai_video_studio/media/probe.py`
- Create: `src/ai_video_studio/media/__init__.py`
- Create: `tests/media/test_probe.py`

**Interfaces:**
- Produces: `AsyncProcessRunner.run(args: list[str]) -> ProcessResult`; `MediaProbe.inspect(path) -> MediaInfo`

- [ ] Write tests proving arguments are passed as a list, non-zero exits become `MediaProcessError`, and ffprobe JSON maps width, height, duration, FPS, audio presence, and rotation.
- [ ] Run `python -m pytest tests/media/test_probe.py -q`; expect missing-module failure.
- [ ] Implement `ProcessResult(returncode, stdout, stderr)`, `MediaInfo(width, height, duration_ms, fps, has_audio, rotation)`, cancellation, and UTF-8-safe decoding.
- [ ] Reject missing input, zero duration, unsupported video stream, and insufficient free disk space with typed Vietnamese-facing error codes.
- [ ] Run tests; expect PASS.
- [ ] Commit: `git commit -m "feat: add safe media inspection"`.

### Task 2: Faster-Whisper transcription with word timestamps

**Files:**
- Create: `src/ai_video_studio/transcription/base.py`
- Create: `src/ai_video_studio/transcription/faster_whisper.py`
- Create: `tests/transcription/test_faster_whisper.py`

**Interfaces:**
- Produces: `Transcriber.transcribe(media, language) -> Transcript`; `WordToken(text, start_ms, end_ms, confidence)`

- [ ] Write a fake-model test mapping Vietnamese words and timestamps into normalized `TranscriptSegment` objects.
- [ ] Verify language `auto`, `vi`, `en`, and `zh` mapping and cancellation between decoded segments.
- [ ] Implement lazy model loading with CPU defaults `device="cpu"`, `compute_type="int8"`, and `word_timestamps=True`.
- [ ] Persist raw model output plus normalized transcript before returning.
- [ ] Run `python -m pytest tests/transcription -q`; expect PASS.
- [ ] Commit: `git commit -m "feat: transcribe video with word timing"`.

### Task 3: Caption segmentation and quality warnings

**Files:**
- Create: `src/ai_video_studio/subtitles/models.py`
- Create: `src/ai_video_studio/subtitles/segmenter.py`
- Create: `src/ai_video_studio/subtitles/validation.py`
- Create: `tests/subtitles/test_segmenter.py`

**Interfaces:**
- Produces: `CaptionCue`, `WordTiming`, `CaptionSegmenter.segment(words, policy)`, `CaptionValidator.validate(cues, frame_size)`

- [ ] Test splits on sentence punctuation, pauses ≥500 ms, maximum two lines, and configurable characters per line.
- [ ] Test no cue has `end_ms <= start_ms` and word timings remain inside the parent cue.
- [ ] Implement reading-speed warnings, overlap warnings, frame overflow warnings, and missing-font-glyph warnings.
- [ ] Add source, translated, and bilingual text fields plus global/per-cue position override types.
- [ ] Run `python -m pytest tests/subtitles -q`; expect PASS.
- [ ] Commit: `git commit -m "feat: build editable caption cues"`.

### Task 4: SRT, WebVTT, and ASS serializers

**Files:**
- Create: `src/ai_video_studio/subtitles/serialize.py`
- Create: `tests/subtitles/test_serialize.py`

**Interfaces:**
- Produces: `write_srt(cues, path, track)`, `write_vtt(cues, path, track)`, `write_ass(cues, style, path, karaoke)`

- [ ] Add golden-file tests containing Vietnamese diacritics, Simplified Chinese, and Traditional Chinese.
- [ ] Test bilingual line order, millisecond rounding, newline escaping, ASS positioning tags, and word-level karaoke durations.
- [ ] Implement UTF-8 writers with deterministic ordering and no mutation of cue data.
- [ ] Run serializer tests; expect byte-for-byte PASS.
- [ ] Commit: `git commit -m "feat: export multilingual subtitle formats"`.

### Task 5: Original burned-in subtitle OCR masks

**Files:**
- Create: `src/ai_video_studio/subtitles/ocr/base.py`
- Create: `src/ai_video_studio/subtitles/ocr/detector.py`
- Create: `src/ai_video_studio/subtitles/masks.py`
- Create: `tests/subtitles/test_masks.py`

**Interfaces:**
- Produces: `OcrRegion(frame_ms, box, confidence, text)`; `SubtitleMask(start_ms, end_ms, keyframes, treatment)`; `MaskTracker.group(regions)`

- [ ] Test that nearby OCR boxes across adjacent sampled frames become one time-ranged mask.
- [ ] Test low-confidence boxes are excluded and shot-boundary gaps prevent accidental grouping.
- [ ] Implement normalized coordinates so masks survive resolution changes.
- [ ] Support `blur`, `pixelate`, and `inpaint` treatment values; default to `blur`.
- [ ] Persist user-edited boxes and keyframes; mark manual overrides so later OCR refresh does not overwrite them.
- [ ] Run mask tests; expect PASS.
- [ ] Commit: `git commit -m "feat: detect editable original subtitle masks"`.

### Task 6: FFmpeg mask and subtitle render graph

**Files:**
- Create: `src/ai_video_studio/render/filters.py`
- Create: `src/ai_video_studio/render/export.py`
- Create: `tests/render/test_filters.py`

**Interfaces:**
- Produces: `FilterGraphBuilder.build(masks, ass_path, media_info) -> list[str]`; `VideoExporter.export(request) -> Path`

- [ ] Write exact command tests for one blur mask, one pixelated mask, multiple time ranges, ASS overlay, audio stream mapping, and rotated portrait video.
- [ ] Build blur with cropped region + `gblur` + timed `overlay`; build pixelation with downscale/upscale nearest-neighbor filters.
- [ ] Escape Windows paths safely for FFmpeg subtitle filters without using a shell.
- [ ] Always render to a temporary output inside the export directory, validate it with ffprobe, then atomically rename to the final new filename.
- [ ] Reject final paths equal to source media.
- [ ] Run `python -m pytest tests/render -q`; expect PASS.
- [ ] Commit: `git commit -m "feat: render replacement subtitles safely"`.

### Task 7: Interactive subtitle and mask editor

**Files:**
- Create: `src/ai_video_studio/ui/subtitle_editor.py`
- Create: `src/ai_video_studio/ui/video_overlay.py`
- Create: `src/ai_video_studio/ui/subtitle_style.py`
- Create: `tests/ui/test_subtitle_editor.py`

**Interfaces:**
- Produces: `SubtitleEditorWidget`; signals `cue_changed`, `position_changed`, `mask_changed`, `style_changed`

- [ ] Test editing source/translation, timestamp validation, global versus per-cue position, and undo/redo.
- [ ] Add synchronized cue table, source/translation fields, waveform time fields, warning badges, and search/replace.
- [ ] Add draggable/resizable subtitle and mask overlays over the video preview.
- [ ] Add mask treatment selector, keyframe controls, Before/After toggle, safe zones, and overflow indication.
- [ ] Add style controls for font, size, fill, outline, shadow, background, alignment, and karaoke preview.
- [ ] Persist after each accepted edit and invalidate only subtitle preview/export stages.
- [ ] Run UI tests offscreen; expect PASS.
- [ ] Commit: `git commit -m "feat: add automatic subtitle studio"`.

### Task 8: Subtitle pipeline checkpoints and export center

**Files:**
- Modify: `src/ai_video_studio/pipeline/state.py`
- Modify: `src/ai_video_studio/pipeline/orchestrator.py`
- Create: `src/ai_video_studio/pipeline/subtitles.py`
- Create: `tests/pipeline/test_subtitle_pipeline.py`

**Interfaces:**
- Adds stages: `TRANSCRIBED`, `CAPTIONED`, `MASKS_DETECTED`, `SUBTITLES_RENDERED`

- [ ] Test resume after transcription, OCR cancellation, per-cue edit invalidation, mask-only invalidation, and render retry.
- [ ] Implement checkpoint persistence after each transcription segment, OCR sample batch, and rendered preview.
- [ ] Export source/translated/bilingual SRT, VTT, ASS, soft-subtitle MP4, and burn-in MP4 independently.
- [ ] Ensure an export format failure does not invalidate successful sibling formats.
- [ ] Run pipeline tests and the full suite; expect PASS.
- [ ] Commit: `git commit -m "feat: orchestrate resumable subtitle exports"`.

### Task 9: End-to-end subtitle replacement fixture

**Files:**
- Create: `tests/integration/test_subtitle_replacement.py`
- Create: `tests/fixtures/subtitle_regions.json`
- Modify: `README.md`
- Modify: `docs/development.md`

**Interfaces:**
- Validates the complete Phase 2 subtitle workflow with deterministic fakes.

- [ ] Create a portrait-video fixture description with burned-in Vietnamese subtitles, translated Chinese cues, two OCR masks, and a manual position override.
- [ ] Run the integration test before wiring; expect failure.
- [ ] Wire probe → transcript → captions → translation → masks → ASS → FFmpeg command using fake process/model adapters.
- [ ] Assert original input hash is unchanged, output path differs, UTF-8 text is preserved, manual mask survives reload, and no network is used.
- [ ] Document FFmpeg, Faster-Whisper, OCR engine, supported exports, CPU performance expectations, and optional inpainting behavior.
- [ ] Run `python -m ruff check . && python -m pytest -q`; expect PASS.
- [ ] Commit: `git commit -m "test: verify automatic subtitle replacement"`.
