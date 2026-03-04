#!/usr/bin/env python
"""
Script de indexación del himnario.

Uso:
    python scripts/ingest.py              # Indexa (sin sobrescribir si ya existe)
    python scripts/ingest.py --force      # Re-indexa forzando reemplazo
    python scripts/ingest.py --stats      # Solo muestra estadísticas del índice
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Asegurar que el directorio raíz esté en el path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.config import settings
from src.ingestion.indexer import index_hymns, collection_exists
from src.ingestion.parser import parse_all_hymns


def print_stats() -> None:
    """Muestra estadísticas del índice existente."""
    summary_path = settings.chroma_persist_dir / "index_summary.json"
    if not summary_path.exists():
        print("❌ No existe resumen de indexación. Ejecuta: python scripts/ingest.py")
        return

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    print("\n" + "═" * 60)
    print("  📊  ESTADÍSTICAS DEL HIMNARIO INDEXADO")
    print("═" * 60)
    print(f"  Total himnos:       {data['total_hymns']}")
    print(f"  Colección:          {data['collection']}")
    print(f"  Modelo embedding:   {data['embedding_model']}")
    print(f"  Directorio himnos:  {data['hymns_dir']}")

    print("\n  🎉  Por ocasión litúrgica:")
    for occ, nums in sorted(data.get("occasions_index", {}).items(), key=lambda x: -len(x[1])):
        print(f"    {occ:<22} {len(nums)} himnos  (ej: #{nums[0]})")

    print("\n  🎵  Por tono musical:")
    for tone, nums in sorted(data.get("tones_index", {}).items(), key=lambda x: -len(x[1])):
        print(f"    {tone:<22} {len(nums)} himnos")
    print("═" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexador del Himnario ICUAJP en ChromaDB"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-indexa aunque ya existan datos (borra colección previa)"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Solo muestra estadísticas del índice actual"
    )
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    print("\n" + "═" * 60)
    print("  🙏  INDEXADOR DEL HIMNARIO — ICUAJP")
    print("═" * 60)

    # Validar directorio de himnos
    hymns_dir = settings.hymns_dir
    if not hymns_dir.exists():
        print(f"❌ Directorio de himnos no encontrado: '{hymns_dir}'")
        print("   Asegúrate de que los archivos .txt estén en ese directorio.")
        sys.exit(1)

    txt_files = list(hymns_dir.glob("*.txt"))
    if not txt_files:
        print(f"❌ No se encontraron archivos .txt en '{hymns_dir}'")
        sys.exit(1)

    print(f"  📁 Directorio: {hymns_dir.resolve()}")
    print(f"  📄 Archivos .txt encontrados: {len(txt_files)}")
    print(f"  🗄️  Base de datos: {settings.chroma_persist_dir.resolve()}")
    print(f"  🤖 Modelo de embeddings: {settings.embedding_model}")

    if collection_exists() and not args.force:
        print("\n  ℹ️  Ya existe una colección indexada.")
        print("     Usa --force para re-indexar completamente.")
        print_stats()
        return

    print("\n  ⏳ Iniciando indexación...\n")
    t0 = time.time()

    try:
        count = index_hymns(hymns_dir=hymns_dir, force=args.force)
        elapsed = time.time() - t0

        print(f"\n  ✅ ¡Indexación completa!")
        print(f"  📊 {count} himnos indexados en {elapsed:.1f} segundos.")
        print_stats()

    except Exception as exc:
        print(f"\n  ❌ Error durante la indexación: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
