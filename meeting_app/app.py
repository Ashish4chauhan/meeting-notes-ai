import json
import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .audio import SUPPORTED_AUDIO_EXTENSIONS, validate_audio_file
from .exporters import export_meeting
from .recording import MicrophoneRecorder, RecordingError
from .storage import MeetingStore
from .summarize import summarize_transcript
from .transcription import transcribe

APP_NAME = "Meeting Notes AI"


def data_directory() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "MeetingNotesAI"
    root.mkdir(parents=True, exist_ok=True)
    return root


class MeetingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x760")
        self.minsize(850, 580)
        self.configure(bg="#f3f5f8")
        self.store = MeetingStore(data_directory() / "meetings.sqlite3")
        self.events = queue.Queue()
        self.audio_path = None
        self.transcript = ""
        self.summary = None
        self.segments = []
        self.busy = False
        self.is_recording = False
        self.recorder = None
        self.recording_started = None
        self._build_ui()
        self._refresh_history()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_events)

    def _build_ui(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("TFrame", background="#f3f5f8")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f3f5f8", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#101828")
        style.configure("Muted.TLabel", foreground="#667085")
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Accent.TButton", background="#315efb", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#244bd0"), ("disabled", "#a9b6ee")])
        style.configure("TNotebook", background="#ffffff", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI", 10))

        outer = ttk.Frame(self, padding=22); outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer); header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="Meeting Notes AI", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Transcribe locally, find decisions and action items, and keep a private meeting archive.", style="Muted.TLabel").pack(anchor="w", pady=(3, 0))

        controls = ttk.Frame(outer, style="Card.TFrame", padding=14); controls.pack(fill="x", pady=(0, 12))
        self.title_var = tk.StringVar(value=f"Meeting {datetime.now():%Y-%m-%d %H:%M}")
        ttk.Label(controls, text="Meeting name").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.title_var, width=30).grid(row=1, column=0, padx=(0, 14), sticky="ew")
        ttk.Label(controls, text="Audio file").grid(row=0, column=1, sticky="w")
        self.file_label = ttk.Label(controls, text="No file selected", style="Muted.TLabel", width=35)
        self.file_label.grid(row=1, column=1, padx=(0, 10), sticky="ew")
        ttk.Button(controls, text="Choose audio…", command=self._choose_audio).grid(row=1, column=2, padx=(0, 12))
        ttk.Label(controls, text="Model").grid(row=0, column=3, sticky="w")
        self.model_var = tk.StringVar(value="small")
        ttk.Combobox(controls, textvariable=self.model_var, values=("tiny", "base", "small", "medium", "large-v3"), state="readonly", width=12).grid(row=1, column=3, padx=(0, 12))
        ttk.Label(controls, text="Summary").grid(row=0, column=4, sticky="w")
        self.style_var = tk.StringVar(value="concise")
        ttk.Combobox(controls, textvariable=self.style_var, values=("concise", "detailed"), state="readonly", width=12).grid(row=1, column=4, padx=(0, 12))
        self.start_button = ttk.Button(controls, text="Transcribe", style="Accent.TButton", command=self._start)
        self.start_button.grid(row=1, column=5)
        self.record_button = ttk.Button(controls, text="Start live recording", command=self._start_recording)
        self.record_button.grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.stop_record_button = ttk.Button(controls, text="Stop & transcribe", command=self._stop_recording, state="disabled")
        self.stop_record_button.grid(row=2, column=1, sticky="w", pady=(12, 0))
        self.recording_hint = ttk.Label(controls, text="Microphone recording is saved on this computer.", style="Muted.TLabel")
        self.recording_hint.grid(row=2, column=2, columnspan=4, sticky="w", padx=(8, 0), pady=(12, 0))
        controls.columnconfigure(1, weight=1)

        status = ttk.Frame(outer); status.pack(fill="x", pady=(0, 10))
        self.progress = ttk.Progressbar(status, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.status_var = tk.StringVar(value="Ready. Select an audio file or start a live recording.")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel", width=45).pack(side="right")

        content = ttk.Frame(outer, style="Card.TFrame", padding=12); content.pack(fill="both", expand=True)
        self.tabs = ttk.Notebook(content); self.tabs.pack(fill="both", expand=True)
        transcript_tab = ttk.Frame(self.tabs, padding=8); summary_tab = ttk.Frame(self.tabs, padding=8); history_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(transcript_tab, text="Transcript"); self.tabs.add(summary_tab, text="Summary & actions"); self.tabs.add(history_tab, text="History")
        self.transcript_text = self._text_widget(transcript_tab)
        self.summary_text = self._text_widget(summary_tab)
        history_top = ttk.Frame(history_tab); history_top.pack(fill="x", pady=(0, 8))
        ttk.Button(history_top, text="Refresh", command=self._refresh_history).pack(side="left")
        ttk.Button(history_top, text="Open selected", command=self._open_history).pack(side="left", padx=8)
        self.history = ttk.Treeview(history_tab, columns=("date",), show="tree headings", height=7)
        self.history.heading("#0", text="Meeting"); self.history.heading("date", text="Created")
        self.history.column("#0", width=280); self.history.column("date", width=220)
        self.history.pack(fill="both", expand=True)

        footer = ttk.Frame(outer); footer.pack(fill="x", pady=(12, 0))
        ttk.Label(footer, text="Local processing • Recordings stay on this computer • No speaker labels", style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Export…", command=self._export).pack(side="right")

    def _text_widget(self, parent):
        frame = ttk.Frame(parent); frame.pack(fill="both", expand=True)
        widget = tk.Text(frame, wrap="word", undo=False, font=("Segoe UI", 10), bg="#fbfcfe", fg="#1f2937", relief="flat", padx=14, pady=12)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=widget.yview); widget.configure(yscrollcommand=scroll.set)
        widget.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        return widget

    def _choose_audio(self):
        path = filedialog.askopenfilename(title="Choose meeting audio", filetypes=[("Audio files", " ".join(f"*{x}" for x in sorted(SUPPORTED_AUDIO_EXTENSIONS))), ("All files", "*.*")])
        if path:
            self.audio_path = path
            self.file_label.configure(text=Path(path).name)

    def _start(self):
        if self.busy:
            return
        try:
            audio = validate_audio_file(self.audio_path or "")
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror("Audio file", str(exc))
            return
        self._process_audio(audio)

    def _process_audio(self, audio):
        self.busy = True
        self.start_button.configure(state="disabled")
        self.record_button.configure(state="disabled")
        self.stop_record_button.configure(state="disabled")
        self.progress.configure(value=0)
        self.status_var.set("Loading model and transcribing… First run may download model files.")
        model = self.model_var.get()
        style = self.style_var.get()
        title = self.title_var.get().strip() or Path(audio).stem
        threading.Thread(target=self._worker, args=(audio, model, style, title), daemon=True).start()

    def _start_recording(self):
        if self.busy:
            return
        filename = datetime.now().strftime("recording_%Y%m%d_%H%M%S.wav")
        recording_path = data_directory() / "recordings" / filename
        self.recorder = MicrophoneRecorder(recording_path)
        try:
            self.recorder.start()
        except RecordingError as exc:
            self.recorder = None
            messagebox.showerror("Microphone recording", str(exc))
            return
        self.busy = True
        self.is_recording = True
        self.recording_started = time.monotonic()
        self.start_button.configure(state="disabled")
        self.record_button.configure(state="disabled")
        self.stop_record_button.configure(state="normal")
        self.progress.configure(value=0)
        self._update_recording_status()

    def _update_recording_status(self):
        if not self.is_recording:
            return
        elapsed = int(time.monotonic() - self.recording_started)
        minutes, seconds = divmod(elapsed, 60)
        self.status_var.set(f"Recording microphone • {minutes:02d}:{seconds:02d} • saved locally")
        self.after(1000, self._update_recording_status)

    def _stop_recording(self):
        if not self.is_recording or self.recorder is None:
            return
        self.is_recording = False
        self.stop_record_button.configure(state="disabled")
        try:
            audio = self.recorder.stop()
        except RecordingError as exc:
            self.busy = False
            self.recorder = None
            self._set_idle_controls()
            self.status_var.set("Microphone recording could not be completed")
            messagebox.showerror("Microphone recording", str(exc))
            return
        self.recorder = None
        self.audio_path = audio
        self.file_label.configure(text=f"Recorded: {audio.name}")
        self._process_audio(audio)

    def _set_idle_controls(self):
        self.start_button.configure(state="normal")
        self.record_button.configure(state="normal")
        self.stop_record_button.configure(state="disabled")

    def _on_close(self):
        if self.is_recording and self.recorder is not None:
            self.is_recording = False
            try:
                self.recorder.stop()
            except Exception:
                pass
        self.destroy()

    def _worker(self, audio, model, style, title):
        try:
            transcript, segments = transcribe(audio, model_size=model, progress=lambda n: self.events.put(("progress", n)))
            self.events.put(("status", "Preparing transcript-backed summary…"))
            summary = summarize_transcript(transcript, style=style)
            meeting_id = self.store.save_meeting(title, transcript, summary.render(style), json.dumps(segments))
            self.events.put(("done", (meeting_id, transcript, summary, segments)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress": self.progress.configure(value=payload); self.status_var.set(f"Transcribing… {payload}%")
                elif kind == "status": self.status_var.set(payload)
                elif kind == "done":
                    meeting_id, self.transcript, self.summary, self.segments = payload
                    self._display_results(); self._refresh_history(); self.progress.configure(value=100)
                    self.status_var.set(f"Complete • meeting #{meeting_id} saved locally")
                    self.busy = False; self._set_idle_controls()
                elif kind == "error":
                    self.busy = False; self._set_idle_controls(); self.progress.configure(value=0)
                    self.status_var.set("Could not complete transcription")
                    messagebox.showerror("Processing failed", payload)
        except queue.Empty: pass
        self.after(100, self._poll_events)

    def _display_results(self):
        self.transcript_text.delete("1.0", "end"); self.transcript_text.insert("1.0", self.transcript)
        self.summary_text.delete("1.0", "end"); self.summary_text.insert("1.0", self.summary.render(self.style_var.get()))
        self.tabs.select(1)

    def _refresh_history(self):
        for item in self.history.get_children(): self.history.delete(item)
        for row in self.store.list_meetings():
            try: date = datetime.fromisoformat(row["created_at"]).astimezone().strftime("%Y-%m-%d %H:%M")
            except Exception: date = row["created_at"]
            self.history.insert("", "end", iid=str(row["id"]), text=row["title"], values=(date,))

    def _open_history(self):
        selected = self.history.selection()
        if not selected: return
        meeting = self.store.get_meeting(int(selected[0]))
        if not meeting: return
        self.title_var.set(meeting["title"]); self.transcript = meeting["transcript"]
        self.transcript_text.delete("1.0", "end"); self.transcript_text.insert("1.0", self.transcript)
        self.summary_text.delete("1.0", "end"); self.summary_text.insert("1.0", meeting["summary"])
        self.summary = None; self.segments = json.loads(meeting["segments_json"] or "[]")
        self.tabs.select(0); self.status_var.set("Loaded a saved meeting from local history")

    def _export(self):
        if not self.transcript:
            messagebox.showinfo("Export", "Transcribe or open a saved meeting first."); return
        path = filedialog.asksaveasfilename(title="Export meeting notes", defaultextension=".txt", filetypes=[("Text", "*.txt"), ("PDF", "*.pdf"), ("Word document", "*.docx")])
        if not path: return
        summary = self.summary.render(self.style_var.get()) if self.summary else self.summary_text.get("1.0", "end").strip()
        try:
            export_meeting(path, self.title_var.get().strip() or "Meeting", self.transcript, summary, self.segments)
            self.status_var.set(f"Exported to {Path(path).name}")
        except Exception as exc: messagebox.showerror("Export failed", str(exc))


def main():
    app = MeetingApp()
    app.mainloop()

if __name__ == "__main__": main()
