"""Tokens JWT, contraseñas y dependencias de autorización."""
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_master_key
from .crypto.ecc import sub_clave
from .db import get_db
from .models import Usuario, Votante
from .servicios import monitor

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)

ROL_SUPERADMIN = "Superadministrador"
ROL_ADMIN = "Administrador"
ROL_SUPERVISOR = "Supervisor"

DB = Annotated[Session, Depends(get_db)]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(hash_: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_, password)
    except VerifyMismatchError:
        return False


def _clave_jwt() -> bytes:
    return sub_clave(get_master_key(), "jwt")


def crear_token(sub: str, tipo: str, minutos: int, **extra) -> str:
    ahora = datetime.now(UTC)
    datos = {"sub": sub, "typ": tipo, "iat": ahora, "exp": ahora + timedelta(minutes=minutos),
             "jti": secrets.token_hex(8), **extra}
    return jwt.encode(datos, _clave_jwt(), algorithm="HS256")


def _leer_token(cred: HTTPAuthorizationCredentials | None, tipo: str) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Se requiere autenticación")
    try:
        datos = jwt.decode(cred.credentials, _clave_jwt(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión expiró, inicie de nuevo") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido") from None
    if datos.get("typ") != tipo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token no válido para esta operación")
    return datos


Credenciales = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def token_flujo(*etapas: str):
    """Token temporal del flujo del votante (registro -> cédula -> biometría -> elegibilidad)."""
    def dependencia(cred: Credenciales) -> dict:
        datos = _leer_token(cred, "flujo")
        if datos.get("etapa") not in etapas:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Debe completar el paso anterior")
        return datos
    return dependencia


def votante_actual(cred: Credenciales, db: DB) -> Votante:
    datos = _leer_token(cred, "votante")
    votante = db.get(Votante, int(datos["sub"]))
    if votante is None or votante.estado_habilitacion != "habilitado":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El votante no está habilitado")
    monitor.marcar_votante_activo(votante.id_votante)
    return votante


def usuario_actual(cred: Credenciales, db: DB) -> Usuario:
    datos = _leer_token(cred, "admin")
    usuario = db.get(Usuario, int(datos["sub"]))
    if usuario is None or usuario.estado != "activo":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cuenta inactiva")
    return usuario


def requiere_rol(*roles: str):
    def dependencia(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
        if usuario.rol.nombre not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Su rol no permite esta acción")
        return usuario
    return dependencia


VotanteActual = Annotated[Votante, Depends(votante_actual)]
UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]
Gestor = Annotated[Usuario, Depends(requiere_rol(ROL_SUPERADMIN, ROL_ADMIN))]
SuperAdmin = Annotated[Usuario, Depends(requiere_rol(ROL_SUPERADMIN))]


def ip_cliente(request: Request) -> str | None:
    return request.client.host if request.client else None
