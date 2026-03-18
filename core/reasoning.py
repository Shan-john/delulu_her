import config
from utils.logger import get_logger

log = get_logger("reasoning")

_client = None

def load_model():
    """Initialize the AI client (Groq or Gemini)."""
    global _client
    
    if config.USE_GROQ and config.GROQ_API_KEY:
        try:
            from groq import Groq
            _client = Groq(api_key=config.GROQ_API_KEY)
            log.info("Groq Engine Ready (Model: %s)", config.GROQ_MODEL)
        except Exception as e:
            log.error("Failed to load Groq: %s", e)
            _client = None
            
    elif config.USE_GEMINI and config.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            _client = genai.GenerativeModel(config.GEMINI_MODEL)
            log.info("Gemini Engine Ready (Model: %s)", config.GEMINI_MODEL)
        except Exception as e:
            log.error("Failed to load Gemini: %s", e)
            _client = None
    else:
        log.error("No valid AI provider (Groq/Gemini) configured in .env!")
        _client = None

def generate(prompt, max_tokens=200, temperature=0.8):
    """Generate response using the active provider."""
    global _client
    if _client is None: 
        load_model()
    
    if _client is None:
        return "My brain feels empty... Please check the API keys in .env!"

    try:
        # Check if it's Groq
        if hasattr(_client, "chat"):
            response = _client.chat.completions.create(
                model=config.GROQ_MODEL,
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
