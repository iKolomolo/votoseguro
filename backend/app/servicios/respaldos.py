"""Copias de seguridad cifradas y restauración (RQF30, RQF31, RQNF10).

Cada respaldo es un volcado JSON de todas las tablas, cifrado con ECIES (llave "respaldo") y firmado con
ECDSA (llave "firma"). Antes de restaurar se comprueban el hash y la firma.
"""
import base64
import json
import zlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Integer, delete, func, insert, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crypto import ecc, llavero
from ..db import Base
from ..models import Respaldo
from . import auditoria

_EXCLUIDAS = {"respaldo"}
_CONTEXTO = b"respaldo-v1"


def _tablas():
    return [t for t in Base.metadata.sorted_tables if t.name not in _EXCLUIDAS]


def _a_json(valor):
    if isinstance(valor, bytes):
        return {"$b": base64.b64encode(valor).decode()}
    if isinstance(valor, datetime):
        return {"$d": valor.isoformat()}
    return valor


def _desde_json(valor):
    if isinstance(valor, dict) and "$b" in valor:
        return base64.b64decode(valor["$b"])
    if isinstance(valor, dict) and "$d" in valor:
        return datetime.fromisoformat(valor["$d"])
    return valor


def crear(db: Session, *, creado_por: str, automatico: bool = False) -> Respaldo:
    volcado = {
        "version": 1,
        "fecha": datetime.now(UTC).isoformat(),
        "tablas": {
            t.name: [{k: _a_json(v) for k, v in fila.items()} for fila in db.execute(select(t)).mappings()]
            for t in _tablas()
        },
    }
    comprimido = zlib.compress(json.dumps(volcado, ensure_ascii=False).encode(), 6)
    cifrado = ecc.cifrar(llavero.publica(db, "respaldo"), comprimido, _CONTEXTO)
    hash_ = ecc.sha256_hex(cifrado)

    directorio = get_settings().directorio_respaldos
    directorio.mkdir(parents=True, exist_ok=True)
    momento = datetime.now(UTC)
    ruta = directorio / f"respaldo-{momento:%Y%m%d-%H%M%S-%f}.vsbak"
    ruta.write_bytes(cifrado)

    respaldo = Respaldo(
        archivo=ruta.name, fecha=momento, tamano=len(cifrado), hash=hash_,
        firma=ecc.firmar(llavero.privada(db, "firma"), hash_.encode()),
        automatico=automatico, creado_por=creado_por,
    )
    db.add(respaldo)
    auditoria.registrar(db, "CREAR_RESPALDO", actor=creado_por,
                        descripcion=f"{'Respaldo automático' if automatico else 'Respaldo manual'} {ruta.name}",
                        commit=False)
    db.commit()
    return respaldo


def verificar(db: Session, respaldo: Respaldo) -> tuple[bool, bytes | None]:
    ruta = get_settings().directorio_respaldos / Path(respaldo.archivo).name
    if not ruta.exists():
        return False, None
    datos = ruta.read_bytes()
    ok = ecc.sha256_hex(datos) == respaldo.hash and ecc.verificar_firma(
        llavero.publica(db, "firma"), respaldo.firma, respaldo.hash.encode())
    return ok, datos


def restaurar(db: Session, respaldo: Respaldo, *, actor: str, ip: str | None) -> None:
    ok, datos = verificar(db, respaldo)
    if not ok or datos is None:
        raise ValueError("El respaldo no existe o su firma no es válida")
    volcado = json.loads(zlib.decompress(ecc.descifrar(llavero.privada(db, "respaldo"), datos, _CONTEXTO)))

    postgres = db.get_bind().dialect.name == "postgresql"
    if postgres:
        db.execute(text("SET LOCAL votoseguro.restaurando = 'on'"))
    tablas = _tablas()
    for tabla in reversed(tablas):
        db.execute(delete(tabla))
    for tabla in tablas:
        filas = [{k: _desde_json(v) for k, v in f.items()} for f in volcado["tablas"].get(tabla.name, [])]
        if filas:
            db.execute(insert(tabla), filas)
        pk = list(tabla.primary_key.columns)
        if postgres and len(pk) == 1 and isinstance(pk[0].type, Integer):
            maximo = db.scalar(select(func.max(pk[0])))
            db.execute(text("SELECT setval(pg_get_serial_sequence(:t, :c), :v, :llamado)"),
                       {"t": tabla.name, "c": pk[0].name, "v": maximo or 1, "llamado": maximo is not None})
    llavero.limpiar_cache()
    # Sin id_usuario: la cuenta que restaura puede no existir en el estado restaurado.
    auditoria.registrar(db, "RESTAURAR_RESPALDO", actor=actor, ip=ip,
                        descripcion=f"Restauración de {respaldo.archivo} (fecha {volcado['fecha']})", commit=False)
    db.commit()
