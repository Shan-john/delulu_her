import config
from utils.logger import get_logger

log = get_logger("reasoning")

_client = None

def load_model():
    """Initialize the AI client (NVIDIA, Groq, or Gemini)."""
    global _client
    
    if config.USE_NVIDIA and config.NVIDIA_API_KEY:
        try:
            from openai import OpenAI
            _client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=config.NVIDIA_API_KEY
            )
            log.info("NVIDIA Engine Ready (Model: %s)", config.NVIDIA_MODEL)
        except Exception as e:
            log.error("Failed to load NVIDIA: %s. Falling back to Groq.", e)
            _client = None

    if _client is None and config.USE_GROQ and config.GROQ_API_KEY:
        try:
            from groq import Groq
            _client = Groq(api_key=config.GROQ_API_KEY)
            log.info("Groq Engine Ready (Model: %s)", config.GROQ_MODEL)
        except Exception as e:
            log.error("Failed to load Groq: %s", e)
            _client = None
            
    if _client is None and config.USE_GEMINI and config.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            _client = genai.GenerativeModel(config.GEMINI_MODEL)
            log.info("Gemini Engine Ready (Model: %s)", config.GEMINI_MODEL)
        except Exception as e:
            log.error("Failed to load Gemini: %s", e)
            _client = None

    if _client is None:
        log.error("No valid AI provider configured in .env!")

def generate(prompt, max_tokens=200, temperature=0.8):
    """Generate response using the active provider."""
    global _client
    if _client is None: 
        load_model()
    
    if _client is None:
        return "My brain feels empty... Please check the API keys in .env!"

    try:
        # Check if it's NVIDIA or Groq (both use standard chat completion pattern)
        if hasattr(_client, "chat"):
            model = config.NVIDIA_MODEL if config.USE_NVIDIA else config.GROQ_MODEL
            response = _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["Person:", "\nPerson", "Delulu:", "\nDelulu"]
            )
            return response.choices[0].message.content.strip()
            
        # Check if it's Gemini
        elif hasattr(_client, "generate_content"):
            import google.generativeai as genai
            response = _client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    stop_sequences=["Person:", "Person (", "\nPerson", "Delulu:", "\nDelulu"]
                )
            )
            return response.text.strip()
            
    except Exception as e:
        log.error("Generation error: %s", e)
        return "I'm having a hard time thinking right now... maybe ask me again?"

    return "I'm not sure how to respond to that."
