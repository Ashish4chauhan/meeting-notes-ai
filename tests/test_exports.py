import tempfile
import unittest
from pathlib import Path

from meeting_app.exporters import export_meeting


class NativeFormatExportTests(unittest.TestCase):
    def test_exports_docx(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meeting.docx'
            export_meeting(path, 'Planning', 'Transcript body', 'Summary body')
            self.assertEqual(Document(path).paragraphs[0].text, 'Planning')

    def test_exports_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meeting.pdf'
            export_meeting(path, 'Planning', 'Transcript body', 'Summary body')
            self.assertTrue(path.read_bytes().startswith(b'%PDF-'))

    def test_export_surfaces_destination_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing' / 'meeting.txt'
            with self.assertRaises(FileNotFoundError):
                export_meeting(path, 'Planning', 'Transcript body', 'Summary body')
