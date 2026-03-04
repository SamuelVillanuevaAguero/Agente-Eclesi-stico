"""
Nodos del grafo LangGraph.
Cada función representa una acción en el flujo del agente.
"""
from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from src.config import settings
from src.agent.state import AgentState
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import ALL_TOOLS


# ─── LLM con herramientas enlazadas ───────────────────────────────────────────

def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        openai_api_key=settings.openai_api_key,
        streaming=True,          # Habilita streaming de tokens
    ).bind_tools(ALL_TOOLS)


# Instancia lazy (se crea en el primer uso)
_llm_with_tools: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    global _llm_with_tools
    if _llm_with_tools is None:
        _llm_with_tools = _build_llm()
    return _llm_with_tools


# ─── Nodo principal del agente ─────────────────────────────────────────────────

def agent_node(state: AgentState) -> dict:
    """
    Nodo central: invoca el LLM con el historial completo.
    El LLM decide si responder directamente o usar una herramienta.
    """
    llm = get_llm()

    # Construir lista de mensajes con el system prompt al inicio
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response: AIMessage = llm.invoke(messages)

    return {
        "messages": [response],
        "needs_clarification": False,
    }


# ─── Nodo de aclaración (Human-in-the-Loop) ───────────────────────────────────

def clarification_node(state: AgentState) -> dict:
    """
    Pausa la ejecución del grafo y solicita aclaración al usuario.

    Cuando el agente no tiene suficiente información para responder con
    precisión, llega a este nodo. La llamada a `interrupt()` suspende el grafo
    y devuelve la pregunta de aclaración al cliente (vía SSE en la API).

    El grafo se reanuda cuando el usuario proporciona su respuesta mediante
    el endpoint /chat/{thread_id}/resume.
    """
    # Extraer la pregunta de aclaración del último mensaje del agente
    last_ai = next(
        (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    clarification_question = (
        last_ai.content
        if last_ai
        else "¿Podría darme más detalles sobre su consulta, hermano/hermana?"
    )

    # 🛑 PAUSA — espera input del usuario
    user_response = interrupt(
        {
            "type": "clarification_needed",
            "question": clarification_question,
        }
    )

    # Cuando se reanuda, `user_response` contiene lo que el usuario envió
    from langchain_core.messages import HumanMessage
    return {
        "messages": [HumanMessage(content=str(user_response))],
        "needs_clarification": False,
    }


# ─── Función de enrutamiento condicional ──────────────────────────────────────

def should_continue(
    state: AgentState,
) -> Literal["tools", "clarification", "__end__"]:
    """
    Decide el siguiente paso después del nodo agent:

    - Si el LLM generó tool_calls  → ejecutar herramientas
    - Si marcó necesidad de aclaracion → nodo de aclaración
    - En cualquier otro caso       → fin de la conversación
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, AIMessage):
        return "__end__"

    # ¿Hay llamadas a herramientas pendientes?
    if last_message.tool_calls:
        return "tools"

    # ¿El agente detectó que necesita aclaración?
    if state.get("needs_clarification"):
        return "clarification"

    return "__end__"
