"""
_write_prompt_builder.py
Run once to generate core/prompt_builder.py with ChatML tags intact.
Usage: python _write_prompt_builder.py
"""
import os

# ChatML format tokens (TinyLlama uses these)
# We build them dynamically to avoid XML stripping by editors/tools
LT  = chr(60)   # <
GT  = chr(62)   # >
BAR = chr(124)  # |

def tok(name: str) -> str:
    return LT + BAR + name + BAR + GT

SYS_TAG  = tok("system")
USR_TAG  = tok("user")
AST_TAG  = tok("assistant")

code = f'''\
"""
core/prompt_builder.py
Build memory-augmented prompts for TinyLlama (ChatML format).

Injects:
  1. System personality prompt + internal state
  2. Retrieved memories as context
  3. Recent conversation history (last 6 messages / 3 turns)
  4. Current user input
"""

from __future__ import annotations

from core.personality import SYSTEM_PROMPT
from consciousness.state import get_state
from memory.retriever import retrieve_memories
from memory.extractor import Extraction
from memory.database import get_db
from utils.logger import get_logger
import config

log = get_logger("prompt_builder")

_SYSTEM_BUDGET = 700
_MEMORY_BUDGET = 500

# ChatML tokens for TinyLlama
_SYS = "{SYS_TAG}"
_USR = "{USR_TAG}"
_AST = "{AST_TAG}"


def build_prompt(user_text: str, extraction: Extraction, session_id: str) -> str:
    """Construct the full memory-augmented TinyLlama ChatML prompt."""
    state     = get_state()
    mood      = state.get("mood", "curious")
    curiosity = float(state.get("curiosity_level", 0.7))
    thought   = state.get("current_thought", "...")

    system = (
        SYSTEM_PROMPT
        + f"\\n\\nCurrent mood: {{mood}}.  Curiosity: {{curiosity:.1f}}/1.0.  Internal thought: {{thought}}"
    )
    system = system[:_SYSTEM_BUDGET]

    memories     = retrieve_memories(user_text, extraction.topics)
    memory_block = _format_memories(memories)[:_MEMORY_BUDGET]

    history = _get_recent_history(session_id)

    # Assemble
    parts = [_SYS + "\\n" + system + "\\n"]

    if memory_block:
        parts.append(_SYS + "\\nRelevant memories I have:\\n" + memory_block + "\\n")

    for msg in history:
        role    = msg.get("role", "user")
        content = msg.get("content", "")[:150]
        tag     = _USR if role == "user" else _AST
        parts.append(tag + "\\n" + content + "\\n")

    parts.append(_USR + "\\n" + user_text + "\\n")
    parts.append(_AST + "\\n")

    prompt = "".join(parts)
    log.debug("Prompt length: %d chars", len(prompt))
    return prompt


def _format_memories(memories: list) -> str:
    if not memories:
        return ""
    lines = []
    for m in memories[:5]:
        topic = m.get("topic", "?")
        data  = m.get("data",  "?")
        lines.append(f"- [{{topic}}] {{data}}")
    return "\\n".join(lines)


def _get_recent_history(session_id: str, n: int = 3) -> list:
    """Return last n*2 messages from the current conversation."""
    try:
        db = get_db()
        conv = db.conversations.find_one({{"session_id": session_id}})
        if not conv:
            return []
        msgs = conv.get("messages", [])
        return msgs[-(n * 2):] if len(msgs) > 0 else []
    except Exception:
        return []
'''

os.makedirs("core", exist_ok=True)
with open("core/prompt_builder.py", "w", encoding="utf-8") as f:
    f.write(code)

print("core/prompt_builder.py written successfully.")
