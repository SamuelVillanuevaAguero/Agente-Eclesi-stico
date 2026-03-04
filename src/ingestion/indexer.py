"""
Indexador de himnos en ChromaDB.
Crea embeddings con OpenAI o con modelos locales (HuggingFace).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.ingestion.parser import parse_all_hymns
from src.ingestion.embeddings import get_embeddings


def _get_chroma_client() -> chromadb.ClientAPI:
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _build_metadata(hymn: dict) -> dict:
    return {
        "numero": hymn["numero"],
        "titulo": hymn["titulo"],
        "tono": hymn["tono"],
        "ocasiones": ",".join(hymn["ocasiones"]) if hymn["ocasiones"] else "",
        "referencias_biblicas": (
            ",".join(hymn["referencias_biblicas"])
            if hymn["referencias_biblicas"]
            else ""
        ),
        "archivo": hymn["archivo"],
    }


def _embed_with_retry(embeddings_fn, docs: list[str], max_intentos: int = 5) -> list:
    """Genera embeddings con reintentos automáticos ante rate limit."""
    ultimo_error = None

    for intento in range(max_intentos):
        try:
            return embeddings_fn.embed_documents(docs)
        except Exception as e:
            ultimo_error = e
            es_rate_limit = (
                "429" in str(e)
                or "rate" in str(e).lower()
                or "quota" in str(e).lower()
            )
            if es_rate_limit:
                espera = 15 * (intento + 1)   # 15s, 30s, 45s, 60s, 75s
                print(f"  ⏳ Rate limit (intento {intento+1}/{max_intentos}) — esperando {espera}s...")
                time.sleep(espera)
            else:
                raise

    raise RuntimeError(
        f"\n❌ Se agotaron {max_intentos} reintentos por rate limit.\n"
        f"   Opciones:\n"
        f"   1. Espera 1-2 min y vuelve a ejecutar: python scripts/ingest.py --force\n"
        f"   2. Usa embeddings locales GRATUITOS — en tu .env pon:\n"
        f"      EMBEDDING_PROVIDER=local\n"
        f"      Instala: pip install langchain-huggingface sentence-transformers\n"
    ) from ultimo_error


def index_hymns(hymns_dir: Optional[Path] = None, force: bool = False) -> int:
    hymns_dir = hymns_dir or settings.hymns_dir
    client = _get_chroma_client()
    embeddings_fn = get_embeddings()

    if force:
        try:
            client.delete_collection(settings.chroma_collection)
            print(f"  🗑️  Colección '{settings.chroma_collection}' eliminada.")
        except Exception:
            pass

    try:
        collection = client.get_collection(settings.chroma_collection)
        existing_count = collection.count()
        if existing_count > 0 and not force:
            print(f"  ℹ️  La colección ya contiene {existing_count} documentos. Usa --force para re-indexar.")
            return existing_count
    except Exception:
        collection = client.create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    print(f"  📖 Parseando himnos desde '{hymns_dir}'...")
    hymns = parse_all_hymns(hymns_dir)
    print(f"  ✅ {len(hymns)} himnos parseados.")

    BATCH_SIZE    = 10   # lotes pequeños para no saturar el rate limit
    PAUSA_LOTES   = 8    # segundos entre lotes
    total_indexed = 0
    total_batches = (len(hymns) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(hymns), BATCH_SIZE):
        batch     = hymns[i : i + BATCH_SIZE]
        docs      = [h["doc_texto"] for h in batch]
        ids       = [f"himno_{h['numero']:04d}" for h in batch]
        metadatas = [_build_metadata(h) for h in batch]
        batch_num = i // BATCH_SIZE + 1

        print(f"  ⚙️  Lote {batch_num}/{total_batches} — himnos #{batch[0]['numero']}–#{batch[-1]['numero']}...")

        vectors = _embed_with_retry(embeddings_fn, docs)

        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=docs,
            metadatas=metadatas,
        )
        total_indexed += len(batch)
        print(f"  ✅ {total_indexed}/{len(hymns)} himnos indexados")

        if i + BATCH_SIZE < len(hymns):
            time.sleep(PAUSA_LOTES)

    summary_path = settings.chroma_persist_dir / "index_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "total_hymns": total_indexed,
        "collection": settings.chroma_collection,
        "embedding_model": settings.embedding_model,
        "hymns_dir": str(hymns_dir),
        "occasions_index": _build_occasions_summary(hymns),
        "tones_index": _build_tones_summary(hymns),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"  📋 Resumen guardado en '{summary_path}'")
    return total_indexed


def _build_occasions_summary(hymns: list[dict]) -> dict:
    index: dict[str, list[int]] = {}
    for h in hymns:
        for occ in h["ocasiones"]:
            index.setdefault(occ, []).append(h["numero"])
    return index


def _build_tones_summary(hymns: list[dict]) -> dict:
    index: dict[str, list[int]] = {}
    for h in hymns:
        tono = h["tono"]
        if tono and tono != "INDEFINIDO":
            index.setdefault(tono, []).append(h["numero"])
    return index


def collection_exists() -> bool:
    try:
        client = _get_chroma_client()
        col = client.get_collection(settings.chroma_collection)
        return col.count() > 0
    except Exception:
        return False
