"""Flujo del votante: identificación -> biometría -> elegibilidad -> votación (Figura 9).

La inscripción (datos, cédula y rostro) se hace antes en la Registraduría (rutas/registraduria.py); aquí el
votante solo presenta su documento y su rostro.
"""
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..crypto import biometria as bio
from ..crypto import ecc, llavero
from ..models import Biometria, Eleccion, Participacion, Persona, Votante
from ..seguridad import DB, VotanteActual, crear_token, ip_cliente, token_flujo
from ..servicios import auditoria, elecciones
from ..servicios.consultas import campo_persona, candidatos_de, edad, eleccion_dict, elecciones_visibles

router = APIRouter(prefix="/api/votante", tags=["votante"])


class Documento(BaseModel):
    tipo_documento: Literal["CC", "CE", "PA", "PPT"]
    documento: str = Field(pattern=r"^[0-9A-Za-z]{5,15}$")


@router.post("/identificacion")
def identificacion(datos: Documento, db: DB, request: Request):
    """Paso 1 (RQF01): ubica al ciudadano inscrito en la Registraduría por su documento."""
    indice = llavero.indice_documento(datos.tipo_documento, datos.documento)
    persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))
    votante = None if persona is None else db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
    inscrito = votante is not None and db.scalar(select(Biometria.id_biometria).where(
        Biometria.id_persona == persona.id_persona, Biometria.estado == "activa")) is not None
    if not inscrito:
        auditoria.registrar(db, "IDENTIFICACION_FALLIDA", actor="votante", ip=ip_cliente(request),
                            resultado="rechazado", descripcion="Documento sin inscripción completa")
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Este documento no está inscrito. Acérquese a la Registraduría para registrar sus "
                            "datos, su cédula y su rostro.")
    if votante.estado_habilitacion == "bloqueado":
        raise HTTPException(status.HTTP_423_LOCKED,
                            "Cuenta bloqueada por intentos biométricos fallidos. Acuda a la Registraduría.")
    token = crear_token(str(votante.id_votante), "flujo", get_settings().minutos_token_flujo, etapa="identificado")
    return {"token": token}


def votante_del_flujo(db, flujo: dict) -> Votante:
    votante = db.get(Votante, int(flujo["sub"]))
    if votante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votante no encontrado")
    if votante.estado_habilitacion == "bloqueado":
        raise HTTPException(status.HTTP_423_LOCKED, "Cuenta bloqueada por intentos biométricos fallidos")
    return votante


class Descriptor(BaseModel):
    descriptor: list[float] = Field(min_length=bio.DIMENSION, max_length=bio.DIMENSION)


def plantilla_de(db, fila: Biometria) -> tuple[list[float], bytes]:
    contexto = f"bio:{fila.id_persona}".encode()
    semilla = ecc.descifrar(llavero.privada(db, "biometria"), fila.semilla, contexto + b":semilla")
    plantilla = bio.desde_bytes(ecc.descifrar(llavero.privada(db, "biometria"), fila.plantilla_biometrica, contexto))
    return plantilla, semilla


def fallo_biometrico(db, votante: Votante, ip: str | None, mensaje: str):
    """Suma un intento fallido, bloquea al llegar al máximo y responde con el error."""
    votante.intentos_biometricos += 1
    restantes = get_settings().max_intentos_biometricos - votante.intentos_biometricos
    if restantes <= 0:
        votante.estado_habilitacion = "bloqueado"
    auditoria.registrar(db, "VERIFICAR_BIOMETRIA", actor="votante", ip=ip, resultado="rechazado", commit=False,
                        descripcion=f"Votante #{votante.id_votante}, intentos restantes: {max(restantes, 0)}")
    db.commit()
    if restantes <= 0:
        raise HTTPException(status.HTTP_423_LOCKED, "Cuenta bloqueada por intentos biométricos fallidos")
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"{mensaje}. Intentos restantes: {restantes}")


@router.post("/biometria")
def biometria(datos: Descriptor, db: DB, request: Request,
              flujo: Annotated[dict, Depends(token_flujo("identificado"))]):
    """Paso 2 (RQF03, RQF27): compara el rostro con la plantilla registrada en la Registraduría."""
    settings = get_settings()
    try:
        descriptor = bio.validar_descriptor(datos.descriptor)
    except bio.DescriptorInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    votante = votante_del_flujo(db, flujo)
    ip = ip_cliente(request)
    existente = db.scalar(select(Biometria).where(Biometria.id_persona == votante.id_persona))
    if existente is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este documento no tiene su rostro registrado")
    plantilla, semilla = plantilla_de(db, existente)
    if bio.distancia(bio.transformar(descriptor, semilla), plantilla) >= settings.umbral_biometrico:
        fallo_biometrico(db, votante, ip, "El rostro no coincide")
    votante.intentos_biometricos = 0
    auditoria.registrar(db, "VERIFICAR_BIOMETRIA", actor="votante", ip=ip, commit=False,
                        descripcion=f"Votante #{votante.id_votante} verificado")
    db.commit()
    token = crear_token(str(votante.id_votante), "flujo", settings.minutos_token_flujo, etapa="verificado")
    return {"verificado": True, "token": token}


@router.get("/elegibilidad")
def elegibilidad(db: DB, request: Request, flujo: Annotated[dict, Depends(token_flujo("verificado"))]):
    """Paso 3 (RQF04): valida requisitos y, si se cumplen, entrega la sesión de votación."""
    votante = db.get(Votante, int(flujo["sub"]))
    persona = votante.persona
    nacimiento = date.fromisoformat(campo_persona(db, persona, "fecha_nacimiento"))
    estado = votante.estado_habilitacion
    requisitos = [
        {"clave": "edad", "texto": "Mayor de 18 años", "ok": edad(nacimiento) >= 18},
        {"clave": "censo", "texto": "Cédula habilitada en el censo", "ok": estado in ("habilitado", "sancionado")},
        {"clave": "sanciones", "texto": "Sin sanciones electorales vigentes", "ok": estado != "sancionado"},
        {"clave": "mesa", "texto": "Inscripción en mesa asignada", "ok": bool(votante.mesa)},
    ]
    habilitado = all(r["ok"] for r in requisitos) and estado == "habilitado"
    auditoria.registrar(db, "VALIDAR_ELEGIBILIDAD", actor="votante", ip=ip_cliente(request),
                        resultado="exito" if habilitado else "rechazado",
                        descripcion=f"Votante #{votante.id_votante}: {'habilitado' if habilitado else 'no habilitado'}")
    respuesta = {"habilitado": habilitado, "requisitos": requisitos,
                 "nombre": campo_persona(db, persona, "nombres")}
    if habilitado:
        respuesta["token"] = crear_token(str(votante.id_votante), "votante", get_settings().minutos_token_votante)
    return respuesta


@router.get("/elecciones")
def listar_elecciones(votante: VotanteActual, db: DB):
    votadas = set(db.scalars(select(Participacion.id_eleccion).where(Participacion.id_votante == votante.id_votante)))
    return [{**eleccion_dict(db, e), "ya_voto": e.id_eleccion in votadas} for e in elecciones_visibles(db)]


def _eleccion(db, id_eleccion: int) -> Eleccion:
    eleccion = db.get(Eleccion, id_eleccion)
    if eleccion is None or eleccion.archivada:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votación no encontrada")
    return eleccion


@router.get("/elecciones/{id_eleccion}/candidatos")
def candidatos(id_eleccion: int, votante: VotanteActual, db: DB):
    eleccion = _eleccion(db, id_eleccion)
    return {"eleccion": eleccion_dict(db, eleccion), "candidatos": candidatos_de(eleccion)}


class NuevoVoto(BaseModel):
    id_eleccion: int
    id_candidato: int


@router.post("/votos", status_code=status.HTTP_201_CREATED)
def votar(datos: NuevoVoto, votante: VotanteActual, db: DB):
    """Emisión del voto (RQF05, RQF10-RQF16): cifrado con la llave pública ECC de la elección."""
    eleccion = _eleccion(db, datos.id_eleccion)
    try:
        comprobante = elecciones.emitir_voto(db, votante, eleccion, datos.id_candidato)
    except elecciones.ErrorVotacion as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    except IntegrityError:
        # Dos envíos simultáneos del mismo votante: la restricción UNIQUE de PARTICIPACION rechaza el segundo.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Usted ya emitió su voto en esta votación") from None
    # El registro de auditoría no identifica al votante ni al candidato.
    auditoria.registrar(db, "EMITIR_VOTO", actor="votante",
                        descripcion=f"Voto cifrado registrado en {eleccion.codigo}")
    return comprobante
