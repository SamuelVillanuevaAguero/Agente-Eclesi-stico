"""
Dependencias de autenticación para FastAPI.
Usa el header 'X-API-Key' en todos los endpoints protegidos.
"""
from __future__ import annotations

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from src.auth.database import get_user_by_api_key

# ─── Esquema de seguridad (aparece en Swagger UI automáticamente) ─────────────
_api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    description="API Key obtenida desde `POST /api/v1/auth/token`",
    auto_error=True,
)


async def require_api_key(api_key: str = Security(_api_key_scheme)) -> dict:
    """
    Dependencia FastAPI que valida el header X-API-Key.

    Uso en cualquier endpoint:
        @router.get("/ruta", dependencies=[Depends(require_api_key)])

    O para acceder al usuario autenticado:
        @router.get("/ruta")
        async def endpoint(user: dict = Depends(require_api_key)):
            ...
    """
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o inactiva. Obtén tu key en POST /api/v1/auth/token",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return user