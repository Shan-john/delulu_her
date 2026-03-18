"""
_write_reasoning.py
Generates core/reasoning.py with stop-token strings intact.
Run: python _write_reasoning.py
"""
import os

LT  = chr(60)
GT  = chr(62)
BAR = chr(124)
SL  = chr(47)

def tok(name: str) -> str:
    return LT + BAR + name + BAR + GT

def etok(name: str) -> str:
    return LT + SL + name + GT

STOP_USER = tok("user")
STOP_SYS  = tok("system")
EOS       = LT + SL + "s" + GT   # </s>

code = f'''\
"""
core/reasoning.py
TinyLlama 1.1B inference via llama-cpp-python.
CPU-optimized for Raspberry Pi 5 / laptop.
"""

from __future__ import annotations

import config
from utils.logger import get_logger

log = get_logger("reasoning")

_llm = None

# Tokens that signal the model should stop generating
_STOP_TOKENS = ["{EOS}", "{STOP_USER}", "{STOP_SYS}"]


def load_model() -> None:
    """Load TinyLlama GGUF model — call once at startup."""
    global _llm
    from llama_cpp import Llama

    model_path = str(config.MODEL_PATH)
    log.info("Loading model: %s", model_path)
    log.info("CPU threads=%d  GPU layers=%d  Context=%d",
             config.MODEL_THREADS, config.MODEL_GPU_LAYERS, config.MODEL_CTX)

    _llm = Llama(
        model_path=model_path,
        n_ctx=config.MODEL_CTX,
        n_threads=config.MODEL_THREADS,
        n_gpu_layers=config.MODEL_GPU_LAYERS,
        verbose=False,
    )
    log.info("Model ready.")


def generate(prompt: str, max_tokens: int = 150, temperature: float = 0.8) -> str:
    """
    Run inference on TinyLlama.

    Returns generated text string (stripped).
    Falls back to a canned response if model is not loaded.
    """
    if _llm is None:
        log.error("Model not loaded! Call load_model() first.")
        return "I... I can\'t think right now... sorry."

    try:
        output = _llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            stop=_STOP_TOKENS,
            echo=False,
        )
        text = output["choices"][0]["text"].strip()
        log.debug("Generated %d chars", len(text))
        return text

    except Exception as e:
        log.error("Inference error: %s", e)
        return "Hmm... I got confused. Can you say that again?"


def is_ready() -> bool:
    return _llm is not None
'''

os.makedirs("core", exist_ok=True)
with open("core/reasoning.py", "w", encoding="utf-8") as f:
    f.write(code)

print("core/reasoning.py written successfully.")
