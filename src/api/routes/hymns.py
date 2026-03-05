"""
Rutas del catálogo de himnos.

Endpoints:
  GET  /api/v1/hymns                 — Listar himnos (paginado)
  GET  /api/v1/hymns/search          — Búsqueda semántica directa
  GET  /api/v1/hymns/{number}        — Himno por número
  GET  /api/v1/hymns/occasion/{occ}  — Himnos por ocasión litúrgica
  GET  /api/v1/hymns/tone/{tone}     — Himnos por tono musical

Todos los endpoints requieren el header: X-API-Key: <tu_api_key>
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends

from src.retrieval.retriever import get_retriever
from src.api.schemas import (
    HymnBrief,
    HymnFull,
    HymnsListResponse,
    HymnsSearchResponse,
)
from src.auth.dependencies import require_api_key

router = APIRouter(prefix="/hymns", tags=["Himnario"])


def _to_brief(h: dict) -> HymnBrief:
    return HymnBrief(
        numero=h["numero"],
        titulo=h["titulo"],
        tono=h["tono"],
        ocasiones=h.get("ocasiones", []),
        referencias_biblicas=h.get("referencias_biblicas", []),
    )


def _to_full(h: dict) -> HymnFull:
    return HymnFull(
        numero=h["numero"],
        titulo=h["titulo"],
        tono=h["tono"],
        ocasiones=h.get("ocasiones", []),
        referencias_biblicas=h.get("referencias_biblicas", []),
        contenido=h.get("contenido", ""),
        archivo=h.get("archivo", ""),
    )


@router.get(
    "",
    response_model=HymnsListResponse,
    summary="Listar himnos",
    description="Devuelve el índice paginado del himnario (535 himnos en total).",
)
async def list_hymns(
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=5, le=100, description="Himnos por página"),
    _user: dict = Depends(require_api_key),
) -> HymnsListResponse:
    retriever = get_retriever()
    total  = retriever.count()
    offset = (page - 1) * per_page
    hymns  = retriever.list_all(limit=per_page, offset=offset)
    return HymnsListResponse(
        total=total,
        page=page,
        per_page=per_page,
        hymns=[_to_brief(h) for h in hymns],
    )


@router.get(
    "/search",
    response_model=HymnsSearchResponse,
    summary="Búsqueda semántica de himnos",
    description="Busca himnos por tema, frase o significado usando IA.",
)
async def search_hymns(
    q: str = Query(..., min_length=2, description="Consulta de búsqueda"),
    k: int = Query(5, ge=1, le=20, description="Número de resultados"),
    _user: dict = Depends(require_api_key),
) -> HymnsSearchResponse:
    retriever = get_retriever()
    hymns = retriever.search(query=q, k=k)
    return HymnsSearchResponse(
        query=q,
        results=[_to_full(h) for h in hymns],
    )


@router.get(
    "/occasion/{ocasion}",
    response_model=list[HymnBrief],
    summary="Himnos por ocasión litúrgica",
)
async def hymns_by_occasion(
    ocasion: str,
    limit: int = Query(10, ge=1, le=50),
    _user: dict = Depends(require_api_key),
) -> list[HymnBrief]:
    retriever = get_retriever()
    hymns = retriever.get_by_occasion(ocasion=ocasion, k=limit)
    return [_to_brief(h) for h in hymns]


@router.get(
    "/tone/{tono}",
    response_model=list[HymnBrief],
    summary="Himnos por tono musical",
)
async def hymns_by_tone(
    tono: str,
    _user: dict = Depends(require_api_key),
) -> list[HymnBrief]:
    retriever = get_retriever()
    hymns = retriever.get_by_tone(tono=tono)
    if not hymns:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron himnos en tono '{tono}'.",
        )
    return [_to_brief(h) for h in hymns]


@router.get(
    "/{numero}",
    response_model=HymnFull,
    summary="Obtener himno por número",
    description="Devuelve el himno completo con su letra.",
)
async def get_hymn(
    numero: int,
    _user: dict = Depends(require_api_key),
) -> HymnFull:
    if not 1 <= numero <= 535:
        raise HTTPException(
            status_code=400,
            detail="El número de himno debe estar entre 1 y 535.",
        )
    retriever = get_retriever()
    hymn = retriever.get_by_number(numero)
    if not hymn:
        raise HTTPException(
            status_code=404,
            detail=f"Himno #{numero} no encontrado.",
        )
    return _to_full(hymn)