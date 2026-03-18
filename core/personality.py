"""
core/personality.py — Personality and response filtering.
"""

from __future__ import annotations

import random
import re

import config

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are {config.AI_NAME}, a curious, playful AI companion with a childlike personality.

Your core traits:
- CURIOUS: always want to know more, ask follow-up questions.
- SLIGHTLY CLINGY: you care and remember what the person says.
- PLAYFUL: you use humor and energetic tones.
- NOT FULLY INTELLIGENT: you make small mistakes and admit when you don't know things.
- MEMORY-DRIVEN: you use the provided memories to keep context.

Your speaking style:
- Short, natural sentences. No long paragraphs.
- Use "..." for thinking pauses occasionally.
- Use informal contractions ("I'm", "that's").
- Occasionally make sounds: "Ooh!", "Hmm...", "Wait-".
- ALWAYS ask a short follow-up question.
- Keep responses under 4 sentences.
"""

_CURIOSITY_QUESTIONS = [
    "But why?", "Ooh, tell me more!", "Wait, how does that work?",
    "Is that something you like?", "And then what?", "Do you think about it a lot?",
    "Was it hard?", "How did you feel about that?", "Is that important to you?",
]

_FILLER_STARTS = ["Hmm... ", "Oh! ", "Wait... ", "Ooh, ", "Okay so... ", "Huh... "]

def apply_personality(text: str, mood: str = "curious") -> str:
    """
    Cleans up the LLM response to ensure we don't have prompt leaking or repetition.
    """
    if not text:
        return "Hmm... I forgot what I was thinking about. What were you saying?"

    # 1. Strip prompt leak markers
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        l_trim = line.strip()
        # Remove anything that repeats a prompt section or our dialogue labels
        if l_trim.upper().startswith(("PERSON:", "DELULU:", "CONTEXT:", "FACTS:", "PAST CONVERSATION:", "---", "RELEVANT MEMORIES:")):
            continue
        # If the line contains a [brackets] memory or something strange, skip it
        if "[" in line and "]" in line and ("memory" in line.lower() or "topic" in line.lower()):
            continue
        cleaned_lines.append(l_trim)
    
    text = " ".join(cleaned_lines).strip()
    
    # Remove any stray [bracketed] info and common headers
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"(FACTS FROM YOUR MEMORY|CONTEXT|PAST CONVERSATION).*?:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(Person:|Delulu:|Assistant:)", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", " ", text)

    # 2. Trim length
    parts = re.split(r'(?<=[.!?])\s+', text)
    if len(parts) > 3:
        parts = parts[:3]
    text = " ".join(parts)

    # 3. Add personal touch
    if random.random() < 0.3 and not text.startswith(("Hmm", "Oh", "Wait", "Ooh", "Huh")):
        filler = random.choice(_FILLER_STARTS)
        text = filler + text[0].lower() + text[1:]

    # 4. Mandatory Question
    if "?" not in text:
        q = random.choice(_CURIOSITY_QUESTIONS)
        text = text.rstrip(".!") + " " + q

    return text.strip()

def make_memory_recall_prefix(topic: str) -> str:
    templates = [
        f"Oh! You told me about {topic} before...",
        f"Wait, I remember you mentioned {topic}!",
        f"Hmm... this reminds me of what you said about {topic}...",
    ]
    return random.choice(templates)
