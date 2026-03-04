"""
Definición del estado del agente LangGraph.
"""
from __future__ import annotations

from typing import Annotated, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Estado completo del agente a través del grafo.

    messages:
        Historial de la conversación. `add_messages` asegura que los mensajes
        nuevos se acumulen (no se sobreescriban) en cada paso del grafo.

    thread_id:
        Identificador único de la sesión conversacional.
        Permite que MemorySaver mantenga contexto entre invocaciones.

    hymns_retrieved:
        Últimos himnos encontrados por las herramientas.
        Útil para que el agente los referencie sin repetir búsquedas.

    needs_clarification:
        Flag que indica si el agente determinó que necesita más contexto
        del usuario antes de poder responder con precisión.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    thread_id: Optional[str]
    hymns_retrieved: Optional[list[dict]]
    needs_clarification: Optional[bool]
