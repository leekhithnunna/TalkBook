"""
Two separate RAG pipelines:
  - General knowledge base (CHROMA_PERSIST_DIR)
  - Per-session PDF chat (PDF_CHROMA_DIR)
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from models.embeddings import get_embeddings
from config.config import CHROMA_PERSIST_DIR, PDF_CHROMA_DIR

_general_vs  = None
_pdf_vs      = None

# ── helpers ───────────────────────────────────────────────────────────────────
def _upsert_to_chroma(persist_dir: str, chunks, id_prefix: str = "doc") -> Chroma:
    embeddings = get_embeddings()
    texts     = [c.page_content for c in chunks]
    metadatas = [c.metadata     for c in chunks]
    vectors   = embeddings.embed_documents(texts)
    if not vectors:
        raise ValueError("Embedding model returned empty vectors.")
    vs = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
    vs._collection.upsert(
        ids       = [f"{id_prefix}_{i}" for i in range(len(texts))],
        documents = texts,
        embeddings= vectors,
        metadatas = metadatas,
    )
    return vs

def _load_chroma(persist_dir: str) -> Chroma | None:
    embeddings = get_embeddings()
    if os.path.exists(persist_dir) and os.listdir(persist_dir):
        try:
            return Chroma(persist_directory=persist_dir, embedding_function=embeddings)
        except Exception:
            pass
    return None

def _chunk_pdf(file_path: str):
    loader  = PyPDFLoader(file_path)
    docs    = loader.load()
    if not docs:
        raise ValueError("PDF is empty or unreadable.")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks   = splitter.split_documents(docs)
    if not chunks:
        raise ValueError("No text could be extracted from the PDF.")
    return chunks

# ── General knowledge base ────────────────────────────────────────────────────
def load_vectorstore():
    global _general_vs
    if _general_vs is None:
        _general_vs = _load_chroma(CHROMA_PERSIST_DIR)
    return _general_vs

def ingest_pdf(file_path: str) -> int:
    global _general_vs
    chunks = _chunk_pdf(file_path)
    _general_vs = _upsert_to_chroma(CHROMA_PERSIST_DIR, chunks)
    return len(chunks)

def retrieve_context(query: str, k: int = 4) -> str:
    global _general_vs
    if _general_vs is None:
        _general_vs = load_vectorstore()
    if _general_vs is None:
        return ""
    try:
        docs = _general_vs.similarity_search(query, k=k)
        return "\n\n".join(d.page_content for d in docs)
    except Exception:
        return ""

# ── PDF Chat (separate, per-upload) ──────────────────────────────────────────
def ingest_pdf_for_chat(file_path: str) -> int:
    """Ingest a PDF into the dedicated PDF-chat vector store."""
    global _pdf_vs
    chunks  = _chunk_pdf(file_path)
    _pdf_vs = _upsert_to_chroma(PDF_CHROMA_DIR, chunks, id_prefix="pdf")
    return len(chunks)

def retrieve_from_pdf(query: str, k: int = 4) -> str:
    global _pdf_vs
    if _pdf_vs is None:
        _pdf_vs = _load_chroma(PDF_CHROMA_DIR)
    if _pdf_vs is None:
        return ""
    try:
        docs = _pdf_vs.similarity_search(query, k=k)
        return "\n\n".join(d.page_content for d in docs)
    except Exception:
        return ""

def pdf_vs_ready() -> bool:
    global _pdf_vs
    if _pdf_vs is not None:
        return True
    _pdf_vs = _load_chroma(PDF_CHROMA_DIR)
    return _pdf_vs is not None
