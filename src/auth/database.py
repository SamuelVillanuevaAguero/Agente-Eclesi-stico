"""
Base de datos SQLite para autenticación.
Maneja usuarios, contraseñas (hash PBKDF2) y API Keys persistentes.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

_IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))
DB_PATH = Path("/data/auth.db") if _IS_RAILWAY else Path("data/auth.db")

# ─── Ruta de la BD ────────────────────────────────────────────────────────────
DB_PATH = Path("data/auth.db")

# ─── Conexión ─────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row          # Resultados como dict
    conn.execute("PRAGMA journal_mode=WAL") # Mejor concurrencia
    return conn


# ─── Inicialización del esquema ───────────────────────────────────────────────

def init_db() -> None:
    """Crea la tabla de usuarios si no existe."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                api_key       TEXT    UNIQUE,
                app_name      TEXT    DEFAULT '',
                is_active     INTEGER DEFAULT 1,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login    TIMESTAMP
            )
        """)
        conn.commit()


# ─── Hashing de contraseñas (PBKDF2-SHA256, sin dependencias externas) ────────

def hash_password(password: str) -> str:
    """Genera hash seguro con salt aleatorio."""
    salt = os.urandom(16)
    key  = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica contraseña contra hash almacenado."""
    try:
        salt_hex, key_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        key  = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        # Comparación de tiempo constante (evita timing attacks)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


# ─── Gestión de API Keys ──────────────────────────────────────────────────────

def generate_api_key() -> str:
    """Genera API Key criptográficamente segura (48 chars URL-safe)."""
    return secrets.token_urlsafe(36)


# ─── CRUD de usuarios ─────────────────────────────────────────────────────────

def create_user(
    email: str,
    password: str,
    app_name: str = "",
) -> dict:
    """
    Crea un usuario nuevo con su API Key pre-generada.
    Lanza ValueError si el email ya existe.
    """
    password_hash = hash_password(password)
    api_key       = generate_api_key()

    with _get_conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, api_key, app_name)
                VALUES (?, ?, ?, ?)
                """,
                (email.lower().strip(), password_hash, api_key, app_name),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"El usuario '{email}' ya existe.")

    return get_user_by_email(email)  # type: ignore


def get_user_by_email(email: str) -> Optional[dict]:
    """Busca usuario por email. Devuelve None si no existe."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email.lower().strip(),),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_api_key(api_key: str) -> Optional[dict]:
    """Busca usuario por API Key. Devuelve None si no existe o está inactivo."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE api_key = ? AND is_active = 1",
            (api_key,),
        ).fetchone()
    return dict(row) if row else None


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Valida credenciales y actualiza last_login.
    Devuelve el usuario si es válido, None si no.
    """
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None

    # Actualizar last_login
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],),
        )
        conn.commit()

    return user


def rotate_api_key(email: str) -> Optional[str]:
    """
    Regenera la API Key de un usuario.
    Útil para revocar acceso sin eliminar el usuario.
    Devuelve la nueva key, o None si el usuario no existe.
    """
    new_key = generate_api_key()
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET api_key = ? WHERE email = ? AND is_active = 1",
            (new_key, email.lower().strip()),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
    return new_key


def list_users() -> list[dict]:
    """Lista todos los usuarios (sin exponer password_hash ni api_key completa)."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, app_name, is_active, created_at, last_login FROM users"
        ).fetchall()
    return [dict(r) for r in rows]


def deactivate_user(email: str) -> bool:
    """Desactiva un usuario sin eliminarlo."""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET is_active = 0 WHERE email = ?",
            (email.lower().strip(),),
        )
        conn.commit()
        return cur.rowcount > 0