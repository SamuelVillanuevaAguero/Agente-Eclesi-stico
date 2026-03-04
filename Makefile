.PHONY: install ingest api studio help

# ─── Setup ────────────────────────────────────────────────────────────────────
install:
	@echo "📦 Instalando dependencias..."
	pip install -r requirements.txt
	@echo "✅ Dependencias instaladas."

# ─── Ingestion ────────────────────────────────────────────────────────────────
ingest:
	@echo "📖 Indexando himnos en ChromaDB..."
	python scripts/ingest.py
	@echo "✅ Himnario indexado."

ingest-force:
	@echo "🔄 Re-indexando himnos (forzado)..."
	python scripts/ingest.py --force
	@echo "✅ Himnario re-indexado."

# ─── Servidores ───────────────────────────────────────────────────────────────
api:
	@echo "🚀 Iniciando API en http://localhost:8000 ..."
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

api-prod:
	@echo "🚀 Iniciando API (producción)..."
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 2

studio:
	@echo "🎨 Iniciando LangGraph Studio local..."
	langgraph dev

# ─── Utilidades ───────────────────────────────────────────────────────────────
clean-db:
	@echo "🗑️ Eliminando base de datos vectorial..."
	rm -rf data/chroma_db
	@echo "✅ BD eliminada. Ejecuta 'make ingest' para re-indexar."

help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║   Agente Eclesiástico - ICUAJP  |  Comandos disponibles  ║"
	@echo "╠══════════════════════════════════════════════════════════╣"
	@echo "║  make install      Instala todas las dependencias        ║"
	@echo "║  make ingest       Indexa los 535 himnos en ChromaDB     ║"
	@echo "║  make ingest-force Re-indexa forzando reemplazo          ║"
	@echo "║  make api          Inicia FastAPI con hot-reload          ║"
	@echo "║  make api-prod     Inicia FastAPI en producción           ║"
	@echo "║  make studio       Inicia servidor para LangGraph Studio  ║"
	@echo "║  make clean-db     Elimina la BD vectorial               ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
