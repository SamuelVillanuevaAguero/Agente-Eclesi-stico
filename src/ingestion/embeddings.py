"""
Fábrica de embeddings.
Soporta dos proveedores:
  - "openai"  → OpenAI text-embedding-3-small (requiere créditos)
  - "local"   → sentence-transformers via HuggingFace (gratis, sin cuota)

Para cambiar de proveedor, en tu .env:
    EMBEDDING_PROVIDER=local
"""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol, runtime_checkable

from src.config import settings


@runtime_checkable
class EmbeddingFunction(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def get_embeddings() -> EmbeddingFunction:
    """
    Devuelve la función de embeddings configurada en .env.
    EMBEDDING_PROVIDER=openai  → OpenAI API
    EMBEDDING_PROVIDER=local   → HuggingFace local (gratis)
    """
    provider = settings.embedding_provider.lower().strip()

    if provider == "local":
        return _get_local_embeddings()
    else:
        return _get_openai_embeddings()


def _get_openai_embeddings() -> EmbeddingFunction:
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
    )


def _get_local_embeddings() -> EmbeddingFunction:
    """
    Embeddings locales usando sentence-transformers.
    Modelo: paraphrase-multilingual-MiniLM-L12-v2
      - Soporta español perfectamente
      - ~120MB descarga única, luego queda en caché local
      - Sin límites de cuota, funciona offline
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        raise ImportError(
            "\n❌ Falta instalar el paquete para embeddings locales.\n"
            "   Ejecuta: pip install langchain-huggingface sentence-transformers\n"
        )

    print(f"  🤗 Usando embeddings locales: {settings.local_embedding_model}")
    print("  ⏳ Primera vez: descargando modelo (~120MB)...")

    return HuggingFaceEmbeddings(
        model_name=settings.local_embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
