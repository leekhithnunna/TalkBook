import os

# --- LLM ---
# Default key must come from environment; avoid hardcoded secrets
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Vector Store (general chat RAG) ---
CHROMA_PERSIST_DIR = "./chroma_db"

# --- Vector Store (PDF chat RAG — separate) ---
PDF_CHROMA_DIR = "./pdf_chroma_db"

# --- Database ---
DB_PATH = "./db/bookings.db"

# --- Email (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

# --- App ---
MAX_HISTORY = 20
GUEST_CHAT_LIMIT = 5
APP_NAME = "TalkBook"
