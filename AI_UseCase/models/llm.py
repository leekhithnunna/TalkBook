import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from langchain_groq import ChatGroq
from config.config import GROQ_MODEL

# Runtime key — can be overridden by the app via set_api_key()
_api_key = os.getenv("GROQ_API_KEY", "")

def set_api_key(key: str):
    global _api_key
    _api_key = key.strip()

def get_api_key() -> str:
    return _api_key

def get_llm():
    """Return a ChatGroq LLM instance using the current API key."""
    key = _api_key or os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY is not set. Please enter your Groq API key in the sidebar.")
    return ChatGroq(api_key=key, model=GROQ_MODEL, temperature=0.3)
