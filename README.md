# Delulu Her — Local AI Companion

A fully local, lightweight AI companion designed to run on a Raspberry Pi 5 or a laptop.
Delulu Her behaves like a curious, somewhat chaotic, and slightly clingy companion. She learns from your conversations, builds a long-term memory in MongoDB, and even generates her own spontaneous thoughts when it’s quiet.

## Core Architecture

Intelligence = Small Language Model (`TinyLlama 1.1B`) + Local Memory (`MongoDB`) + Continuous Processing Loops.

1. **Audio Input**: Listens via microphone, buffering speech using Voice Activity Detection (VAD).
2. **Speech-to-Text**: Transcribes audio locally using `Whisper Tiny`.
3. **Memory Pipeline**: Extracts facts, topics, and events from your speech, storing them in MongoDB.
4. **Reasoning Layer**: Retrieves relevant memories and current internal state (mood), then constructs an augmented prompt for the TinyLlama model via `llama-cpp-python`.
5. **TTS Output**: Speaks responses aloud using `Piper TTS` (or `pyttsx3` fallback).
6. **Consciousness Loop**: A background process that randomly generates thoughts and occasionally speaks them based on environmental silence, mood decay, and memory recall.

## Setup Requirements

### 1. Python Dependencies

Create a virtual environment (Python 3.10+ recommended) and install the packages:

```bash
pip install -r requirements.txt
```

### 2. MongoDB

You need a local MongoDB instance running.

- **Windows/macOS**: Install [MongoDB Community Edition](https://www.mongodb.com/try/download/community).
- **Linux / Raspberry Pi**: `sudo apt install mongodb-server` (or run via Docker: `docker run -d -p 27017:27017 mongo`)

### 3. Download the TinyLlama Model

Download the GGUF model file and place it in a `models/` directory:

1. Download: [TinyLlama-1.1B-Chat-v1.0.Q4_K_M.gguf](https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf?download=true)
2. Create: `mkdir models`
3. Move the `.gguf` file into `models/`.

### 4. Piper TTS (Optional but recommended)

If you want the most natural sounding voice offline, install [Piper](https://github.com/rhasspy/piper/releases).

1. Download the executable for your OS and extract it to a `piper/` folder in this project.
2. Download a voice model (e.g., `en_US-amy-medium.onnx` and its `.json`) from [Piper Voices](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US) into `piper/voices/`.
3. If Piper is not detected, the system will automatically fall back to `pyttsx3`.

## Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Review the `.env` settings.
**Important**: If you do not have a microphone connected during development, set `TEXT_INPUT_MODE=true` in `.env` to type your messages instead of speaking.

## Running the System

```bash
python main.py
```

### Text Mode Example

If `TEXT_INPUT_MODE=true`:

```text
==================================================
  Delulu is listening (text mode).
  Type your message and press Enter.
==================================================

You: I am learning how to use Kubernetes.
[12:34:56] main INFO     👤 User: I am learning how to use Kubernetes.
[12:34:56] learner INFO  🧠 Learned: [kubernetes] am learning how to use
[12:34:56] main INFO     💭 Thinking...
[12:34:58] main INFO     ✨ Delulu: Ooh... Kubernetes! Is that hard to learn? Wait, what does it actually do?
```

## Collections Reference

If you want to view Delulu's memories, connect to your local MongoDB (database `delulu_her`) and inspect the collections:

- `memories`: Core learned facts and recall counts.
- `knowledge`: Broad topic domain knowledge.
- `conversations`: Raw chat logs grouped by session.
- `events`: Life events flagged for follow-up.
- `internal_state`: The single document representing her current mood, curiosity, energy, and thoughts.
