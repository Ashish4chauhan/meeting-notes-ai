from pathlib import Path

from meeting_app.audio import validate_audio_file
from meeting_app.summarize import summarize_transcript
from meeting_app.storage import MeetingStore
from meeting_app.exporters import export_meeting

import tempfile
import unittest


class AudioValidationTests(unittest.TestCase):
    def test_rejects_missing_audio_file(self):
        with self.assertRaises(FileNotFoundError):
            validate_audio_file(Path('does-not-exist.wav'))

    def test_rejects_empty_audio_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.wav'
            path.touch()
            with self.assertRaisesRegex(ValueError, 'empty'):
                validate_audio_file(path)

    def test_rejects_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'notes.txt'
            path.write_text('not audio', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                validate_audio_file(path)


class SummarizationTests(unittest.TestCase):
    def test_extracts_only_supported_decisions_tasks_and_points(self):
        transcript = (
            '[00:00:02] Alex: We decided to launch on Friday.\n'
            '[00:00:05] Sam: I will send the revised budget by Monday.\n'
            '[00:00:08] Alex: The beta feedback was mostly positive.'
        )
        summary = summarize_transcript(transcript, style='concise')
        self.assertTrue(any('launch on Friday' in item for item in summary.decisions))
        self.assertTrue(any('send the revised budget by Monday' in item for item in summary.tasks))
        self.assertTrue(any('beta feedback was mostly positive' in item for item in summary.key_points))
        self.assertEqual(summary.deadlines, ['Friday', 'Monday'])

    def test_empty_transcript_returns_empty_sections(self):
        summary = summarize_transcript('  ')
        self.assertEqual(summary.decisions, [])
        self.assertEqual(summary.tasks, [])
        self.assertEqual(summary.key_points, [])


class StorageTests(unittest.TestCase):
    def test_meeting_round_trips_through_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MeetingStore(Path(directory) / 'meetings.sqlite3')
            meeting_id = store.save_meeting('Planning', 'transcript', 'summary', '[]')
            saved = store.get_meeting(meeting_id)
            self.assertEqual(saved['title'], 'Planning')
            self.assertEqual(saved['transcript'], 'transcript')
            self.assertEqual(len(store.list_meetings()), 1)


class ExportTests(unittest.TestCase):
    def test_exports_text_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meeting.txt'
            export_meeting(path, 'Planning', 'Transcript body', 'Summary body')
            self.assertIn('Transcript body', path.read_text(encoding='utf-8'))

    def test_rejects_unknown_export_format(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Choose a'):
                export_meeting(Path(directory) / 'meeting.csv', 'x', 'y', 'z')


if __name__ == '__main__':
    unittest.main()
