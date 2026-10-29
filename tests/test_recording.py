import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from meeting_app.recording import MicrophoneRecorder, RecordingError


class FakeStream:
    def __init__(self, **kwargs):
        self.callback = kwargs['callback']
        self.stopped = False

    def start(self):
        self.callback(bytes(16), 8, None, None)

    def stop(self):
        self.stopped = True

    def close(self):
        pass


class FakeAudioBackend:
    def InputStream(self, **kwargs):
        self.stream = FakeStream(**kwargs)
        return self.stream


class MicrophoneRecordingTests(unittest.TestCase):
    def test_records_mono_pcm_wav_and_closes_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'live.wav'
            backend = FakeAudioBackend()
            recorder = MicrophoneRecorder(path, backend=backend)
            recorder.start()
            result = recorder.stop()
            self.assertEqual(result, path)
            self.assertTrue(backend.stream.stopped)
            with wave.open(str(path), 'rb') as audio:
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getframerate(), 16000)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getnframes(), 8)

    def test_reports_missing_sounddevice_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = MicrophoneRecorder(Path(directory) / 'live.wav')
            with patch.dict('sys.modules', {'sounddevice': None}):
                with self.assertRaisesRegex(RecordingError, 'sounddevice'):
                    recorder.start()


if __name__ == '__main__':
    unittest.main()
