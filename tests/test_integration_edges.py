import unittest
from types import SimpleNamespace
from unittest.mock import patch

from meeting_app.summarize import summarize_transcript
from meeting_app.transcription import TranscriptionError, transcribe


class LongTranscriptTests(unittest.TestCase):
    def test_detailed_summary_handles_more_sentences_than_one_chunk(self):
        transcript = " ".join(f"Topic {n} was reviewed." for n in range(120))
        summary = summarize_transcript(transcript, style="detailed", chunk_size=1000)
        self.assertEqual(len(summary.key_points), 20)
        self.assertIn("Topic 0 was reviewed.", summary.key_points)


class TranscriptionFailureTests(unittest.TestCase):
    def test_model_failure_is_reported_as_transcription_error(self):
        with patch("faster_whisper.WhisperModel", side_effect=RuntimeError("model load failed")):
            with self.assertRaisesRegex(TranscriptionError, "Transcription failed: model load failed"):
                transcribe("recording.wav")

    def test_no_speech_is_reported_clearly(self):
        model = SimpleNamespace(transcribe=lambda *args, **kwargs: (iter(()), SimpleNamespace(duration=1)))
        with patch("faster_whisper.WhisperModel", return_value=model):
            with self.assertRaisesRegex(TranscriptionError, "No speech was detected"):
                transcribe("silent.wav")


if __name__ == "__main__":
    unittest.main()
