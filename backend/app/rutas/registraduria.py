"""Registraduría (simulada): inscripción del ciudadano, separada del flujo de votación.

Aquí se toman los datos personales, la foto de la cédula (número por OCR y cara impresa) y el rostro, que se
compara con la cédula antes de guardar la plantilla cancelable. El votante, después, solo se identifica con su
documento y su rostro.
"""
import json
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from ..config import get_settings
from ..crypto import biometria as bio
from ..crypto import ecc, llavero
from ..models import Biometria, DocumentoIdentidad, Persona, Votante
from ..seguridad import DB, crear_token, ip_cliente, token_flujo
from ..servicios import auditoria, documento
from ..servicios.consultas import campo_persona, cifrar_campo, edad, normalizar
from .votante import Descriptor, fallo_biometrico, plantilla_de, votante_del_flujo

router = APIRouter(prefix="/api/registraduria", tags=["registraduría"])

TIPOS_CEDULA = {"image/jpeg", "image/png", "image/webp"}


class DatosIdentidad(BaseModel):
    tipo_documento: Literal["CC", "CE", "PA", "PPT"]
    documento: str = Field(pattern=r"^[0-9A-Za-z]{5,15}$")
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    fecha_nacimiento: date
    correo: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=150)
    telefono: str | None = Field(default=None, pattern=r"^[0-9+ ]{7,20}$")

    @field_validator("fecha_nacimiento")
    @classmethod
    def no_futura(cls, v: date) -> date:
        if v >= date.today() or v.year < 1900:
            raise ValueError("Fecha de nacimiento inválida")
        return v


@router.post("/inscripcion")
def inscripcion(datos: DatosIdentidad, db: DB, request: Request):
    """Inscripción, paso 1 (RQF01): registra los datos cifrados. Si el documento ya existe sin rostro registrado
    (inscripción a medias), permite retomarla siempre que los datos coincidan."""
    ip = ip_cliente(request)
    indice = llavero.indice_documento(datos.tipo_documento, datos.documento)
    persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))

    if persona is None:
        persona = Persona(
            tipo_documento=datos.tipo_documento, documento_indice=indice,
            documento=cifrar_campo(db, indice, "documento", datos.documento),
            nombres=cifrar_campo(db, indice, "nombres", datos.nombres.strip()),
            apellidos=cifrar_campo(db, indice, "apellidos", datos.apellidos.strip()),
            correo=cifrar_campo(db, indice, "correo", datos.correo.strip()),
            telefono=cifrar_campo(db, indice, "telefono", datos.telefono),
            fecha_nacimiento=cifrar_campo(db, indice, "fecha_nacimiento", datos.fecha_nacimiento.isoformat()),
        )
        db.add(persona)
        db.flush()
        mayor = edad(datos.fecha_nacimiento) >= 18
        votante = Votante(
            id_persona=persona.id_persona,
            estado_habilitacion="habilitado" if mayor else "no_habilitado",
            fecha_habilitacion=datetime.now(UTC) if mayor else None,
            mesa="Mesa virtual 01",
        )
        db.add(votante)
        auditoria.registrar(db, "REGISTRAR_VOTANTE", actor="registraduria", ip=ip,
                            descripcion=f"Nuevo votante #{persona.id_persona}", commit=False)
        db.commit()
    else:
        votante = db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
        if votante is None or db.scalar(select(Biometria.id_biometria).where(
                Biometria.id_persona == persona.id_persona, Biometria.estado == "activa")) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este documento ya está inscrito. Puede ir a votar.")
        coincide = (
            normalizar(campo_persona(db, persona, "nombres")) == normalizar(datos.nombres)
            and normalizar(campo_persona(db, persona, "apellidos")) == normalizar(datos.apellidos)
            and campo_persona(db, persona, "fecha_nacimiento") == datos.fecha_nacimiento.isoformat()
        )
        if not coincide:
            auditoria.registrar(db, "INSCRIPCION_FALLIDA", actor="registraduria", ip=ip, resultado="rechazado",
                                descripcion="Datos que no coinciden con una inscripción en curso")
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Este documento tiene una inscripción en curso con otros datos")

    if votante.estado_habilitacion == "bloqueado":
        raise HTTPException(status.HTTP_423_LOCKED, "La inscripción de este documento está bloqueada")
    token = crear_token(str(votante.id_votante), "flujo", get_settings().minutos_token_flujo, etapa="inscripcion")
    return {"token": token}


@router.post("/cedula")
async def cedula(db: DB, request: Request, flujo: Annotated[dict, Depends(token_flujo("inscripcion"))],
                 imagen: Annotated[UploadFile, File()], descriptor: Annotated[str, Form(max_length=8000)]):
    """Inscripción, paso 2: foto de la cédula. El servidor lee el número con OCR y guarda la imagen y el
    descriptor de la cara impresa cifrados, para compararla después con el rostro en vivo."""
    settings = get_settings()
    votante = votante_del_flujo(db, flujo)
    if imagen.content_type not in TIPOS_CEDULA:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La imagen debe ser JPG, PNG o WEBP")
    maximo = settings.max_mb_cedula * 1024 * 1024
    datos = await imagen.read(maximo + 1)
    if len(datos) > maximo:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"La imagen supera {settings.max_mb_cedula} MB")
    try:
        documento.abrir(datos)
        cara = bio.validar_descriptor(json.loads(descriptor))
    except documento.ImagenInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "No se pudo procesar el rostro de la cédula") from None

    persona = votante.persona
    ip = ip_cliente(request)
    if settings.verificar_numero_cedula:
        try:
            leidos = documento.leer_numeros(datos)
        except documento.OcrNoDisponible as e:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
        if not documento.coincide(campo_persona(db, persona, "documento"), leidos):
            auditoria.registrar(db, "VERIFICAR_DOCUMENTO", actor="registraduria", ip=ip, resultado="rechazado",
                                descripcion=f"Votante #{votante.id_votante}: el número de la cédula no coincide")
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "No se pudo leer el número del documento en la foto, o no coincide con el "
                                "registrado. Tome la foto de frente, sin reflejos y con buena luz.")

    fila = db.scalar(select(DocumentoIdentidad).where(DocumentoIdentidad.id_persona == persona.id_persona))
    if fila is None:
        fila = DocumentoIdentidad(id_persona=persona.id_persona)
        db.add(fila)
    documento.guardar(db, fila, datos, imagen.content_type, cara)
    fila.estado = "pendiente"
    auditoria.registrar(db, "VERIFICAR_DOCUMENTO", actor="registraduria", ip=ip, commit=False,
                        descripcion=f"Votante #{votante.id_votante}: cédula recibida")
    db.commit()
    token = crear_token(str(votante.id_votante), "flujo", settings.minutos_token_flujo, etapa="cedula")
    return {"token": token}


@router.post("/rostro")
def rostro(datos: Descriptor, db: DB, request: Request, flujo: Annotated[dict, Depends(token_flujo("cedula"))]):
    """Inscripción, paso 3 (RQF02, RQF27): el rostro en vivo debe coincidir con la foto de la cédula; luego se
    guarda la plantilla cancelable y la inscripción queda completa."""
    settings = get_settings()
    try:
        descriptor = bio.validar_descriptor(datos.descriptor)
    except bio.DescriptorInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    votante = votante_del_flujo(db, flujo)
    ip = ip_cliente(request)
    if db.scalar(select(Biometria.id_biometria).where(Biometria.id_persona == votante.id_persona)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este documento ya está inscrito")
    cedula_fila = db.scalar(select(DocumentoIdentidad).where(DocumentoIdentidad.id_persona == votante.id_persona))
    if cedula_fila is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Primero debe presentar la foto de la cédula")

    _, cara_cedula = documento.descifrar(db, cedula_fila)
    if bio.distancia(descriptor, cara_cedula) >= settings.umbral_cedula:
        fallo_biometrico(db, votante, ip, "El rostro no coincide con la foto de la cédula")
    # Evita que un mismo rostro se registre con dos documentos distintos (Figura 10).
    for otra in db.scalars(select(Biometria).where(Biometria.estado == "activa")):
        plantilla, semilla = plantilla_de(db, otra)
        if bio.distancia(bio.transformar(descriptor, semilla), plantilla) < settings.umbral_biometrico:
            auditoria.registrar(db, "BIOMETRIA_DUPLICADA", actor="registraduria", ip=ip, resultado="rechazado",
                                descripcion=f"Votante #{votante.id_votante} coincide con persona #{otra.id_persona}")
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Este rostro ya está registrado con otro documento de identidad")

    semilla = bio.nueva_semilla()
    contexto = f"bio:{votante.id_persona}".encode()
    pub = llavero.publica(db, "biometria")
    db.add(Biometria(
        id_persona=votante.id_persona,
        plantilla_biometrica=ecc.cifrar(pub, bio.a_bytes(bio.transformar(descriptor, semilla)), contexto),
        semilla=ecc.cifrar(pub, semilla, contexto + b":semilla"),
    ))
    cedula_fila.estado = "verificado"
    votante.intentos_biometricos = 0
    auditoria.registrar(db, "ENROLAR_BIOMETRIA", actor="registraduria", ip=ip, commit=False,
                        descripcion=f"Plantilla cancelable registrada para votante #{votante.id_votante} "
                                    "(rostro verificado contra la cédula)")
    db.commit()
    return {"inscrito": True, "nombre": campo_persona(db, votante.persona, "nombres"),
            "habilitado": votante.estado_habilitacion == "habilitado"}
