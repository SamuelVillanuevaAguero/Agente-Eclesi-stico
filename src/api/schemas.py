"""
Esquemas Pydantic para la API REST.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


# ─── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Solicitud de chat del usuario."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mensaje del usuario",
        examples=["¿Qué himnos puedo cantar en primicias?"],
    )
    thread_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="ID de hilo conversacional. Omitir para nueva conversación.",
    )


class ResumeRequest(BaseModel):
    """Reanuda una conversación interrumpida (Human-in-the-Loop)."""
    response: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Respuesta del usuario a la pregunta de aclaración",
    )
    thread_id: str = Field(
        ...,
        description="ID del hilo interrumpido a reanudar",
    )


# ─── SSE Events ───────────────────────────────────────────────────────────────

class SSEEventType(str, Enum):
    TOKEN       = "token"           # Fragmento de token del LLM
    TOOL_START  = "tool_start"      # Inicio de ejecución de herramienta
    TOOL_END    = "tool_end"        # Fin de ejecución de herramienta
    INTERRUPT   = "interrupt"       # Human-in-the-Loop: aclaración solicitada
    DONE        = "done"            # Respuesta completa
    ERROR       = "error"           # Error en el agente
    METADATA    = "metadata"        # Información adicional (thread_id, etc.)


class SSEEvent(BaseModel):
    """Evento SSE enviado al cliente durante el streaming."""
    type: SSEEventType
    data: Any = None
    thread_id: Optional[str] = None


# ─── Himnos ───────────────────────────────────────────────────────────────────

class HymnBrief(BaseModel):
    """Información resumida de un himno."""
    numero: int
    titulo: str
    tono: str
    ocasiones: list[str] = []
    referencias_biblicas: list[str] = []


class HymnFull(HymnBrief):
    """Himno completo con letra."""
    contenido: str
    archivo: str


class HymnsListResponse(BaseModel):
    """Respuesta paginada de himnos."""
    total: int
    page: int
    per_page: int
    hymns: list[HymnBrief]


class HymnsSearchResponse(BaseModel):
    """Respuesta de búsqueda de himnos."""
    query: str
    results: list[HymnFull]


# ─── Admin ────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    """Respuesta del endpoint de indexación."""
    success: bool
    hymns_indexed: int
    message: str


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Estado de salud del servicio."""
    status: str
    hymns_indexed: int
    model: str
    embedding_model: str
    langsmith_enabled: bool
