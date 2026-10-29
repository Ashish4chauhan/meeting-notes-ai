from dataclasses import asdict, dataclass
import re

@dataclass
class MeetingSummary:
    overview: str
    decisions: list[str]
    key_points: list[str]
    tasks: list[str]
    deadlines: list[str]

    def to_dict(self):
        return asdict(self)

    def render(self, style: str = "concise") -> str:
        lines = ["Meeting Summary", "===============", self.overview or "No summary available."]
        for heading, items in (("Decisions", self.decisions), ("Key discussion points", self.key_points), ("Tasks", self.tasks), ("Deadlines", self.deadlines)):
            lines.extend(["", heading])
            lines.extend([f"- {item}" for item in items] or ["- None identified in the transcript."])
        return "\n".join(lines)


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]


def summarize_transcript(transcript: str, style: str = "concise", chunk_size: int = 5000) -> MeetingSummary:
    """Extract evidence-bearing items with conservative pattern matching; never calls a remote API."""
    if style not in {"concise", "detailed"}:
        raise ValueError("style must be 'concise' or 'detailed'")
    sentences = _sentences(transcript)
    if not sentences:
        return MeetingSummary("", [], [], [], [])
    # Chunk then merge by sentence-level evidence, keeping this safe for very long transcripts.
    chunks = [sentences[i:i + max(1, chunk_size // 100)] for i in range(0, len(sentences), max(1, chunk_size // 100))]
    decisions, tasks, points, deadlines = [], [], [], []
    decision_re = re.compile(r"\b(decided|decision|agreed|approved|we will|will proceed|chosen|selected)\b", re.I)
    task_re = re.compile(r"\b(I will|we will|will (?:send|share|prepare|create|review|follow|update|deliver|complete|finish|schedule|contact|draft|provide)|needs? to|must|action item|assigned to|owner:)\b", re.I)
    date_re = re.compile(r"\b(?:today|tomorrow|tonight|next\s+(?:week|month|Monday|Tuesday|Wednesday|Thursday|Friday)|(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)|\d{4}-\d{2}-\d{2})\b", re.I)
    for chunk in chunks:
        for sentence in chunk:
            content = re.sub(r"^\[\d{2}:\d{2}(?::\d{2})?\]\s*", "", sentence)
            content = re.sub(r"^[^:]{1,40}:\s*", "", content)
            if decision_re.search(content): decisions.append(content)
            if task_re.search(content): tasks.append(content)
            dates = date_re.findall(content)
            deadlines.extend(dates)
            if not decision_re.search(content) and not task_re.search(content): points.append(content)
    unique = lambda items: list(dict.fromkeys(items))
    points = unique(points)
    if style == "concise": points = points[:5]
    else: points = points[:20]
    overview = " ".join(points[:2] if style == "concise" else points[:5])
    return MeetingSummary(overview, unique(decisions), points, unique(tasks), unique(deadlines))

