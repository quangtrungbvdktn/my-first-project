# AI Video Translator & Dubbing Studio — Technical Design

**Date:** 2026-09-14  
**Status:** Approved design; implementation pending spec review  
**Target:** Windows desktop, CPU-first, hybrid local/cloud  
**Foundation:** Fork/adaptation of [pyVideoTrans](https://github.com/jianchang512/pyvideotrans), GPL-3.0

## 1. Product goal

Build a modern desktop studio that translates and dubs videos while retaining editable transcripts, speaker assignments, timing, background audio, subtitles, and export history. The primary language pairs are:

- Vietnamese ↔ English
- Vietnamese ↔ Simplified Chinese
- Vietnamese ↔ Traditional Chinese
- Additional languages through provider adapters

The first release supports videos up to approximately 30 minutes and provides both an automated Quick Dub workflow and a detailed Studio workflow.

## 2. Product modes

### Quick Dub

1. Import a video.
2. Detect or select source language.
3. Select target language and processing mode.
4. Automatically transcribe, translate, synthesize, align, mix, and export.
5. Present warnings or approvals only where needed.

### Studio

Users can edit:

- Source transcript and translated text side by side
- Segment boundaries and timestamps
- Speaker labels and colors
- Voice/model assigned to each speaker
- Glossary, names, brand terms, and pronoun rules
- Speech speed, pitch, gain, timing, and subtitle style
- Background music/ambience mix
- Lip-sync selection per eligible shot

## 3. Architecture

The application is divided into independent modules with stable interfaces:

1. **Desktop UI**
   - Dark, modern Windows interface
   - Project navigation, preview, transcript editor, speaker timeline, voice manager, inspector, task queue, and export center

2. **Pipeline Orchestrator**
   - Runs work as resumable stages
   - Stores checkpoints after every stage
   - Retries only failed segments
   - Supports cancellation and provider fallback

3. **Local Media Engine**
   - FFmpeg for extraction, timing, mixing, and final composition
   - Faster-Whisper CPU for default transcription
   - Optional Demucs for source separation
   - Optional pyannote diarization
   - Experimental Wav2Lip CPU fallback

4. **Provider Adapter Layer**
   - Translation adapters
   - Text-to-speech adapters
   - Voice-cloning adapters
   - Lip-sync adapters
   - Each adapter exposes capability discovery, health check, cost estimate, request, cancellation, and normalized error reporting

5. **Project Workspace**
   - Local project metadata
   - Source media and generated assets
   - Transcript, translations, glossary, speaker configuration, cache, checkpoints, and exports

## 4. Processing pipeline

1. Inspect media and validate disk space.
2. Extract dialogue/audio locally.
3. Transcribe with Faster-Whisper CPU by default.
4. Detect and segment speakers.
5. Normalize sentence boundaries and timestamps.
6. Translate using project context, glossary, names, and address rules.
7. Let the user review text and speaker assignments.
8. Generate short voice previews per segment.
9. Synthesize approved dialogue.
10. Align synthesized speech to target windows without excessive time stretching.
11. Mix dialogue with retained music and ambience.
12. Apply lip-sync only to shots with a sufficiently visible face.
13. Render preview and final outputs.
14. Export MP4, dubbed audio, source SRT, translated SRT, or bilingual SRT.

## 5. OpenRouter integration

OpenRouter is a first-class provider for free translation and dubbing models.

### Model discovery

At startup and on manual refresh, the adapter fetches the current model catalog and filters models by:

- Required input/output modality
- Current price of zero or a free model route
- Availability and quota
- Target language support
- Provider health

Model names are not permanently hard-coded because the free catalog can change.

### Translation

OpenRouter free models may be used to:

- Translate Vietnamese, English, and Chinese
- Rewrite translations to fit speaking duration
- Preserve glossary entries and proper nouns
- Check translation consistency
- Return structured segment results

### TTS/dubbing

When OpenRouter exposes compatible free TTS models:

1. Select a default model or assign a model per speaker.
2. Generate a 5–10 second preview.
3. Retry with the next compatible free model after quota/provider failure.
4. Fall back to Edge TTS if no free OpenRouter TTS route succeeds.
5. Ask for approval before switching to a paid model.

Standard TTS must never be presented as voice cloning. Voice cloning is enabled only when the selected provider explicitly supports it.

## 6. Default providers and fallbacks

| Stage | Default | Fallback |
|---|---|---|
| Media processing | FFmpeg local | None |
| Transcription | Faster-Whisper CPU | Whisper-compatible API |
| Speaker diarization | pyannote local/background | Compatible cloud service |
| Translation | OpenRouter free | Gemini, OpenAI, LibreTranslate, custom |
| Draft TTS | OpenRouter free | Edge TTS |
| Premium TTS | User-selected adapter | Azure, OpenAI, ElevenLabs-compatible |
| Voice cloning | Authorized cloud adapter | Experimental XTTS local |
| Lip-sync | Cloud adapter | Experimental Wav2Lip CPU |
| Composition/export | FFmpeg local | None |

## 7. Language behavior

- Auto-detect source language with manual override.
- Treat Simplified and Traditional Chinese as separate targets.
- Preserve names, brands, URLs, product codes, and glossary terms.
- Store glossary and forms of address per project.
- Validate Vietnamese and Chinese Unicode through the full export pipeline.
- Allow future language packs without changing pipeline orchestration.

## 8. Automatic Subtitle Studio

The application generates editable subtitles from Faster-Whisper word timestamps and keeps source and translated text synchronized.

### Authoring

- Split captions using sentence meaning, pauses, reading speed, and line-length limits.
- Edit source/translated text, start/end time, line breaks, and per-caption position.
- Support source-only, translated-only, and bilingual layouts.
- Find/replace in bulk and apply the project glossary.
- Warn about overlaps, excessive reading speed, overflow, and missing glyphs.
- Re-time captions after transcript edits or dubbed-audio duration changes.

### Styling and export

- Configure font, size, fill, outline, shadow, background, alignment, and safe-zone position.
- Preview styling over the video and save reusable project presets.
- Support word-level karaoke highlighting when word timestamps are available.
- Export source, translated, and bilingual SRT; WebVTT; styled ASS; soft-subtitle video; and FFmpeg-burned MP4.

### Replacing existing burned-in subtitles

- Detect likely original subtitle regions with OCR and group detections by shot/time range.
- Display an editable mask overlay; users can drag, resize, and keyframe masks.
- Process each mask with Gaussian blur, pixelation, or optional cloud/local inpainting.
- Default to CPU-friendly OCR plus FFmpeg Gaussian blur.
- Place translated subtitles over the processed region or at a separately editable position.
- Allow global positioning plus per-caption and per-shot overrides.
- Persist masks, keyframes, positions, and styles so exports can be regenerated without repeating OCR.
- Provide Before/After preview and safe-zone/overflow warnings.
- Never alter the source video; all processing targets new preview/export files.

## 9. Storage and recovery

Each project uses a separate local directory containing:

- Original media references or managed copies
- Extracted audio and separated stems
- Transcript and translations
- Speaker and voice configuration
- Per-segment synthesized audio
- Provider response cache
- Pipeline checkpoint state
- Preview and export history
- Technical logs without API keys

The application autosaves edits, resumes after restart, regenerates only invalidated stages, and never overwrites original media.

## 10. Security, privacy, and consent

- Store secrets in Windows Credential Manager.
- Do not write API keys into project files or logs.
- Clearly show which media will be uploaded before a cloud task.
- Require explicit confirmation before the first upload for each provider/project.
- Require confirmation that the user has the right to clone or use a voice.
- Allow users to clear local cache and provider-generated temporary assets.
- Do not scrape, infer, or clone voices from unauthorized sources.

## 11. Error handling

- Preflight checks: FFmpeg, writable workspace, disk capacity, connectivity, credentials, quota, and provider capability.
- Typed errors: configuration, input, local process, timeout, quota, provider, moderation, and export.
- Bounded retries with exponential backoff.
- Segment-level retry and provider fallback.
- Preserve completed stages after cancellation or application shutdown.
- Show actionable Vietnamese error messages with technical details available on demand.

## 12. Acceptance testing

The first release must validate:

- Single-speaker and multi-speaker videos
- Vietnamese ↔ English and Vietnamese ↔ Chinese
- Simplified and Traditional Chinese output
- Landscape, portrait, and mixed aspect ratios
- Network loss and quota exhaustion during processing
- Resume after application restart
- Correct Vietnamese and Chinese fonts/encoding
- Audio timing within configured tolerances
- Background music retention
- Segment-only regeneration
- Preservation of original media
- OpenRouter free-model fallback behavior
- Refusal to silently use paid models
- OCR detection and manual correction of burned-in subtitle masks
- Blur/pixelate replacement across scene changes
- Manual global, per-caption, and per-shot subtitle positioning
- SRT, VTT, ASS, soft-subtitle, and burned-in MP4 export

## 13. Delivery boundaries

Included in the first release:

- Windows desktop installer
- Quick Dub and Studio workflows
- CPU-first local transcription
- Editable bilingual transcript and speaker timeline
- OpenRouter free translation/TTS discovery
- Edge TTS fallback
- Provider adapters for paid services
- Authorized voice cloning
- Cloud lip-sync and experimental CPU fallback
- MP4, audio, SRT, VTT, and ASS exports
- Automatic Subtitle Studio with styling, karaoke timing, original-subtitle masking, and manual positioning

Not required for the first release:

- Team collaboration
- Cloud project synchronization
- Mobile applications
- Production-grade CPU lip-sync
- Videos longer than approximately 30 minutes
- macOS/Linux installers

## 14. Implementation strategy

The repository is currently an effectively empty starter. Implementation will:

1. Preserve the existing sample files unless the owner later requests removal.
2. Import only the pyVideoTrans components needed for the pipeline, respecting GPL-3.0 attribution and license obligations.
3. Establish module boundaries before UI work.
4. Add automated tests around adapters, project persistence, fallback selection, and pipeline invalidation.
5. Develop on dedicated feature branches and review through pull requests.
