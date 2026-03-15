"""
Nodos del grafo LangGraph.
Cada función representa una acción en el flujo del agente.
"""
from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from src.config import settings
from src.agent.state import AgentState
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import ALL_TOOLS


# ─── Palabras clave que indican consulta sobre himnos ─────────────────────────

_HYMN_KEYWORDS = re.compile(
    r"\b(himno|himnos|himnar|cantar|canciones?|canto|tonada|letra|estrofa|coro"
    r"|ocasion|ocasión|boda|bautismo|navidad|cosecha|primicia|pentecost"
    r"|ascension|semana\s*santa|resurreccion|santa\s*cena|tono|musical"
    r"|busca|buscar|recomienda|recomendar|sugieres?|sugier)\b",
    re.IGNORECASE,
)


def _requires_tool_use(state: AgentState) -> bool:
    """
    Determina si la consulta actual involucra himnos y aún no se usaron herramientas.
    En ese caso forzamos tool_choice='required' para evitar alucinaciones.
    """
    messages = state.get("messages", [])

    # ¿Ya hay ToolMessages en el historial reciente? → el LLM ya consultó la BD
    recent_tool_calls = any(isinstance(m, ToolMessage) for m in messages[-6:])
    if recent_tool_calls:
        return False

    # ¿El último mensaje humano parece ser sobre himnos?
    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    if last_human and _HYMN_KEYWORDS.search(str(last_human.content)):
        return True

    return False


# ─── LLM con herramientas enlazadas ───────────────────────────────────────────

def _build_llm(tool_choice: str = "auto") -> ChatOpenAI:
    base = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        openai_api_key=settings.openai_api_key,
        streaming=True,
    )
    return base.bind_tools(ALL_TOOLS, tool_choice=tool_choice)


_llm_auto: ChatOpenAI | None = None
_llm_required: ChatOpenAI | None = None


def get_llm(force_tools: bool = False) -> ChatOpenAI:
    global _llm_auto, _llm_required
    if force_tools:
        if _llm_required is None:
            _llm_required = _build_llm(tool_choice="required")
        return _llm_required
    else:
        if _llm_auto is None:
            _llm_auto = _build_llm(tool_choice="auto")
        return _llm_auto


# ─── Nodo principal del agente ─────────────────────────────────────────────────

def agent_node(state: AgentState) -> dict:
    """
    Nodo central: invoca el LLM con el historial completo.

    Si la consulta involucra himnos y aún no se han usado herramientas,
    fuerza tool_choice='required' para evitar que el LLM invente datos.
    """
    force_tools = _requires_tool_use(state)
    llm = get_llm(force_tools=force_tools)

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
    """
    last_ai = next(
        (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    clarification_question = (
        last_ai.content
        if last_ai
        else "¿Podría darme más detalles sobre su consulta, hermano/hermana?"
    )

    user_response = interrupt(
        {
            "type": "clarification_needed",
            "question": clarification_question,
        }
    )

    return {
        "messages": [HumanMessage(content=str(user_response))],
        "needs_clarification": False,
    }


# ─── Validador anti-alucinación ────────────────────────────────────────────────

_HALLUCINATION_PATTERNS = re.compile(
    r"(himno\s*[#nN°]?\s*\d+\s*[:\"«]"   # "Himno #3: ..." o "Himno 1:"
    r"|tono\s*:\s*[A-Za-z]"               # "Tono: C Mayor" sin haber buscado
    r"|himno\s+\d+\s*[-–]\s*\")",         # "Himno 1 - "Título""
    re.IGNORECASE,
)


def _looks_like_hallucination(state: AgentState) -> bool:
    """
    Detecta si el último mensaje del agente contiene datos de himnos
    que NO provienen de una herramienta reciente.
    """
    messages = state.get("messages", [])

    last_ai = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)), None
    )
    if not last_ai or not last_ai.content:
        return False

    # Si hay herramientas recientes, los datos son reales
    has_recent_tool = any(isinstance(m, ToolMessage) for m in messages[-8:])
    if has_recent_tool:
        return False

    # Si el mensaje contiene patrones de himno sin haber consultado herramientas
    if _HALLUCINATION_PATTERNS.search(str(last_ai.content)):
        return True

    return False


# ─── Función de enrutamiento condicional ──────────────────────────────────────

def should_continue(
    state: AgentState,
) -> Literal["tools", "clarification", "agent", "__end__"]:
    """
    Decide el siguiente paso después del nodo agent:

    - Si el LLM generó tool_calls        → ejecutar herramientas
    - Si parece haber alucinado himnos   → vuelve al agente (con corrección)
    - Si marcó necesidad de aclaración   → nodo de aclaración
    - En cualquier otro caso             → fin de la conversación
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, AIMessage):
        return "__end__"

    # ¿Hay llamadas a herramientas pendientes?
    if last_message.tool_calls:
        return "tools"

    # ¿El agente parece haber inventado himnos sin consultar la BD?
    if _looks_like_hallucination(state):
        # Inyectamos un recordatorio antes de re-invocar
        from langchain_core.messages import HumanMessage as HM
        state["messages"].append(
            HM(content=(
                "[SISTEMA] Tu respuesta anterior menciona himnos específicos "
                "sin haberlos consultado en la base de datos. "
                "DEBES usar una herramienta primero. "
                "Por favor llama a la herramienta apropiada ahora."
            ))
        )
        return "agent"

    # ¿El agente detectó que necesita aclaración?
    if state.get("needs_clarification"):
        return "clarification"

    return "__end__"