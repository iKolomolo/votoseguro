"""Llavero del sistema: pares ECC por propósito, guardados en CLAVE_SISTEMA con la privada envuelta."""
import threading

from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_master_key
from ..models import ClaveSistema
from . import ecc

PROPOSITOS = ("datos", "biometria", "documento", "firma", "respaldo")

_cache: dict[str, ec.EllipticCurvePrivateKey] = {}
_lock = threading.Lock()


def inicializar(db: Session) -> None:
    """Crea los pares que falten. Se llama al arrancar."""
    for proposito in PROPOSITOS:
        if db.scalar(select(ClaveSistema).where(ClaveSistema.proposito == proposito)) is None:
            privada = ecc.generar_par()
            db.add(ClaveSistema(
                proposito=proposito,
                clave_publica=ecc.exportar_publica(privada.public_key()),
                clave_privada=ecc.envolver_privada(privada, get_master_key(), f"sistema:{proposito}".encode()),
            ))
    db.commit()


def privada(db: Session, proposito: str) -> ec.EllipticCurvePrivateKey:
    with _lock:
        if proposito not in _cache:
            fila = db.scalar(select(ClaveSistema).where(ClaveSistema.proposito == proposito))
            if fila is None:
                raise RuntimeError(f"No existe la llave del sistema '{proposito}'")
            _cache[proposito] = ecc.desenvolver_privada(
                fila.clave_privada, get_master_key(), f"sistema:{proposito}".encode()
            )
        return _cache[proposito]


def publica(db: Session, proposito: str) -> ec.EllipticCurvePublicKey:
    return privada(db, proposito).public_key()


def limpiar_cache() -> None:
    """Necesario tras restaurar un respaldo, porque las llaves pueden haber cambiado."""
    with _lock:
        _cache.clear()


def cifrar_texto(db: Session, valor: str | None, contexto: str) -> bytes | None:
    if valor is None:
        return None
    return ecc.cifrar(publica(db, "datos"), valor.encode(), contexto.encode())


def descifrar_texto(db: Session, paquete: bytes | None, contexto: str) -> str | None:
    if paquete is None:
        return None
    return ecc.descifrar(privada(db, "datos"), paquete, contexto.encode()).decode()


def indice_documento(tipo: str, numero: str) -> str:
    clave = ecc.sub_clave(get_master_key(), "indice-documento")
    return ecc.indice_ciego(clave, f"{tipo}:{numero}")
