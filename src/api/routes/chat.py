"""
Rutas de chat con streaming SSE y Human-in-the-Loop.

Endpoints:
  POST /api/v1/chat/stream              — Inicia o continúa conversación (SSE)
  POST /api/v1/chat/{thread_id}/resume  — Reanuda conversación interrumpida
  GET  /api/v1/chat/{thread_id}/history — Historial de la conversación
  DELETE /api/v1/chat/{thread_id}       — Info para limpiar conversación

Todos los endpoints requieren el header: X-API-Key: <tu_api_key>
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.agent.graph import build_graph
from src.api.schemas import (
    ChatRequest,
    ResumeRequest,
    SSEEventType,
)
from src.auth.dependencies import require_api_key

router = APIRouter(prefix="/chat", tags=["Chat"])

# ─── Grafo con memoria para FastAPI standalone ────────────────────────────────
_memory = MemorySaver()
_compiled = None


def get_graph_with_memory():
    global _compiled
    if _compiled is None:
        g = build_graph()
        try:
            _compiled = g.with_config({"checkpointer": _memory})
        except Exception:
            _compiled = g
    return _compiled, _memory


# ─── Utilidades SSE ────────────────────────────────────────────────────────────

def _sse(event_type: SSEEventType, data: object, thread_id: str = "") -> str:
    payload = json.dumps(
        {"type": event_type.value, "data": data, "thread_id": thread_id},
        ensure_ascii=False,
    )
    return f"data: {payload}\n\n"


def _config(thread_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpointer": _memory,
        },
        "recursion_limit": 25,
    }


# ─── Generador de streaming ────────────────────────────────────────────────────

async def _stream_agent(
    user_message: str,
    thread_id: str,
    resume_value: str | None = None,
) -> AsyncGenerator[str, None]:
    """Genera eventos SSE desde el grafo LangGraph."""
    config = _config(thread_id)
    yield _sse(SSEEventType.METADATA, {"thread_id": thread_id}, thread_id)

    try:
        graph = build_graph()

        if resume_value is not None:
            graph_input = Command(resume=resume_value)
        else:
            graph_input = {"messages": [HumanMessage(content=user_message)]}

        async for event in graph.astream(
            graph_input,
            config=config,
            stream_mode=["messages", "updates"],
        ):
            stream_mode, chunk = event

            if stream_mode == "messages":
                msg_chunk, metadata = chunk
                if (
                    hasattr(msg_chunk, "content")
                    and msg_chunk.content
                    and metadata.get("langgraph_node") == "agent"
                    and not getattr(msg_chunk, "tool_calls", None)
                ):
                    yield _sse(SSEEventType.TOKEN, msg_chunk.content, thread_id)

            elif stream_mode == "updates":
                if "__interrupt__" in chunk:
                    interrupt_data = chunk["__interrupt__"][0].value
                    yield _sse(SSEEventType.INTERRUPT, interrupt_data, thread_id)
                    return

                if "tools" in chunk:
                    for tmsg in chunk["tools"].get("messages", []):
                        if isinstance(tmsg, ToolMessage):
                            yield _sse(
                                SSEEventType.TOOL_END,
                                {
                                    "tool_name": tmsg.name,
                                    "result_preview": str(tmsg.content)[:200],
                                },
                                thread_id,
                            )

                if "agent" in chunk:
                    for amsg in chunk["agent"].get("messages", []):
                        if isinstance(amsg, AIMessage) and amsg.tool_calls:
                            for tc in amsg.tool_calls:
                                yield _sse(
                                    SSEEventType.TOOL_START,
                                    {"tool_name": tc["name"], "args": tc.get("args", {})},
                                    thread_id,
                                )

        yield _sse(SSEEventType.DONE, {"thread_id": thread_id}, thread_id)

    except Exception as exc:
        yield _sse(SSEEventType.ERROR, {"message": str(exc)}, thread_id)


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Chat con streaming SSE",
    response_class=StreamingResponse,
    description=(
        "Inicia o continúa una conversación con el agente vía SSE. "
        "Requiere header `X-API-Key`. El `thread_id` identifica la sesión del "
        "usuario final (genera uno por dispositivo/usuario en tu app Flutter)."
    ),
)
async def chat_stream(
    request: ChatRequest,
    _user: dict = Depends(require_api_key),   # ← protege el endpoint
) -> StreamingResponse:
    thread_id = request.thread_id or str(uuid.uuid4())
    return StreamingResponse(
        _stream_agent(user_message=request.message, thread_id=thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{thread_id}/resume",
    summary="Reanudar conversación (HIL)",
    response_class=StreamingResponse,
)
async def resume_conversation(
    thread_id: str,
    request: ResumeRequest,
    _user: dict = Depends(require_api_key),   # ← protege el endpoint
) -> StreamingResponse:
    return StreamingResponse(
        _stream_agent(user_message="", thread_id=thread_id, resume_value=request.response),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/{thread_id}/history",
    summary="Historial de conversación",
)
async def get_history(
    thread_id: str,
    _user: dict = Depends(require_api_key),   # ← protege el endpoint
) -> dict:
    config = _config(thread_id)
    try:
        graph = build_graph()
        state = graph.get_state(config)
        if not state or not state.values:
            raise HTTPException(status_code=404, detail="Hilo no encontrado")

        messages = state.values.get("messages", [])
        history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                history.append({"role": "tool", "tool_name": msg.name, "content": msg.content})

        return {"thread_id": thread_id, "message_count": len(history), "messages": history}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/{thread_id}",
    summary="Limpiar conversación",
)
async def clear_conversation(
    thread_id: str,
    _user: dict = Depends(require_api_key),   # ← protege el endpoint
) -> dict:
    return {
        "thread_id": thread_id,
        "message": "Para nueva conversación usa un thread_id diferente.",
    }