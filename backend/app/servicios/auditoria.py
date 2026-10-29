"""Registro de auditoría encadenado (RQF25, RQNF08)."""
import json
import threading
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..crypto.ecc import sha256_hex
from ..models import Auditoria

GENESIS = "0" * 64
_lock = threading.Lock()


def _hash(anterior: str, reg: Auditoria) -> str:
    contenido = json.dumps([
        anterior, reg.id_usuario, reg.actor, reg.accion, reg.descripcion,
        reg.fecha_hora.astimezone(UTC).isoformat(), reg.direccion_ip, reg.resultado,
    ], ensure_ascii=False)
    return sha256_hex(contenido.encode())


def registrar(
    db: Session, accion: str, *, actor: str = "sistema", id_usuario: int | None = None,
    descripcion: str | None = None, ip: str | None = None, resultado: str = "exito", commit: bool = True,
) -> Auditoria:
    with _lock:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(20260906)"))
        ultimo = db.scalar(select(Auditoria.hash).order_by(Auditoria.id_auditoria.desc()).limit(1))
        reg = Auditoria(
            id_usuario=id_usuario, actor=actor, accion=accion, descripcion=descripcion,
            fecha_hora=datetime.now(UTC), direccion_ip=ip, resultado=resultado,
            hash_anterior=ultimo or GENESIS,
        )
        reg.hash = _hash(reg.hash_anterior, reg)
        db.add(reg)
        if commit:
            db.commit()
        else:
            db.flush()
        return reg


def verificar_cadena(db: Session) -> dict:
    anterior = GENESIS
    total = 0
    for reg in db.scalars(select(Auditoria).order_by(Auditoria.id_auditoria)):
        total += 1
        if reg.hash_anterior != anterior or _hash(anterior, reg) != reg.hash:
            return {"integra": False, "registros": total, "roto_en": reg.id_auditoria}
        anterior = reg.hash
    return {"integra": True, "registros": total, "roto_en": None}
