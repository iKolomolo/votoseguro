"""Límites de intentos, guardados en la base de datos para que no se reinicien cuando el servidor se reinicia.

Cada contador tiene una clave (por ejemplo "bio:<índice del documento>" o "identificacion:ip:<ip>") y vence al
terminar su ventana. La clave se guarda como HMAC-SHA256 con una llave derivada de la maestra: la tabla no contiene
direcciones IP ni documentos legibles. Los contadores vencidos se borran en cada ciclo de retención.
"""
import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import get_master_key, get_settings
from ..crypto.ecc import sub_clave
from ..models import Limite
from ..seguridad import DB, ip_cliente


class LimiteExcedido(Exception):
    def __init__(self, segundos: int):
        super().__init__(f"Espere {segundos} segundos")
        self.segundos = segundos


def _clave(nombre: str) -> str:
    return hmac.new(sub_clave(get_master_key(), "limites"), nombre.encode(), hashlib.sha256).hexdigest()


def _vigente(db: Session, nombre: str) -> Limite | None:
    fila = db.get(Limite, _clave(nombre))
    if fila is not None and fila.vence <= datetime.now(UTC):
        db.delete(fila)
        db.flush()
        return None
    return fila


def contador(db: Session, nombre: str) -> int:
    fila = _vigente(db, nombre)
    return 0 if fila is None else fila.contador


def segundos_restantes(db: Session, nombre: str) -> int:
    fila = _vigente(db, nombre)
    return 0 if fila is None else max(math.ceil((fila.vence - datetime.now(UTC)).total_seconds()), 1)


def sumar(db: Session, nombre: str, segundos: int) -> int:
    """Suma 1 al contador (lo crea con la ventana indicada si no existe) y devuelve el total. No hace commit."""
    fila = _vigente(db, nombre)
    if fila is None:
        fila = Limite(clave=_clave(nombre), contador=0, vence=datetime.now(UTC) + timedelta(seconds=segundos))
        db.add(fila)
    fila.contador += 1
    db.flush()
    return fila.contador


def reiniciar(db: Session, nombre: str) -> None:
    db.execute(delete(Limite).where(Limite.clave == _clave(nombre)))


def consumir(db: Session, nombre: str, maximo: int, segundos: int) -> None:
    """Cuenta un intento; si ya se hicieron `maximo` en la ventana, lanza LimiteExcedido. Hace commit."""
    if contador(db, nombre) >= maximo:
        raise LimiteExcedido(segundos_restantes(db, nombre))
    sumar(db, nombre, segundos)
    db.commit()


def purgar(db: Session) -> int:
    """Borra los contadores vencidos. No hace commit."""
    return db.execute(delete(Limite).where(Limite.vence <= datetime.now(UTC))).rowcount


def en_minutos(segundos: int) -> str:
    minutos = max(math.ceil(segundos / 60), 1)
    return "1 minuto" if minutos == 1 else f"{minutos} minutos"


def por_ip(nombre: str, ajuste_maximo: str, segundos: int):
    """Dependencia de FastAPI: máximo de peticiones por dirección IP en la ventana. `ajuste_maximo` es el nombre del
    ajuste de configuración con el máximo, para poder cambiarlo sin tocar código."""
    def dependencia(request: Request, db: DB) -> None:
        try:
            consumir(db, f"{nombre}:ip:{ip_cliente(request)}", getattr(get_settings(), ajuste_maximo), segundos)
        except LimiteExcedido as e:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                f"Demasiados intentos desde esta conexión. Espere {en_minutos(e.segundos)} y vuelva "
                                "a intentarlo.", headers={"Retry-After": str(e.segundos)}) from None
    return Depends(dependencia)
