"""
Configuración central del proyecto.
Todas las variables de entorno se leen desde .env
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Detectar si estamos en Railway
_IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))
_DATA_BASE = Path("/data") if _IS_RAILWAY else Path("data")

# Luego cambia las rutas:
chroma_persist_dir: Path = _DATA_BASE / "chroma_db"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── OpenAI ─────────────────────────────────────────────────────────────
    openai_api_key: str

    # ─── LangSmith ──────────────────────────────────────────────────────────
    langchain_api_key: str = ""
    langchain_tracing_v2: str = "true"
    langchain_project: str = "iglesia-universal-agente"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # ─── Modelos ────────────────────────────────────────────────────────────
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.2
    max_tokens: int = 2048

    # ─── Embeddings locales (alternativa gratuita sin API key) ──────────────
    # Opciones: "openai" | "local"
    # "local" usa sentence-transformers (HuggingFace) gratis y sin cuota
    embedding_provider: str = "openai"
    local_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # ─── Rutas ──────────────────────────────────────────────────────────────
    hymns_dir: Path = Path("himnos")
    chroma_persist_dir: Path = Path("data/chroma_db")
    chroma_collection: str = "himnario_icuajp"

    # ─── Recuperación ───────────────────────────────────────────────────────
    max_retrieval_results: int = 8

    # ─── API ────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Agente Eclesiástico — Iglesia Cristiana Universal Apostólica de Jesús Pentecostés A.R."
    api_version: str = "1.0.0"

    def configure_langsmith(self) -> None:
        """Activa LangSmith si hay API key configurada."""
        if self.langchain_api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = self.langchain_tracing_v2
            os.environ["LANGCHAIN_API_KEY"] = self.langchain_api_key
            os.environ["LANGCHAIN_PROJECT"] = self.langchain_project
            os.environ["LANGCHAIN_ENDPOINT"] = self.langchain_endpoint


settings = Settings()
settings.configure_langsmith()
