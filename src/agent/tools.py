"""
Herramientas del Agente Eclesiástico.
Cada @tool encapsula una capacidad de recuperación del himnario.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from src.retrieval.retriever import get_retriever


# ─── Formateadores ─────────────────────────────────────────────────────────────

def _fmt_hymn_brief(h: dict) -> str:
    """Formato corto: número + título + tono."""
    occ = ", ".join(h.get("ocasiones", [])) or "—"
    return (
        f"  • Himno #{h['numero']:>3} | {h['titulo']}\n"
        f"    Tono: {h['tono']} | Ocasiones: {occ}"
    )


def _fmt_hymn_full(h: dict) -> str:
    """Formato completo con letra."""
    refs = ", ".join(h.get("referencias_biblicas", [])) or "ninguna"
    occ  = ", ".join(h.get("ocasiones", [])) or "—"
    # Contenido: extraer solo la parte del himno (sin el bloque de metadata del embedding)
    contenido = h.get("contenido", "")
    # Si el doc_texto tiene el bloque de meta al inicio, lo removemos
    if "HIMNO #" in contenido and "\n\n" in contenido:
        _, _, contenido = contenido.partition("\n\n")
    return (
        f"🎵 HIMNO #{h['numero']}: {h['titulo'].upper()}\n"
        f"   Tono: {h['tono']}\n"
        f"   Ocasiones: {occ}\n"
        f"   Referencias bíblicas: {refs}\n"
        f"{'─' * 50}\n"
        f"{contenido.strip()}\n"
    )


# ─── Herramientas ─────────────────────────────────────────────────────────────

@tool
def buscar_himnos(consulta: str, limite: int = 5) -> str:
    """
    Busca himnos por tema, contenido o significado usando búsqueda semántica.

    Úsala cuando el usuario pregunte por himnos sobre un tema general como:
    perdón, gracia, segunda venida, salvación, fe, esperanza, amor, paz,
    misión, etc.

    Args:
        consulta: El tema o mensaje a buscar (ej: "perdón entre hermanos",
                  "segunda venida de Cristo", "la gracia de Dios")
        limite:   Número de resultados (1-10). Default: 5.

    Returns:
        Lista de himnos con número, título, tono y extracto relevante.
    """
    retriever = get_retriever()
    k = max(1, min(limite, 10))
    hymns = retriever.search(query=consulta, k=k)

    if not hymns:
        return (
            "No encontré himnos que coincidan con esa búsqueda. "
            "Intente con términos diferentes o una descripción más general."
        )

    lines = [f"Encontré {len(hymns)} himno(s) relacionado(s) con «{consulta}»:\n"]
    for h in hymns:
        lines.append(_fmt_hymn_brief(h))
    return "\n".join(lines)


@tool
def obtener_himno(numero: int) -> str:
    """
    Obtiene un himno específico por su número, mostrando la letra completa.

    Úsala cuando el usuario pregunte por el himno número X, o cuando quiera
    ver la letra completa de un himno ya identificado.

    Args:
        numero: Número del himno (1 a 535).

    Returns:
        Himno completo con título, tono y letra.
    """
    retriever = get_retriever()
    hymn = retriever.get_by_number(numero)

    if not hymn:
        return (
            f"No encontré el himno número {numero} en el himnario. "
            f"Los himnos van del 1 al 535."
        )

    return _fmt_hymn_full(hymn)


@tool
def buscar_por_ocasion(ocasion: str, limite: int = 8) -> str:
    """
    Busca himnos apropiados para una ocasión litúrgica o festiva específica.

    Úsala cuando el usuario pregunte qué himnos cantar en:
    - cosechas, primicias
    - pentecostés, ascensión
    - semana santa, viernes santo, calvario
    - resurrección, pascua
    - navidad, noche de paz
    - bautismo, santa cena / comunión
    - día del trabajo, siembra
    - misión, evangelismo

    Args:
        ocasion: Nombre de la ocasión (ej: "cosechas", "pentecostés",
                 "semana santa", "navidad", "bautismo")
        limite:  Número de resultados (1-20). Default: 8.

    Returns:
        Lista de himnos recomendados para esa ocasión.
    """
    retriever = get_retriever()
    k = max(1, min(limite, 20))
    hymns = retriever.get_by_occasion(ocasion=ocasion, k=k)

    if not hymns:
        return (
            f"No encontré himnos específicamente catalogados para «{ocasion}». "
            f"Pruebe con búsqueda semántica usando la herramienta buscar_himnos."
        )

    lines = [f"Himnos recomendados para **{ocasion}** ({len(hymns)} encontrados):\n"]
    for h in hymns:
        lines.append(_fmt_hymn_brief(h))
    return "\n".join(lines)


@tool
def buscar_por_tono(tono: str) -> str:
    """
    Busca himnos en un tono musical específico.

    Úsala cuando el usuario pregunte qué himnos están en cierto tono musical.

    Tonos disponibles: C Mayor / Do Mayor, D Mayor / Re Mayor, E Mayor / Mi Mayor,
    F Mayor / Fa Mayor, G Mayor / Sol Mayor, A Mayor / La Mayor, B Mayor / Si Mayor,
    y sus respectivos menores.

    Args:
        tono: Tono musical (ej: "Sol Mayor", "G", "La Mayor", "E Mayor", "Mi")

    Returns:
        Lista de himnos en ese tono.
    """
    retriever = get_retriever()
    hymns = retriever.get_by_tone(tono=tono)

    if not hymns:
        return (
            f"No encontré himnos en el tono «{tono}». "
            f"Tenga en cuenta que la mayoría de los himnos figuran como 'INDEFINIDO' "
            f"en cuanto al tono en el himnario. "
            f"Tonos con datos: C Mayor, E Mayor, La Mayor."
        )

    lines = [f"Himnos en tono **{tono}** ({len(hymns)} encontrados):\n"]
    for h in hymns:
        lines.append(_fmt_hymn_brief(h))
    return "\n".join(lines)


@tool
def buscar_por_referencia_biblica(referencia: str, limite: int = 5) -> str:
    """
    Busca himnos relacionados con una referencia o pasaje bíblico (Reina Valera 1909).

    Úsala cuando el usuario pregunte qué himnos se relacionan con un versículo
    o pasaje de la Biblia, por ejemplo: "Juan 3:16", "Salmos 23", "Romanos 8".

    Args:
        referencia: Referencia bíblica (ej: "Juan 3:16", "Salmos 23",
                    "Apocalipsis 21", "gracia de Efesios 2")
        limite:     Número de resultados. Default: 5.

    Returns:
        Lista de himnos relacionados con ese pasaje bíblico.
    """
    retriever = get_retriever()
    k = max(1, min(limite, 10))
    hymns = retriever.search_by_biblical_ref(referencia=referencia, k=k)

    if not hymns:
        return (
            f"No encontré himnos claramente relacionados con «{referencia}». "
            f"Intente con el tema principal del pasaje."
        )

    lines = [
        f"Himnos relacionados con el pasaje bíblico «{referencia}» "
        f"(Reina Valera 1909):\n"
    ]
    for h in hymns:
        refs = ", ".join(h.get("referencias_biblicas", [])) or "—"
        lines.append(_fmt_hymn_brief(h))
        if h.get("referencias_biblicas"):
            lines.append(f"    Refs. explícitas: {refs}")
    return "\n".join(lines)


@tool
def listar_himnos(pagina: int = 1, por_pagina: int = 20) -> str:
    """
    Lista los himnos del himnario de forma paginada.

    Úsala cuando el usuario pida el índice o listado de himnos.

    Args:
        pagina:     Página a mostrar (empieza en 1).
        por_pagina: Himnos por página (máx. 50). Default: 20.

    Returns:
        Lista paginada de himnos con número y título.
    """
    retriever = get_retriever()
    por_pagina = max(5, min(por_pagina, 50))
    offset = (pagina - 1) * por_pagina
    hymns = retriever.list_all(limit=por_pagina, offset=offset)
    total = retriever.count()
    total_pages = (total + por_pagina - 1) // por_pagina

    if not hymns:
        return f"No hay himnos en la página {pagina}."

    lines = [f"📚 Himnario — Página {pagina} de {total_pages} (total: {total}):\n"]
    for h in hymns:
        lines.append(f"  #{h['numero']:>3}. {h['titulo']}")
    lines.append(f"\nPágina {pagina}/{total_pages}. Para más, solicite la página siguiente.")
    return "\n".join(lines)


# ─── Lista exportada ───────────────────────────────────────────────────────────
ALL_TOOLS = [
    buscar_himnos,
    obtener_himno,
    buscar_por_ocasion,
    buscar_por_tono,
    buscar_por_referencia_biblica,
    listar_himnos,
]
