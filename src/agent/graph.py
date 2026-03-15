"""
Grafo LangGraph del Agente Eclesiástico.

Arquitectura:
    START → agent_node → should_continue → tools   → agent_node (loop)
                              │
                              ├──────────── agent   ← corrección anti-alucinación
                              │
                         clarification  ← interrupt() → espera usuario
                              │
                          __end__
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from src.agent.state import AgentState
from src.agent.nodes import agent_node, clarification_node, should_continue
from src.agent.tools import ALL_TOOLS


def build_graph():
    """Construye y compila el grafo del agente sin checkpointer."""
    builder = StateGraph(AgentState)

    # ── Nodos ────────────────────────────────────────────────────────────────
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(ALL_TOOLS))
    builder.add_node("clarification", clarification_node)

    # ── Flujo principal ───────────────────────────────────────────────────────
    builder.add_edge(START, "agent")

    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools":          "tools",
            "clarification":  "clarification",
            "agent":          "agent",   # ← corrección anti-alucinación
            "__end__":        END,
        },
    )

    # Después de herramientas → vuelve al agente
    builder.add_edge("tools", "agent")

    # Después de aclaración → vuelve al agente con respuesta del usuario
    builder.add_edge("clarification", "agent")

    return builder.compile(name="agente_eclesiastico")


# ── Instancia exportada para LangGraph Studio ─────────────────────────────────
graph = build_graph()