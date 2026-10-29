"""Ciclo de vida de las elecciones, emisión del voto y escrutinio."""
import json
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_master_key
from ..crypto import ecc, llavero
from ..models import Eleccion, InscripcionCandidato, Participacion, Resultado, Votante, Voto
from . import auditoria

_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para evitar confusiones al leerlo


class ErrorVotacion(Exception):
    pass


def ahora() -> datetime:
    return datetime.now(UTC)


def _contexto_eleccion(eleccion: Eleccion) -> bytes:
    return f"eleccion:{eleccion.codigo}".encode()


def nuevo_codigo(db: Session, anio: int) -> str:
    n = db.scalar(select(func.count()).select_from(Eleccion).where(Eleccion.codigo.like(f"EL-{anio}-%"))) or 0
    return f"EL-{anio}-{n + 1:03d}"


def crear(db: Session, *, nombre: str, descripcion: str | None, tipo: str,
          fecha_inicio: datetime, fecha_fin: datetime) -> Eleccion:
    privada = ecc.generar_par()
    eleccion = Eleccion(
        codigo=nuevo_codigo(db, fecha_inicio.year), nombre=nombre, descripcion=descripcion, tipo=tipo,
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, estado="programada",
        clave_publica=ecc.exportar_publica(privada.public_key()), clave_privada=b"",
    )
    eleccion.clave_privada = ecc.envolver_privada(privada, get_master_key(), _contexto_eleccion(eleccion))
    db.add(eleccion)
    db.flush()
    return eleccion


def estado_calculado(eleccion: Eleccion, momento: datetime | None = None) -> str:
    if eleccion.estado == "finalizada":
        return "finalizada"
    momento = momento or ahora()
    if momento < eleccion.fecha_inicio:
        return "programada"
    if momento < eleccion.fecha_fin:
        return "activa"
    return "finalizada"


def sincronizar_estados(db: Session) -> list[str]:
    """Abre las elecciones cuya hora de inicio llegó y cierra (con escrutinio) las vencidas (RQF26)."""
    cambios = []
    for eleccion in db.scalars(select(Eleccion).where(Eleccion.estado != "finalizada")):
        nuevo = estado_calculado(eleccion)
        if nuevo == eleccion.estado:
            continue
        if nuevo == "activa":
            eleccion.estado = "activa"
            auditoria.registrar(db, "ABRIR_ELECCION", descripcion=f"Apertura automática de {eleccion.codigo}",
                                commit=False)
        else:
            cerrar(db, eleccion, actor="sistema", automatico=True)
        cambios.append(f"{eleccion.codigo}:{nuevo}")
    db.commit()
    return cambios


def emitir_voto(db: Session, votante: Votante, eleccion: Eleccion, id_candidato: int) -> dict:
    """Registra la participación y guarda el voto cifrado, en una sola transacción."""
    if estado_calculado(eleccion) != "activa":
        raise ErrorVotacion("La votación no está abierta")
    inscripcion = db.scalar(select(InscripcionCandidato).where(
        InscripcionCandidato.id_eleccion == eleccion.id_eleccion,
        InscripcionCandidato.id_candidato == id_candidato,
        InscripcionCandidato.estado == "inscrito",
    ))
    if inscripcion is None:
        raise ErrorVotacion("El candidato no pertenece a esta votación")
    ya_voto = db.scalar(select(Participacion.id_participacion).where(
        Participacion.id_votante == votante.id_votante, Participacion.id_eleccion == eleccion.id_eleccion,
    ))
    if ya_voto:
        raise ErrorVotacion("Usted ya emitió su voto en esta votación")

    momento = ahora()
    contenido = json.dumps({"c": id_candidato, "r": secrets.token_hex(16)}).encode()  # r: relleno aleatorio
    cifrado = ecc.cifrar(ecc.importar_publica(eleccion.clave_publica), contenido, _contexto_eleccion(eleccion))
    codigo = f"VS-{momento.year}-" + "".join(secrets.choice(_ALFABETO) for _ in range(8))
    hash_voto = ecc.sha256_hex(cifrado)
    codigo_hash = ecc.sha256_hex(codigo.encode())
    firma = ecc.firmar(llavero.privada(db, "firma"), _mensaje_firma(eleccion.codigo, hash_voto, codigo_hash))

    db.add(Participacion(id_votante=votante.id_votante, id_eleccion=eleccion.id_eleccion, fecha_hora=momento))
    db.add(Voto(
        id_voto=str(uuid.uuid4()), id_eleccion=eleccion.id_eleccion, voto_cifrado=cifrado,
        fecha_hora=momento.replace(minute=0, second=0, microsecond=0),
        hash_voto=hash_voto, codigo_hash=codigo_hash, firma=firma,
    ))
    db.commit()
    return {"codigo": codigo, "hash_voto": hash_voto, "eleccion": eleccion.nombre, "fecha": momento.isoformat()}


def _mensaje_firma(codigo_eleccion: str, hash_voto: str, codigo_hash: str) -> bytes:
    return f"{codigo_eleccion}|{hash_voto}|{codigo_hash}".encode()


def verificar_comprobante(db: Session, codigo: str) -> dict:
    """Verificabilidad: confirma que el voto existe y está intacto, sin revelar el candidato."""
    voto = db.scalar(select(Voto).where(Voto.codigo_hash == ecc.sha256_hex(codigo.strip().upper().encode())))
    if voto is None:
        return {"encontrado": False}
    eleccion = db.get(Eleccion, voto.id_eleccion)
    intacto = ecc.sha256_hex(voto.voto_cifrado) == voto.hash_voto
    firma_ok = ecc.verificar_firma(
        llavero.publica(db, "firma"), voto.firma, _mensaje_firma(eleccion.codigo, voto.hash_voto, voto.codigo_hash)
    )
    return {
        "encontrado": True, "eleccion": eleccion.nombre, "codigo_eleccion": eleccion.codigo,
        "hora_aproximada": voto.fecha_hora.isoformat(), "hash_voto": voto.hash_voto,
        "integro": intacto, "firma_valida": firma_ok, "escrutado": eleccion.estado == "finalizada",
    }


def cerrar(db: Session, eleccion: Eleccion, *, actor: str, id_usuario: int | None = None,
           automatico: bool = False, ip: str | None = None) -> None:
    """Cierra la elección y hace el escrutinio: descifra cada voto con la llave privada de la elección."""
    if eleccion.estado == "finalizada":
        raise ErrorVotacion("La votación ya está cerrada")
    momento = ahora()
    eleccion.estado = "finalizada"
    eleccion.fecha_cierre = momento
    if momento < eleccion.fecha_fin:
        eleccion.fecha_fin = momento

    privada = ecc.desenvolver_privada(eleccion.clave_privada, get_master_key(), _contexto_eleccion(eleccion))
    firma_pub = llavero.publica(db, "firma")
    conteo = {i.id_candidato: 0 for i in eleccion.inscripciones if i.estado == "inscrito"}
    invalidos = 0
    votos = db.scalars(select(Voto).where(Voto.id_eleccion == eleccion.id_eleccion)).all()
    for voto in votos:
        try:
            ok = ecc.sha256_hex(voto.voto_cifrado) == voto.hash_voto and ecc.verificar_firma(
                firma_pub, voto.firma, _mensaje_firma(eleccion.codigo, voto.hash_voto, voto.codigo_hash))
            candidato = json.loads(ecc.descifrar(privada, voto.voto_cifrado, _contexto_eleccion(eleccion)))["c"]
            if not ok or candidato not in conteo:
                raise ValueError
            conteo[candidato] += 1
        except Exception:
            invalidos += 1

    participaciones = db.scalar(
        select(func.count()).select_from(Participacion).where(Participacion.id_eleccion == eleccion.id_eleccion)
    )
    db.query(Resultado).filter(Resultado.id_eleccion == eleccion.id_eleccion).delete()
    for id_candidato, votos_candidato in conteo.items():
        db.add(Resultado(id_eleccion=eleccion.id_eleccion, id_candidato=id_candidato, votos=votos_candidato))
    eleccion.votos_escrutados = sum(conteo.values())
    # Coincidencia voto-registro (indicador de la Tabla 1): cada participación debe tener su voto válido.
    eleccion.integridad_ok = invalidos == 0 and len(votos) == participaciones

    auditoria.registrar(
        db, "CERRAR_ELECCION", actor=actor, id_usuario=id_usuario, ip=ip,
        descripcion=(f"{'Cierre automático' if automatico else 'Cierre manual'} de {eleccion.codigo}. "
                     f"Votos: {len(votos)}, participaciones: {participaciones}, inválidos: {invalidos}"),
        resultado="exito" if eleccion.integridad_ok else "alerta", commit=False,
    )
    db.flush()
