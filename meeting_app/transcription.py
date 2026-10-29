"""Lazy local faster-whisper adapter; model download occurs on first transcription."""

class TranscriptionError(RuntimeError):
    pass


def transcribe(path, model_size="small", device="cpu", compute_type="int8", progress=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError("faster-whisper is not installed. Install dependencies from requirements.txt.") from exc
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(str(path), beam_size=5, vad_filter=True)
        segments = []
        text_parts = []
        duration = max(float(getattr(info, "duration", 0.0) or 0.0), 1.0)
        for segment in segments_iter:
            text_parts.append(segment.text.strip())
            segments.append({"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip(), "speaker": None})
            if progress: progress(min(95, int(segment.end / duration * 95)))
        if not text_parts:
            raise TranscriptionError("No speech was detected. Check the audio and try again.")
        return "\n".join(f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}] {s['text']}" for s in segments), segments
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

