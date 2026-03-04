# 🙏 Agente Eclesiástico — ICUAJP

**Iglesia Cristiana Universal Apostólica de Jesús Pentecostés A.R.**

Agente conversacional con IA para el himnario de la iglesia. Responde preguntas
sobre los 535 himnos del himnario con memoria conversacional, streaming en tiempo
real y Human-in-the-Loop.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI (SSE)                           │
│   POST /api/v1/chat/stream    ← streaming token a token        │
│   POST /api/v1/chat/{id}/resume  ← Human-in-the-Loop          │
│   GET  /api/v1/hymns/*        ← catálogo REST                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                    LangGraph Agent                              │
│                                                                 │
│   START → agent_node → should_continue → tools → agent_node   │
│                              │                                  │
│                         clarification  ← interrupt() [H-I-L]  │
│                                                                 │
│   MemorySaver (por thread_id)  │  LangSmith tracing            │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                      Herramientas (Tools)                       │
│   buscar_himnos          búsqueda semántica por tema           │
│   obtener_himno          himno por número (1-535)              │
│   buscar_por_ocasion     cosechas, primicias, pentecostés...   │
│   buscar_por_tono        C Mayor, E Mayor, La Mayor...         │
│   buscar_por_referencia  pasajes de Reina Valera 1909          │
│   listar_himnos          índice paginado del himnario          │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              ChromaDB  (local, persistente)                     │
│   535 himnos indexados con text-embedding-3-small              │
│   Metadata: número, título, tono, ocasiones, refs. bíblicas    │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Requisitos

- Python 3.11+
- Cuenta OpenAI con acceso a `gpt-4o-mini` y `text-embedding-3-small`
- Cuenta LangSmith (para trazabilidad y LangGraph Studio)

---

## 🚀 Instalación

```bash
# 1. Clonar / descomprimir el proyecto
cd iglesia_agente

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
# o: pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus claves de OpenAI y LangSmith

# 5. Indexar el himnario (solo la primera vez)
python scripts/ingest.py
# o: python scripts/ingest.py

# 6. Iniciar la API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
# o: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 Endpoints de la API

### Chat (SSE Streaming)

#### `POST /api/v1/chat/stream`
Inicia o continúa una conversación. Responde con Server-Sent Events token a token.

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué himnos puedo cantar en primicias?", "thread_id": "sesion-123"}' \
  --no-buffer
```

**Eventos SSE emitidos:**
| Evento | Descripción |
|--------|-------------|
| `metadata` | `thread_id` de la conversación |
| `token` | Fragmento de texto del LLM (streaming) |
| `tool_start` | El agente está consultando una herramienta |
| `tool_end` | Resultado de la herramienta |
| `interrupt` | El agente necesita aclaración (Human-in-the-Loop) |
| `done` | Respuesta completada |
| `error` | Error durante la ejecución |

#### `POST /api/v1/chat/{thread_id}/resume`
Reanuda conversación interrumpida (Human-in-the-Loop).

```bash
curl -X POST http://localhost:8000/api/v1/chat/sesion-123/resume \
  -H "Content-Type: application/json" \
  -d '{"response": "Busco himnos de gratitud para la fiesta de cosechas", "thread_id": "sesion-123"}' \
  --no-buffer
```

#### `GET /api/v1/chat/{thread_id}/history`
Historial completo de la conversación.

### Himnario

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/hymns` | Listar himnos (paginado) |
| GET | `/api/v1/hymns/search?q=perdón` | Búsqueda semántica |
| GET | `/api/v1/hymns/{numero}` | Himno completo por número |
| GET | `/api/v1/hymns/occasion/{ocasion}` | Himnos por ocasión |
| GET | `/api/v1/hymns/tone/{tono}` | Himnos por tono musical |

### Admin

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/admin/ingest` | Indexar/re-indexar himnario |
| GET | `/health` | Estado del servicio |

---

## 🎨 LangGraph Studio

LangGraph Studio permite visualizar y depurar el grafo del agente en tiempo real.

```bash
# Instalar LangGraph CLI (incluido en requirements.txt)
pip install langgraph-cli[inmem]

# Iniciar servidor local para Studio
langgraph dev
# o: langgraph dev

# Abrir LangGraph Studio: https://smith.langchain.com/studio
# Conectar a: http://localhost:2024
```

---

## 💬 Ejemplos de uso

```
👤 ¿Qué himnos puedo cantar en primicias?
🤖 Paz de Dios, hermano. Para la fiesta de las primicias, estos himnos son apropiados:
   • Himno #522: Himno Especial Para La Fiesta de las Primicias
   • Himno #380: Fiesta de Cosechas
   ...

👤 ¿Qué himno habla del perdón entre hermanos?
🤖 Encontré varios himnos sobre el perdón y la reconciliación...

👤 ¿Cuál es el himno #57?
🤖 🎵 HIMNO #57: ¡SEÑOR MI DIOS!
   Tono: INDEFINIDO
   ...

👤 ¿Qué himnos se relacionan con Juan 3:16?
🤖 Himnos relacionados con ese pasaje bíblico (RV 1909)...

👤 ¿Qué himnos están en tono E Mayor?
🤖 Himnos en tono E Mayor (4 encontrados)...
```

---

## 🔧 Estructura del Proyecto

```
iglesia_agente/
├── .env.example          Variables de entorno (plantilla)
├── requirements.txt      Dependencias Python
├── langgraph.json        Configuración LangGraph Studio
├── Makefile              Comandos de conveniencia
├── himnos/               535 archivos .txt del himnario
├── data/chroma_db/       Base de datos vectorial (generada)
├── scripts/
│   └── ingest.py         Script de indexación
└── src/
    ├── config.py          Configuración central
    ├── ingestion/
    │   ├── parser.py      Parser de archivos .txt
    │   └── indexer.py     Indexador en ChromaDB
    ├── retrieval/
    │   └── retriever.py   Consultas a ChromaDB
    ├── agent/
    │   ├── state.py       Estado del grafo
    │   ├── prompts.py     Prompts del sistema
    │   ├── tools.py       6 herramientas del agente
    │   ├── nodes.py       Nodos del grafo
    │   └── graph.py       Grafo LangGraph (exportado)
    └── api/
        ├── main.py        FastAPI app
        ├── schemas.py     Modelos Pydantic
        └── routes/
            ├── chat.py    Chat SSE + Human-in-the-Loop
            └── hymns.py   Catálogo REST
```

---

## 🔮 Extensibilidad

El proyecto está diseñado para crecer junto con la iglesia. Para agregar nuevos
tipos de documentos (constitución, historia, eventos, etc.):

1. Crear un nuevo parser en `src/ingestion/`
2. Agregar una nueva colección en ChromaDB (o ampliar la existente)
3. Agregar herramientas en `src/agent/tools.py`
4. El grafo y la API se actualizan automáticamente

---

*Que el Señor bendiga este trabajo para su gloria y la edificación de su iglesia. 🙏*
