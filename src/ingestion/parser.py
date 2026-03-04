"""
Parser de archivos de himnos.
Lee los .txt del himnario y extrae metadata estructurada.
"""
import re
from pathlib import Path
from typing import Optional


# ─── Patrones de referencias bíblicas ──────────────────────────────────────────
_LIBROS = (
    r"Génesis|Éxodo|Levítico|Números|Deuteronomio|Josué|Jueces|Rut|"
    r"1\s*Samuel|2\s*Samuel|1\s*Reyes|2\s*Reyes|1\s*Crónicas|2\s*Crónicas|"
    r"Esdras|Nehemías|Ester|Job|Salmos|Proverbios|Eclesiastés|Cantares|"
    r"Isaías|Jeremías|Lamentaciones|Ezequiel|Daniel|Oseas|Joel|Amós|"
    r"Abdías|Jonás|Miqueas|Nahúm|Habacuc|Sofonías|Hageo|Zacarías|Malaquías|"
    r"Mateo|Marcos|Lucas|Juan|Hechos|Romanos|"
    r"1\s*Corintios|2\s*Corintios|Gálatas|Efesios|Filipenses|Colosenses|"
    r"1\s*Tesalonicenses|2\s*Tesalonicenses|1\s*Timoteo|2\s*Timoteo|"
    r"Tito|Filemón|Hebreos|Santiago|1\s*Pedro|2\s*Pedro|"
    r"1\s*Juan|2\s*Juan|3\s*Juan|Judas|Apocalipsis"
)
BIBLICAL_REF_RE = re.compile(
    rf"(?:{_LIBROS})\s+\d+:\d+(?:[–\-]\d+)?",
    re.IGNORECASE,
)

# ─── Mapeo de ocasiones litúrgicas ─────────────────────────────────────────────
OCCASION_MAP: dict[str, list[str]] = {
    "cosechas": [
        "cosecha", "cosechas", "fiesta de cosechas",
    ],
    "primicias": [
        "primicia", "primicias", "fiesta de las primicias",
        "himno especial para la fiesta",
    ],
    "pentecostes": [
        "pentecostés", "pentecostes", "espíritu santo", "espiritu santo",
        "lenguas de fuego", "fuego divino",
    ],
    "ascension": [
        "ascensión", "ascension", "ascendió", "ascendio al cielo",
        "subió al cielo", "sube al padre",
    ],
    "navidad": [
        "navidad", "noche de paz", "natividad", "nacimiento de jesús",
        "nació en belén", "pesebre", "belen", "belén",
        "pastores", "reyes magos", "estrella de oriente",
    ],
    "semana_santa": [
        "calvario", "pasión", "crucifixión", "semana santa",
        "getsemaní", "getsemani", "via crucis", "siete palabras",
        "entrada triunfal", "domingo de ramos",
    ],
    "resurreccion": [
        "resurrección", "resucitó", "resucito", "sepulcro vacío",
        "pascua", "aleluya resucitó", "del sepulcro",
    ],
    "bautismo": [
        "bautismo", "bautizado", "bautizar", "aguas del bautismo",
        "sepultados con él", "fuimos sepultados",
    ],
    "santa_cena": [
        "santa cena", "cena del señor", "pan y el vino",
        "su cuerpo", "copa de", "comed este pan",
        "comunión", "cena misteriosa",
    ],
    "trabajo_siembra": [
        "día del trabajo", "labradores", "sembrador", "siembra",
        "temporal", "lluvia temprana", "lluvia tardía",
    ],
    "mision": [
        "evangelio", "misión", "predicar", "sembrar la simiente",
        "llevar la luz", "mensajero",
    ],
    "dedicacion_templo": [
        "dedicación", "templo", "casa de dios", "casa del señor",
    ],
}

# ─── Tonos reconocidos ──────────────────────────────────────────────────────────
KNOWN_TONES = {
    "C Mayor", "Do Mayor",
    "D Mayor", "Re Mayor",
    "E Mayor", "Mi Mayor",
    "F Mayor", "Fa Mayor",
    "G Mayor", "Sol Mayor",
    "A Mayor", "La Mayor",
    "B Mayor", "Si Mayor",
    "C Menor", "Do Menor",
    "D Menor", "Re Menor",
    "E Menor", "Mi Menor",
    "F Menor", "Fa Menor",
    "G Menor", "Sol Menor",
    "A Menor", "La Menor",
    "B Menor", "Si Menor",
}


def _normalize_title(raw: str) -> str:
    """Convierte MAYÚSCULAS a Título Capitalizado de forma inteligente."""
    if raw.isupper():
        stop_words = {"a", "al", "de", "del", "en", "y", "e", "o", "u", "el", "la",
                      "los", "las", "un", "una", "por", "con", "sin", "que", "no"}
        words = raw.lower().split()
        return " ".join(
            w.capitalize() if i == 0 or w not in stop_words else w
            for i, w in enumerate(words)
        )
    return raw.strip()


def _extract_tone(lines: list[str]) -> str:
    """Extrae el tono musical del himno (segunda línea no vacía)."""
    non_empty = [l.strip() for l in lines if l.strip()]
    if len(non_empty) >= 2:
        candidate = non_empty[1]
        # Es un tono si es corto y no parece una estrofa
        if len(candidate) < 40 and not candidate.startswith(("1.", "2.", "CORO", "Estrib")):
            return candidate.strip()
    return "INDEFINIDO"


def _extract_occasions(text_lower: str) -> list[str]:
    """Detecta ocasiones litúrgicas a partir del contenido del himno."""
    found = []
    for occasion, keywords in OCCASION_MAP.items():
        if any(kw in text_lower for kw in keywords):
            found.append(occasion)
    return found


def _extract_biblical_refs(text: str) -> list[str]:
    """Extrae referencias bíblicas (ej: Juan 3:16)."""
    refs = BIBLICAL_REF_RE.findall(text)
    # Normalizar y deduplicar
    seen, unique = set(), []
    for r in refs:
        normalized = " ".join(r.split())
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def parse_hymn_file(filepath: Path) -> dict:
    """
    Parsea un archivo .txt de himno y devuelve un dict con metadata estructurada.

    Campos devueltos:
        numero          (int)   — número de himno (del nombre de archivo)
        titulo          (str)   — título del himno
        tono            (str)   — tono musical o 'INDEFINIDO'
        ocasiones       (list)  — lista de ocasiones litúrgicas detectadas
        referencias_biblicas (list) — referencias bíblicas encontradas
        contenido_completo (str) — texto completo original
        doc_texto       (str)   — texto enriquecido para embedding
        archivo         (str)   — nombre del archivo original
    """
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    # ── Número ──────────────────────────────────────────────────────────────
    stem = filepath.stem
    m = re.match(r"^(\d+)", stem)
    numero = int(m.group(1)) if m else 0

    # ── Título ───────────────────────────────────────────────────────────────
    titulo_raw = next((l.strip() for l in lines if l.strip()), "Sin título")
    titulo = _normalize_title(titulo_raw)

    # ── Tono ─────────────────────────────────────────────────────────────────
    tono = _extract_tone(lines)

    # ── Análisis de contenido ─────────────────────────────────────────────────
    text_lower = text.lower()
    ocasiones = _extract_occasions(text_lower)
    referencias_biblicas = _extract_biblical_refs(text)

    # ── Texto enriquecido para embedding ─────────────────────────────────────
    meta_parts = [f"HIMNO #{numero}: {titulo}", f"Tono musical: {tono}"]
    if ocasiones:
        meta_parts.append("Ocasiones litúrgicas: " + ", ".join(ocasiones))
    if referencias_biblicas:
        meta_parts.append("Referencias bíblicas: " + ", ".join(referencias_biblicas))

    doc_texto = "\n".join(meta_parts) + "\n\n" + text.strip()

    return {
        "numero": numero,
        "titulo": titulo,
        "tono": tono,
        "ocasiones": ocasiones,
        "referencias_biblicas": referencias_biblicas,
        "contenido_completo": text.strip(),
        "doc_texto": doc_texto,
        "archivo": filepath.name,
    }


def parse_all_hymns(hymns_dir: Path) -> list[dict]:
    """Parsea todos los archivos .txt de un directorio."""
    files = sorted(hymns_dir.glob("*.txt"))
    hymnals = []
    for f in files:
        try:
            hymn = parse_hymn_file(f)
            if hymn["numero"] > 0:          # Descartar archivos sin número
                hymnals.append(hymn)
        except Exception as exc:
            print(f"  ⚠️  Error parseando {f.name}: {exc}")
    return hymnals
