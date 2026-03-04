"""
Recuperador de himnos desde ChromaDB.
Ofrece búsqueda semántica, por número, por ocasión y por tono.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings

from src.config import settings


# ─── Mapas de normalización ────────────────────────────────────────────────────

OCCASION_ALIASES: dict[str, str] = {
    # cosechas
    "cosecha": "cosechas", "cosechas": "cosechas",
    "fiesta de cosechas": "cosechas",
    # primicias
    "primicia": "primicias", "primicias": "primicias",
    "fiesta de primicias": "primicias", "fiesta de las primicias": "primicias",
    # pentecostés
    "pentecostés": "pentecostes", "pentecostes": "pentecostes",
    "pentecostés": "pentecostes",
    # ascensión
    "ascensión": "ascension", "ascension": "ascension",
    "ascención": "ascension",
    # navidad
    "navidad": "navidad", "natal": "navidad", "christmas": "navidad",
    "noche de paz": "navidad",
    # semana santa
    "semana santa": "semana_santa", "via crucis": "semana_santa",
    "viernes santo": "semana_santa", "pasion": "semana_santa",
    "pasión": "semana_santa", "calvario": "semana_santa",
    # resurrección
    "resurrección": "resurreccion", "resurreccion": "resurreccion",
    "pascua": "resurreccion",
    # bautismo
    "bautismo": "bautismo", "bautizo": "bautismo",
    # santa cena
    "santa cena": "santa_cena", "cena del señor": "santa_cena",
    "comunión": "santa_cena", "comunion": "santa_cena",
    # trabajo / siembra
    "dia del trabajo": "trabajo_siembra", "siembra": "trabajo_siembra",
    "trabajo": "trabajo_siembra",
    # misión
    "mision": "mision", "misión": "mision", "evangelismo": "mision",
}

TONE_ALIASES: dict[str, str] = {
    # inglés / abreviatura → nombre en archivos
    "c": "C Mayor", "c mayor": "C Mayor", "do": "C Mayor", "do mayor": "C Mayor",
    "d": "D Mayor", "d mayor": "D Mayor", "re": "D Mayor", "re mayor": "D Mayor",
    "e": "E Mayor", "e mayor": "E Mayor", "mi": "E Mayor", "mi mayor": "E Mayor",
    "f": "F Mayor", "f mayor": "F Mayor", "fa": "F Mayor", "fa mayor": "F Mayor",
    "g": "G Mayor", "g mayor": "G Mayor", "sol": "G Mayor", "sol mayor": "G Mayor",
    "a": "A Mayor", "a mayor": "A Mayor", "la": "LA Mayor", "la mayor": "LA Mayor",
    "b": "B Mayor", "b mayor": "B Mayor", "si": "B Mayor", "si mayor": "B Mayor",
}


def normalize_occasion(raw: str) -> str:
    """Normaliza un texto de ocasión a la clave interna."""
    return OCCASION_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def normalize_tone(raw: str) -> str:
    """Normaliza un texto de tono al formato del himnario."""
    return TONE_ALIASES.get(raw.strip().lower(), raw.strip())


# ─── Retriever ────────────────────────────────────────────────────────────────

class HimnosRetriever:
    """
    Interfaz de recuperación de himnos desde ChromaDB.
    Inicializa conexión al primer uso.
    """

    def __init__(self) -> None:
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embeddings: Optional[OpenAIEmbeddings] = None

    # ── Inicialización perezosa ─────────────────────────────────────────────
    def _get_collection(self) -> chromadb.Collection:
        if self._collection is None:
            settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(settings.chroma_persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_collection(settings.chroma_collection)
        return self._collection

    def _get_embeddings(self) -> OpenAIEmbeddings:
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.openai_api_key,
            )
        return self._embeddings

    # ── Métodos de búsqueda ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Búsqueda semántica de himnos.

        Args:
            query:  Consulta en lenguaje natural
            k:      Número máximo de resultados
            where:  Filtro de metadata ChromaDB (opcional)

        Returns:
            Lista de dicts con campos: numero, titulo, tono, ocasiones,
            referencias_biblicas, contenido, score
        """
        col = self._get_collection()
        emb_fn = self._get_embeddings()

        query_vector = emb_fn.embed_query(query)
        kwargs = dict(
            query_embeddings=[query_vector],
            n_results=min(k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where

        results = col.query(**kwargs)
        return self._format_results(results)

    def get_by_number(self, numero: int) -> Optional[dict]:
        """Obtiene un himno exacto por su número."""
        col = self._get_collection()
        doc_id = f"himno_{numero:04d}"
        try:
            result = col.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )
            if result["ids"]:
                return {
                    "numero": result["metadatas"][0]["numero"],
                    "titulo": result["metadatas"][0]["titulo"],
                    "tono": result["metadatas"][0]["tono"],
                    "ocasiones": self._split_meta(result["metadatas"][0], "ocasiones"),
                    "referencias_biblicas": self._split_meta(
                        result["metadatas"][0], "referencias_biblicas"
                    ),
                    "contenido": result["documents"][0],
                    "score": 1.0,
                }
        except Exception:
            pass
        return None

    def get_by_occasion(self, ocasion: str, k: int = 10) -> list[dict]:
        """
        Filtra himnos por ocasión litúrgica.
        Combina filtro de metadata + búsqueda semántica para máxima cobertura.
        """
        normalized = normalize_occasion(ocasion)

        # 1) Filtro por metadata (colección ChromaDB)
        try:
            col = self._get_collection()
            result = col.get(
                where={"ocasiones": {"$contains": normalized}},
                include=["documents", "metadatas"],
                limit=k,
            )
            if result["ids"]:
                hymns = []
                for doc, meta in zip(result["documents"], result["metadatas"]):
                    hymns.append({
                        "numero": meta["numero"],
                        "titulo": meta["titulo"],
                        "tono": meta["tono"],
                        "ocasiones": self._split_meta(meta, "ocasiones"),
                        "referencias_biblicas": self._split_meta(meta, "referencias_biblicas"),
                        "contenido": doc,
                        "score": 1.0,
                    })
                if hymns:
                    return sorted(hymns, key=lambda x: x["numero"])
        except Exception:
            pass

        # 2) Fallback: búsqueda semántica con la ocasión como query
        return self.search(query=f"himno para {ocasion}", k=k)

    def get_by_tone(self, tono: str, k: int = 10) -> list[dict]:
        """Filtra himnos por tono musical."""
        normalized = normalize_tone(tono)
        try:
            col = self._get_collection()
            result = col.get(
                where={"tono": {"$eq": normalized}},
                include=["documents", "metadatas"],
                limit=k,
            )
            if result["ids"]:
                hymns = []
                for doc, meta in zip(result["documents"], result["metadatas"]):
                    hymns.append({
                        "numero": meta["numero"],
                        "titulo": meta["titulo"],
                        "tono": meta["tono"],
                        "ocasiones": self._split_meta(meta, "ocasiones"),
                        "referencias_biblicas": self._split_meta(meta, "referencias_biblicas"),
                        "contenido": doc,
                        "score": 1.0,
                    })
                return sorted(hymns, key=lambda x: x["numero"])
        except Exception:
            pass
        return []

    def search_by_biblical_ref(self, referencia: str, k: int = 5) -> list[dict]:
        """Busca himnos que referencien un pasaje bíblico."""
        # Búsqueda semántica enriquecida
        return self.search(
            query=f"himno relacionado con {referencia} biblia",
            k=k,
        )

    def list_all(self, limit: int = 535, offset: int = 0) -> list[dict]:
        """Lista todos los himnos ordenados por número."""
        col = self._get_collection()
        result = col.get(
            include=["metadatas"],
            limit=limit,
            offset=offset,
        )
        hymns = []
        for meta in result["metadatas"]:
            hymns.append({
                "numero": meta["numero"],
                "titulo": meta["titulo"],
                "tono": meta["tono"],
                "ocasiones": self._split_meta(meta, "ocasiones"),
                "referencias_biblicas": self._split_meta(meta, "referencias_biblicas"),
                "archivo": meta["archivo"],
            })
        return sorted(hymns, key=lambda x: x["numero"])

    def count(self) -> int:
        """Devuelve el total de himnos indexados."""
        try:
            return self._get_collection().count()
        except Exception:
            return 0

    # ── Utilidades internas ─────────────────────────────────────────────────
    @staticmethod
    def _split_meta(meta: dict, key: str) -> list[str]:
        val = meta.get(key, "")
        return [v.strip() for v in val.split(",") if v.strip()] if val else []

    @staticmethod
    def _format_results(raw: dict) -> list[dict]:
        hymns = []
        for i, doc_id in enumerate(raw.get("ids", [[]])[0]):
            meta = raw["metadatas"][0][i]
            distance = raw["distances"][0][i]
            score = round(1 - distance, 4)  # cosine similarity
            hymns.append({
                "numero": meta["numero"],
                "titulo": meta["titulo"],
                "tono": meta["tono"],
                "ocasiones": HimnosRetriever._split_meta(meta, "ocasiones"),
                "referencias_biblicas": HimnosRetriever._split_meta(
                    meta, "referencias_biblicas"
                ),
                "contenido": raw["documents"][0][i],
                "score": score,
            })
        return hymns


# ─── Singleton ────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_retriever() -> HimnosRetriever:
    """Devuelve la instancia singleton del retriever."""
    return HimnosRetriever()
