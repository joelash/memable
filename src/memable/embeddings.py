"""
Embeddings providers for memable with auto-detection.

Supports OpenAI and Ollama (local) embeddings with automatic fallback.
"""

import os
from typing import Literal
import httpx
from langchain_core.embeddings import Embeddings


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = "nomic-embed-text"


def is_ollama_available(host: str = OLLAMA_HOST, timeout: float = 2.0) -> bool:
    """Check if Ollama is running and accessible."""
    try:
        response = httpx.get(f"{host}/api/tags", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def has_ollama_model(model: str = DEFAULT_OLLAMA_MODEL, host: str = OLLAMA_HOST) -> bool:
    """Check if a specific embedding model is installed in Ollama."""
    try:
        response = httpx.get(f"{host}/api/tags")
        if response.status_code != 200:
            return False
        data = response.json()
        models = data.get("models", [])
        return any(m.get("name", "").startswith(model) for m in models)
    except Exception:
        return False


class OllamaEmbeddings(Embeddings):
    """
    Ollama embeddings provider for local-first mode.
    
    Uses nomic-embed-text by default (768 dimensions).
    
    Example:
        # First, ensure the model is installed:
        # $ ollama pull nomic-embed-text
        
        embeddings = OllamaEmbeddings()
        vectors = embeddings.embed_documents(["Hello world"])
    """
    
    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: str | None = None,
    ):
        self.model = model
        self.host = host or OLLAMA_HOST
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return [self._embed_single(text) for text in texts]
    
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        return self._embed_single(text)
    
    def _embed_single(self, text: str) -> list[float]:
        """Embed a single text using Ollama API."""
        response = httpx.post(
            f"{self.host}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]


EmbeddingProvider = Literal["openai", "ollama", "auto"]


def create_embeddings(
    provider: EmbeddingProvider = "auto",
    model: str | None = None,
) -> Embeddings:
    """
    Auto-detect and create the best available embeddings provider.
    
    Priority:
    1. MEMABLE_EMBEDDINGS=ollama → force Ollama
    2. MEMABLE_EMBEDDINGS=openai → force OpenAI
    3. OPENAI_API_KEY set → use OpenAI (explicit user intent)
    4. Auto-detect Ollama → use if available with model
    5. Error with helpful message
    
    Args:
        provider: Force a specific provider ('openai', 'ollama', or 'auto')
        model: Model name override (provider-specific)
    
    Returns:
        LangChain Embeddings instance
    
    Raises:
        RuntimeError: If no embedding provider is available
    """
    from langchain_openai import OpenAIEmbeddings
    
    # Check env var override
    env_provider = os.environ.get("MEMABLE_EMBEDDINGS", "").lower()
    if env_provider in ("openai", "ollama"):
        provider = env_provider  # type: ignore
    
    # 1. Explicit MEMABLE_EMBEDDINGS=ollama
    if provider == "ollama":
        if not is_ollama_available():
            raise RuntimeError(
                "MEMABLE_EMBEDDINGS=ollama but Ollama is not running.\n"
                "Start Ollama or remove MEMABLE_EMBEDDINGS to auto-detect."
            )
        ollama_model = model or DEFAULT_OLLAMA_MODEL
        if not has_ollama_model(ollama_model):
            raise RuntimeError(
                f"MEMABLE_EMBEDDINGS=ollama but {ollama_model} model not found.\n"
                f"Run: ollama pull {ollama_model}"
            )
        print(f"[memable] Using Ollama embeddings ({ollama_model})", flush=True)
        return OllamaEmbeddings(model=ollama_model)
    
    # 2. Explicit MEMABLE_EMBEDDINGS=openai
    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY required when MEMABLE_EMBEDDINGS=openai")
        print("[memable] Using OpenAI embeddings (forced via MEMABLE_EMBEDDINGS)", flush=True)
        return OpenAIEmbeddings(model=model or "text-embedding-3-small")
    
    # 3. Explicit OPENAI_API_KEY = user wants OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        print("[memable] Using OpenAI embeddings (OPENAI_API_KEY set)", flush=True)
        return OpenAIEmbeddings(model=model or "text-embedding-3-small")
    
    # 4. Auto-detect: try Ollama
    if is_ollama_available():
        ollama_model = model or DEFAULT_OLLAMA_MODEL
        if has_ollama_model(ollama_model):
            print(f"[memable] Using Ollama embeddings ({ollama_model}, auto-detected)", flush=True)
            return OllamaEmbeddings(model=ollama_model)
        else:
            print(f"[memable] Ollama found but {ollama_model} not installed.", flush=True)
            print(f"[memable] Run: ollama pull {ollama_model}", flush=True)
            # Fall through to error
    
    # 5. Nothing available
    raise RuntimeError(
        "No embedding provider available.\n\n"
        "Options:\n"
        "  1. Install Ollama and run: ollama pull nomic-embed-text\n"
        "  2. Set OPENAI_API_KEY environment variable\n"
        "  3. Use hosted mode with MEMABLE_API_KEY"
    )
