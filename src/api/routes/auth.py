"""
Rutas de autenticación.

Endpoints:
  POST /api/v1/auth/token          — Genera o recupera API Key (email + contraseña)
  POST /api/v1/auth/rotate-key     — Rota la API Key (requiere credenciales)
  GET  /api/v1/auth/me             — Info del usuario autenticado (requiere API Key)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr

from src.auth.database import authenticate_user, rotate_api_key
from src.auth.dependencies import require_api_key

router = APIRouter(prefix="/auth", tags=["Autenticación"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    email: str = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., min_length=4, description="Contraseña")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "himnario.universal@hotmail.com",
                "password": "pass15s15qs",
            }
        }


class TokenResponse(BaseModel):
    api_key: str = Field(..., description="API Key para usar en header X-API-Key")
    app_name: str = Field(..., description="Nombre de la aplicación asociada")
    email: str
    message: str = "Incluye este valor en el header: X-API-Key: <api_key>"


class RotateKeyResponse(BaseModel):
    api_key: str
    message: str = "API Key rotada. Actualiza tu aplicación con la nueva key."


class UserInfoResponse(BaseModel):
    email: str
    app_name: str
    is_active: bool
    created_at: str
    last_login: str | None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtener API Key",
    description=(
        "Autentica con email y contraseña y devuelve la API Key de la aplicación. "
        "La API Key es **persistente**: siempre se devuelve la misma key mientras "
        "no se rote explícitamente. Úsala en el header `X-API-Key` en todas las "
        "demás peticiones."
    ),
)
async def get_token(request: TokenRequest) -> TokenResponse:
    user = authenticate_user(email=request.email, password=request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
        )

    return TokenResponse(
        api_key=user["api_key"],
        app_name=user["app_name"],
        email=user["email"],
    )


@router.post(
    "/rotate-key",
    response_model=RotateKeyResponse,
    summary="Rotar API Key",
    description=(
        "Invalida la API Key actual y genera una nueva. "
        "Requiere credenciales válidas. "
        "**Atención:** Deberás actualizar la key en tu aplicación Flutter."
    ),
)
async def rotate_key(request: TokenRequest) -> RotateKeyResponse:
    user = authenticate_user(email=request.email, password=request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
        )

    new_key = rotate_api_key(email=request.email)
    if not new_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo rotar la API Key.",
        )

    return RotateKeyResponse(api_key=new_key)


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Info del usuario autenticado",
    description="Devuelve información del usuario dueño de la API Key.",
)
async def get_me(user: dict = Depends(require_api_key)) -> UserInfoResponse:
    return UserInfoResponse(
        email=user["email"],
        app_name=user["app_name"],
        is_active=bool(user["is_active"]),
        created_at=user.get("created_at") or "",
        last_login=user.get("last_login"),
    )