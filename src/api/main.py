"""
Aplicación FastAPI principal del Agente Eclesiástico.

Rutas base:
  /api/v1/chat/*   — Conversación con el agente (SSE streaming)
  /api/v1/hymns/*  — Catálogo del himnario
  /api/v1/admin/*  — Administración (indexación)
  /health          — Health check
  /docs            — Swagger UI (deshabilitado en producción)
  /redoc           — ReDoc
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.ingestion.indexer import collection_exists, index_hymns
from src.retrieval.retriever import get_retriever
from src.api.routes.chat import router as chat_router
from src.api.routes.hymns import router as hymns_router
from src.api.schemas import HealthResponse, IngestResponse


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Al iniciar: verifica que ChromaDB esté indexado.
    Si no hay datos, recomienda ejecutar 'make ingest'.
    """
    if not collection_exists():
        print(
            "\n⚠️  ADVERTENCIA: El himnario no está indexado.\n"
            "   Ejecuta: make ingest  (o: python scripts/ingest.py)\n"
        )
    else:
        count = get_retriever().count()
        print(f"\n✅ ChromaDB listo — {count} himnos indexados.\n")
    yield
    # Cleanup al apagar (si fuera necesario)


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "API del Agente Eclesiástico de la **Iglesia Cristiana Universal "
        "Apostólica de Jesús Pentecostés A.R.** — Asistente inteligente del himnario "
        "con streaming SSE, memoria conversacional y Human-in-the-Loop."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Ajusta en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(chat_router,  prefix=API_PREFIX)
app.include_router(hymns_router, prefix=API_PREFIX)


# ─── Endpoints de administración ──────────────────────────────────────────────

@app.post(
    f"{API_PREFIX}/admin/ingest",
    response_model=IngestResponse,
    tags=["Admin"],
    summary="Indexar himnario",
    description=(
        "Parsea los archivos .txt del directorio de himnos y los indexa en ChromaDB. "
        "Usar `force=true` para re-indexar aunque ya existan datos."
    ),
)
async def trigger_ingest(force: bool = False) -> IngestResponse:
    try:
        count = index_hymns(force=force)
        return IngestResponse(
            success=True,
            hymns_indexed=count,
            message=f"✅ {count} himnos indexados correctamente en ChromaDB.",
        )
    except Exception as exc:
        return IngestResponse(
            success=False,
            hymns_indexed=0,
            message=f"❌ Error durante la indexación: {exc}",
        )


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Sistema"],
    summary="Estado del servicio",
)
async def health_check() -> HealthResponse:
    hymns_count = 0
    try:
        hymns_count = get_retriever().count()
    except Exception:
        pass

    return HealthResponse(
        status="ok" if hymns_count > 0 else "degraded",
        hymns_indexed=hymns_count,
        model=settings.llm_model,
        embedding_model=settings.embedding_model,
        langsmith_enabled=bool(settings.langchain_api_key),
    )


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Sistema"], include_in_schema=False)
async def root() -> dict:
    return {
        "servicio": "Agente Eclesiástico — ICUAJP",
        "version": settings.api_version,
        "documentacion": "/docs",
        "salud": "/health",
        "chat_stream": f"{API_PREFIX}/chat/stream",
    }
