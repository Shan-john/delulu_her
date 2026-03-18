import os
import config
from core.personality import SYSTEM_PROMPT
from consciousness.state import get_state
from memory.retriever import retrieve_memories
from memory.extractor import Extraction
from memory.database import get_db
from utils.logger import get_logger

log = get_logger("prompt_builder")

def build_prompt(user_text: str, extraction: Extraction, session_id: str) -> str:
    """Construct a clean, non-leaking prompt for Gemini."""
    
    state     = get_state()
    mood      = state.get("mood", "curious")
    curiosity = float(state.get("curiosity_level", 0.7))
    thought   = state.get("current_thought", "...")
    
    current_lang = config.CURRENT_LANGUAGE
    if current_lang == "ml":
        lang_instruction = (
            "IMPORTANT: Speak only in Malayalam (മലയാളം). "
            "Use natural, conversational, and friendly Malayalam (സംസാരഭാഷ). "
            "Avoid formal or textbook-style words. Keep it simple and childlike."
        )
    else:
        lang_instruction = "Please respond in English."
    
    # Simple, instruction-based system prompt
    # No "header-style" labels that invite completion.
    instructions = f"""{SYSTEM_PROMPT}

Your current mood is {mood}. Your curiosity is {curiosity:.1f}/1.0. 
Internal thought: {thought}
{lang_instruction}

If the user says 'Speak in Malayalam', then from then on, only speak Malayalam. If they say 'English', switch back.

---
RELEVANT MEMORIES (Only use these if they actually help):
{_format_memories(retrieve_memories(user_text, extraction.topics))}

---
PAST CONVERSATION:
"""
    history = _get_recent_history(session_id)
    history_str = ""
    for msg in history:
        role = "Person" if msg.get("role") == "user" else "Delulu"
        history_str += f"{role}: {msg.get('content')}\n"
    
    # We strip any trailing "Delulu:" from the end of the prompt if it exists,
    # and just end with "Delulu:" to encourage completion.
    full_prompt = f"{instructions}\n{history_str}Person: {user_text}\nDelulu:"
    
    return full_prompt

def _format_memories(memories: list) -> str:
    if not memories: return "I don't have enough memories about this yet."
    lines = []
    for m in memories[:5]:
        lines.append(f"- {m.get('data', '?')}")
    return "\n".join(lines)

def _get_recent_history(session_id: str, n: int = 4) -> list:
    try:
        db = get_db()
        conv = db.conversations.find_one({"session_id": session_id})
        if not conv: return []
        msgs = conv.get("messages", [])
        return msgs[-(n * 2):] if len(msgs) > 0 else []
    except: return []
