from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".aac", ".flac", ".ogg", ".wma", ".webm", ".mpeg", ".mpga"}


def validate_audio_file(path: str | Path) -> Path:
    audio = Path(path).expanduser()
    if not audio.exists() or not audio.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio}")
    if audio.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format '{audio.suffix}'. Supported formats: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}")
    if audio.stat().st_size == 0:
        raise ValueError("Audio file is empty.")
    return audio
