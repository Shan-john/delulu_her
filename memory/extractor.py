"""
memory/extractor.py — Extract structured meaning from user text.

Uses simple rule-based extraction plus an optional LLM call
for deeper topic/fact identification.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

from utils.logger import get_logger

if TYPE_CHECKING:
    pass

log = get_logger("extractor")

# ── Life-event trigger keywords ───────────────────────────────────────────────
_EVENT_TRIGGERS = [
    r"\b(going to|starting|joining|beginning|attending)\b.{0,30}\b(college|university|school|job|work|course|class|exam|interview)\b",
    r"\b(i (got|have|just|am)) .{0,20}\b(job|offer|admission|internship|exam|test|appointment|meeting|date)\b",
    r"\b(moving|relocating|shifting)\b.{0,20}\b(to|from|house|city|country|flat|apartment)\b",
    r"\b(getting|got|i am|i'm).{0,10}(married|engaged|divorced|pregnant)\b",
    r"\b(project|assignment|deadline|submission|launch|release)\b.{0,20}\b(is|due|in|on)\b",
]

# ── Facts: "X is/does/means Y" patterns ──────────────────────────────────────
_FACT_PATTERNS = [
    r"(?P<topic>[\w\s]{2,30}?)\s+(is|are|means|works?|does|manages?|handles?|runs?)\s+(?P<data>.{5,120})",
    r"(?P<topic>[\w\s]{2,30}?)\s+(?P<data>can .{5,80})",
    r"(?P<topic>[\w\s]{2,30}?)\s+(helps?|allows?|lets?|enables?)\s+(?P<data>.{5,80})",
]

# ── Question words ─────────────────────────────────────────────────────────
_QUESTION_WORDS = {"what", "why", "how", "when", "where", "who", "which", "can", "could", "would", "is", "are", "do", "does"}


class Extraction:
    """Result of extracting meaning from a user utterance."""

    def __init__(self):
        self.facts: list[dict] = []        # [{"topic": ..., "data": ...}]
        self.events: list[str] = []        # life events detected
        self.topics: list[str] = []        # main topics mentioned
        self.is_question: bool = False     # True if user is asking something
        self.raw_text: str = ""


def extract(text: str) -> Extraction:
    """
    Extract structured meaning from user text using Regex only.
    """
    result = Extraction()
    result.raw_text = text

    text_lower = text.lower().strip()
    if not text_lower: return result

    # ── Is it a question? ──────────────────────────────────────────────────
    words = text_lower.split()
    first_word = words[0] if words else ""
    result.is_question = (
        text.strip().endswith("?")
        or first_word in _QUESTION_WORDS
    )

    # ── Extract facts ─────────────────────────────────────────────────────
    for pattern in _FACT_PATTERNS:
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            topic = match.group("topic").strip()
            data  = match.group("data").strip()
            if len(topic) > 1 and len(data) > 3:
                result.facts.append({"topic": topic, "data": data})
                if topic not in result.topics:
                    result.topics.append(topic)

    # ── Detect life events ────────────────────────────────────────────────
    for pattern in _EVENT_TRIGGERS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            result.events.append(text[:200])  # Store the original sentence
            break

    # ── Keyword topic extraction (fallback) ───────────────────────────────
    if not result.topics:
        result.topics = _extract_keywords(text_lower)

    return result

def ai_extract(text: str, generate_fn: Callable[[str], str]) -> Extraction:
    """
    Use an LLM to extract facts and topics more accurately than regex.
    """
    result = extract(text) # start with regex basics
    
    prompt = f"""Summarize ANY important facts or topics from this user message. 
If the user mentions their name, likes, job, or plans, include them.
Format as: TOPIC|FACT
Example: shan john|The user's name is Shan John.
Example: college|The user is going to college today.

Message: "{text}"
Extraction:"""
    
    response = generate_fn(prompt) # reasoning.generate
    
    for line in response.split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            topic = parts[0].strip().lower()
            data = parts[1].strip()
            
            if topic and data and len(topic) < 30 and len(data) > 3:
                # Add to result if not a near-duplicate
                if not any(f["topic"] == topic for f in result.facts):
                    result.facts.append({"topic": topic, "data": data})
                if topic not in result.topics:
                    result.topics.append(topic)
                    
    log.debug("AI Extracted facts: %d", len(result.facts))
    return result


# ── Simple keyword extractor ────────────────────────────────────────────────
_STOPWORDS = {
    "i", "me", "my", "you", "your", "the", "a", "an", "is", "are", "was",
    "were", "it", "in", "on", "at", "to", "of", "and", "or", "but", "that",
    "this", "for", "with", "about", "just", "so", "do", "does", "did", "have",
    "has", "had", "be", "been", "can", "could", "would", "will", "not", "im",
    "its", "what", "how", "when", "where", "who", "yeah", "yes", "no", "okay",
}

def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"\b[a-z][a-z0-9]{2,}\b", text.lower())
    seen: list[str] = []
    for w in words:
        if w not in _STOPWORDS and w not in seen:
            seen.append(w)
    return seen[:5]
