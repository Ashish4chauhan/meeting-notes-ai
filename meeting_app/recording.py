"""Local microphone capture to a Whisper-compatible WAV file."""

import importlib
import queue
import threading
import wave
from pathlib import Path


class RecordingError(RuntimeError):
    """Raised when microphone recording cannot start or finish safely."""


class MicrophoneRecorder:
    def __init__(self, path: str | Path, backend=None, sample_rate: int = 16000):
        self.path = Path(path)
        self.backend = backend
        self.sample_rate = sample_rate
        self._stream = None
        self._wav = None
        self._chunks = queue.Queue()
        self._writer = None
        self._recording = False
        self._writer_error = None

    @property
    def is_recording(self):
        return self._recording

    def start(self):
        if self._recording:
            raise RecordingError("A microphone recording is already in progress.")
        if self.backend is None:
            try:
                self.backend = importlib.import_module("sounddevice")
            except ImportError as exc:
                raise RecordingError("Live recording needs sounddevice. Install project dependencies with: python -m pip install -r requirements.txt") from exc
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._wav = wave.open(str(self.path), "wb")
            self._wav.setnchannels(1)
            self._wav.setsampwidth(2)
            self._wav.setframerate(self.sample_rate)
            self._writer = threading.Thread(target=self._write_chunks, name="microphone-wav-writer", daemon=True)
            self._writer.start()
            self._stream = self.backend.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                callback=self._on_audio,
            )
            self._stream.start()
            self._recording = True
        except Exception as exc:
            self._finish_writer()
            try:
                self._close_stream()
            except Exception:
                pass
            finally:
                self._close_wave()
            if isinstance(exc, RecordingError):
                raise
            raise RecordingError(f"Could not start microphone recording: {exc}") from exc

    def _on_audio(self, indata, frames, time_info, status):
        # Keep the PortAudio callback short; disk writes happen on a separate worker.
        self._chunks.put(bytes(indata))

    def _write_chunks(self):
        while True:
            chunk = self._chunks.get()
            try:
                if chunk is None:
                    return
                if self._writer_error is None:
                    try:
                        self._wav.writeframesraw(chunk)
                    except Exception as exc:
                        self._writer_error = exc
            finally:
                self._chunks.task_done()

    def _close_stream(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def _finish_writer(self):
        if self._writer is not None:
            self._chunks.put(None)
            self._chunks.join()
            self._writer.join(timeout=5)
            self._writer = None

    def _close_wave(self):
        if self._wav is not None:
            self._wav.close()
            self._wav = None

    def stop(self):
        if self._stream is None and self._wav is None:
            raise RecordingError("No microphone recording is in progress.")
        stream_error = None
        try:
            self._close_stream()
        except Exception as exc:
            stream_error = exc
        finally:
            self._recording = False
            self._finish_writer()
            self._close_wave()
        if self._writer_error:
            raise RecordingError(f"Could not write the recording: {self._writer_error}") from self._writer_error
        if stream_error:
            raise RecordingError(f"Could not stop microphone cleanly: {stream_error}") from stream_error
        if not self.path.exists() or self.path.stat().st_size <= 44:
            raise RecordingError("The microphone captured no audio. Check the input device and microphone permissions.")
        return self.path
