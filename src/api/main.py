"""
Aplicación FastAPI principal del Agente Eclesiástico.

Rutas base:
  /api/v1/auth/*   — Autenticación y gestión de API Keys
  /api/v1/chat/*   — Conversación con el agente (SSE streaming)  [requiere X-API-Key]
  /api/v1/hymns/*  — Catálogo del himnario                       [requiere X-API-Key]
  /api/v1/admin/*  — Administración (indexación)                 [requiere X-API-Key]
  /health          — Health check (público)
  /docs            — Swagger UI (con autenticación integrada)
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.auth.database import init_db
from src.auth.dependencies import require_api_key
from src.ingestion.indexer import collection_exists, index_hymns
from src.retrieval.retriever import get_retriever
from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.hymns import router as hymns_router
from src.api.schemas import HealthResponse, IngestResponse


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Inicializar base de datos de autenticación
    init_db()
    print("✅ Base de datos de autenticación lista (SQLite).")

    # 2. Verificar ChromaDB
    if not collection_exists():
        print(
            "\n⚠️  ADVERTENCIA: El himnario no está indexado.\n"
            "   Ejecuta: make ingest  (o: python scripts/ingest.py)\n"
        )
    else:
        count = get_retriever().count()
        print(f"✅ ChromaDB listo — {count} himnos indexados.\n")
    yield


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "API del Agente Eclesiástico de la **Iglesia Cristiana Universal "
        "Apostólica de Jesús Pentecostés A.R.** — Asistente inteligente del himnario "
        "con streaming SSE, memoria conversacional y Human-in-the-Loop.\n\n"
        "## Autenticación\n"
        "1. Llama a `POST /api/v1/auth/token` con tu email y contraseña.\n"
        "2. Usa la `api_key` recibida en el header `X-API-Key` en todas las peticiones.\n"
        "3. En Swagger: haz clic en **Authorize 🔒** e ingresa tu API Key."
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

app.include_router(auth_router,  prefix=API_PREFIX)  # ← Público (login)
app.include_router(chat_router,  prefix=API_PREFIX)  # ← Protegido internamente
app.include_router(hymns_router, prefix=API_PREFIX)  # ← Protegido internamente


# ─── Admin (protegido con API Key) ────────────────────────────────────────────

@app.post(
    f"{API_PREFIX}/admin/ingest",
    response_model=IngestResponse,
    tags=["Admin"],
    summary="Indexar himnario",
    dependencies=[Depends(require_api_key)],   # ← Protegido
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


# ─── Health Check (público) ───────────────────────────────────────────────────

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


# ─── Root (público) ───────────────────────────────────────────────────────────

@app.get("/", tags=["Sistema"], include_in_schema=False)
async def root() -> dict:
    return {
        "servicio": "Agente Eclesiástico — ICUAJP",
        "version": settings.api_version,
        "documentacion": "/docs",
        "salud": "/health",
        "autenticacion": f"{API_PREFIX}/auth/token",
        "chat_stream": f"{API_PREFIX}/chat/stream",
    }