import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from langchain_huggingface import HuggingFaceEmbeddings
from config.config import EMBEDDING_MODEL

_embeddings = None

def get_embeddings():
    """Return a singleton HuggingFace embeddings instance."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings
