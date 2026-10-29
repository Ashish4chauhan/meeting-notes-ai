# Meeting Notes AI

A local-first Windows desktop application for recording or importing meeting audio, transcribing it, extracting transcript-backed decisions and action items, and keeping meeting history on this computer.

## Features

- Import audio files or record a meeting from the default microphone.
- Transcribe locally with faster-whisper; transcript segments include timestamps.
- Create concise or detailed meeting notes with likely decisions, discussion points, and action items.
- Save meetings in a local SQLite database and reopen them from History.
- Export notes as TXT, PDF, or DOCX.
- Keep long-running recording and transcription work off the GUI thread.

## Requirements

- Windows 10/11 and Python 3.10 or newer (tested with Python 3.10.11).
- Internet access the first time a Whisper model is selected so faster-whisper can download model files. Cached models can be used offline.
- A working microphone for live recording. The default configuration uses CPU int8. GPU acceleration is optional and requires compatible NVIDIA drivers and CUDA/cuDNN for CTranslate2.

## Setup

Open PowerShell in this project folder:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `py` is not available, use the full path to your Python 3.10 executable.

## Run

```powershell
python main.py
```

Choose an audio file and select a model and summary length, then press **Transcribe**. For a live meeting, select **Start live recording** and then **Stop & transcribe**. The app saves a mono 16 kHz WAV recording locally, then transcribes it. The first model download may take time. Use **History** to reopen meetings and **Export…** to save a TXT, PDF, or DOCX copy.

## Data and privacy

Audio and transcripts are processed on this computer. No external summarization API or API key is used. The summary is a transcript-grounded extraction based on phrase rules; it can miss implied items or classify wording imperfectly, so review the notes. Speaker diarization is not implemented.

The SQLite meeting database is stored at `%LOCALAPPDATA%\MeetingNotesAI\meetings.sqlite3`, and microphone recordings are stored under `%LOCALAPPDATA%\MeetingNotesAI\recordings`. Whisper model files are downloaded from the model hub on first use.

## Project structure

```text
main.py
meeting_app/   Tkinter interface, audio, recording, transcription, summary, storage, exports
tests/         Unit and edge-case tests
requirements.txt
```

Run tests with `python -m unittest discover -v`.
