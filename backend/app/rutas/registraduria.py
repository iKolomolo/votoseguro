"""Registraduría (simulada): inscripción del ciudadano, separada del flujo de votación.

Aquí se toman la autorización, los datos personales, la foto de la cédula (número por OCR y cara impresa) y el
rostro, que se compara con la cédula antes de guardar la plantilla cancelable. La inscripción es atómica: nada se
guarda hasta el último paso (ver servicios/inscripcion.py); si no se completa, se descarta.
"""
import json
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from ..config import get_settings
from ..crypto import biometria as bio
from ..seguridad import DB, crear_token, ip_cliente, token_flujo
from ..servicios import auditoria, autorizacion, documento, inscripcion, limites, retencion, vida
from ..servicios.consultas import EDAD_MINIMA, campo_persona, es_menor
from .votante import PRUEBA_FALLIDA, Descriptor

router = APIRouter(prefix="/api/registraduria", tags=["registraduría"])

TIPOS_CEDULA = {"image/jpeg", "image/png", "image/webp"}


def _exigir_piloto_abierto() -> None:
    if retencion.piloto_terminado():
        raise HTTPException(status.HTTP_410_GONE, f"El piloto terminó el {get_settings().fin_piloto:%d/%m/%Y}: "
                                                  "ya no se reciben inscripciones.")


def _rechazo(e: inscripcion.InscripcionRechazada) -> HTTPException:
    return HTTPException(e.estado_http, str(e))


def _token(db, estado: dict, etapa: str) -> str:
    """Token del paso siguiente con el estado sellado. Vence cuando vence la inscripción, no se renueva."""
    return crear_token("inscripcion", "flujo", inscripcion.minutos_restantes(estado), etapa=etapa,
                       biometria=estado["autorizacion"]["acepto_biometria"], sello=inscripcion.sellar(db, estado),
                       retos=vida.nuevos_retos())


def _estado(db, flujo: dict) -> dict:
    try:
        return inscripcion.abrir(db, flujo.get("sello", ""))
    except inscripcion.InscripcionRechazada as e:
        raise _rechazo(e) from None


class AutorizacionAceptada(BaseModel):
    """Lo que el titular aceptó en la pantalla de autorización: versión y huella del texto, y las dos casillas."""
    version: str = Field(max_length=10)
    hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    acepto_datos: bool
    acepto_biometria: bool


class DatosIdentidad(BaseModel):
    tipo_documento: Literal["CC", "CE", "PA", "PPT"]
    documento: str = Field(pattern=r"^[0-9A-Za-z]{5,15}$")
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    fecha_nacimiento: date
    correo: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=150)
    telefono: str | None = Field(default=None, pattern=r"^[0-9+ ]{7,20}$")
    autorizacion: AutorizacionAceptada

    @field_validator("fecha_nacimiento")
    @classmethod
    def no_futura(cls, v: date) -> date:
        if v >= date.today() or v.year < 1900:
            raise ValueError("Fecha de nacimiento inválida")
        return v


@router.post("/inscripcion", dependencies=[limites.por_ip("inscripcion", "limite_inscripcion_ip", 3600)])
def inscripcion_datos(datos: DatosIdentidad, db: DB, request: Request):
    """Inscripción, paso 1 (RQF01): valida la autorización y los datos. No guarda nada todavía: los datos viajan
    sellados en el token hasta que la inscripción termine."""
    _exigir_piloto_abierto()
    aceptada = datos.autorizacion
    try:
        autorizacion.validar(aceptada.version, aceptada.hash, aceptada.acepto_datos, aceptada.acepto_biometria)
    except autorizacion.AutorizacionInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    if es_menor(datos.fecha_nacimiento):
        # Un menor no puede votar y sus datos no se recogen (Ley 1581 art. 7): se rechaza antes de pedir la cédula.
        # La auditoría no guarda el documento ni la fecha, solo que hubo un rechazo por edad.
        auditoria.registrar(db, "INSCRIPCION_RECHAZADA", actor="registraduria", ip=ip_cliente(request),
                            resultado="rechazado", descripcion="Menor de edad")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Debe tener al menos {EDAD_MINIMA} años cumplidos para inscribirse como votante.")
    personales = datos.model_dump(mode="json", exclude={"autorizacion"})
    estado = inscripcion.nuevo_estado(personales, aceptada.model_dump())
    # No se revisa aquí si el documento ya está inscrito: decirlo a quien solo escribe un número revelaría quién
    # participa. Se revisa en el paso de la cédula, cuando ya demostró tenerla.
    return {"token": _token(db, estado, "inscripcion"), "minutos": get_settings().minutos_inscripcion}


@router.post("/cedula")
async def cedula(db: DB, request: Request,
                 flujo: Annotated[dict, Depends(token_flujo("inscripcion", "cedula"))],
                 imagen: Annotated[UploadFile, File()],
                 reverso: Annotated[UploadFile, File()],
                 descriptor: Annotated[str | None, Form(max_length=8000)] = None):
    """Inscripción, paso 2: fotos de las dos caras de la cédula (se puede repetir). El servidor las lee con OCR en
    memoria y exige que el número, los nombres, los apellidos y la fecha de nacimiento escritos coincidan con la
    cédula. NO guarda las imágenes (Decreto 1377 art. 4): solo sus huellas SHA-256. Con autorización biométrica, el
    descriptor de la cara impresa sigue sellado en el token hasta comparar el rostro. Sin ella no se trata ningún
    rostro y la inscripción se confirma aquí (voto presencial)."""
    _exigir_piloto_abierto()
    settings = get_settings()
    estado = _estado(db, flujo)
    maximo = settings.max_mb_cedula * 1024 * 1024
    caras = []
    for archivo, nombre in ((imagen, "del frente"), (reverso, "del reverso")):
        if archivo.content_type not in TIPOS_CEDULA:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"La foto {nombre} debe ser JPG, PNG o WEBP")
        contenido = await archivo.read(maximo + 1)
        if len(contenido) > maximo:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                f"La foto {nombre} supera {settings.max_mb_cedula} MB")
        caras.append(contenido)
    datos, datos_reverso = caras
    con_biometria = bool(estado["autorizacion"]["acepto_biometria"])
    try:
        documento.abrir(datos)
        documento.abrir(datos_reverso)
        # Sin autorización biométrica, el descriptor que llegue se ignora: no se procesa ni se guarda.
        cara = bio.validar_descriptor(json.loads(descriptor or "null")) if con_biometria else None
    except documento.ImagenInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "No se pudo procesar el rostro de la cédula") from None

    ip = ip_cliente(request)
    if settings.verificar_numero_cedula:
        try:
            # El OCR tarda (más aún con la CPU del plan gratuito): corre en otro hilo para que el servidor siga
            # respondiendo, incluida la revisión de salud de Render, que si no lo da por caído y lo reinicia.
            texto = await run_in_threadpool(documento.leer_cedula, datos, datos_reverso)
        except documento.OcrNoDisponible as e:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
        resultado = documento.verificar(texto, estado["datos"])
        del texto
        if fallidos := [documento.CAMPOS[campo] for campo, ok in resultado.items() if not ok]:
            auditoria.registrar(db, "VERIFICAR_DOCUMENTO", actor="registraduria", ip=ip, resultado="rechazado",
                                descripcion=f"Inscripción en curso: la cédula no confirma {', '.join(fallidos)}")
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"La cédula no confirma: {', '.join(fallidos)}. Revise que los haya escrito "
                                "exactamente como aparecen en su cédula y tome las fotos de frente, sin reflejos y "
                                "con buena luz.")

    try:
        inscripcion.revisar_documento(db, estado["indice"])
    except inscripcion.InscripcionRechazada as e:
        raise _rechazo(e) from None
    estado = inscripcion.con_cedula(estado, datos, datos_reverso,
                                    True if settings.verificar_numero_cedula else None, cara)
    del datos, datos_reverso  # las imágenes no salen de esta petición
    if not con_biometria:
        try:
            persona, votante = inscripcion.confirmar(db, estado, None, None, ip)
        except inscripcion.InscripcionRechazada as e:
            raise _rechazo(e) from None
        return {"completa": True, "biometria": False, "nombre": campo_persona(db, persona, "nombres"),
                "habilitado": votante.estado_habilitacion == "habilitado"}
    return {"completa": False, "biometria": True, "token": _token(db, estado, "cedula")}


@router.post("/rostro")
def rostro(datos: Descriptor, db: DB, request: Request, flujo: Annotated[dict, Depends(token_flujo("cedula"))]):
    """Inscripción, paso 3 (RQF02, RQF27): el rostro en vivo debe coincidir con la foto de la cédula. Si coincide,
    se confirma toda la inscripción en una sola transacción. La plantilla se conserva cifrada hasta el fin del
    piloto o hasta que el titular la revoque."""
    _exigir_piloto_abierto()
    settings = get_settings()
    estado = _estado(db, flujo)
    cara_cedula = inscripcion.cara_de(estado)
    if not estado["autorizacion"]["acepto_biometria"] or cara_cedula is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizó el tratamiento de sus datos biométricos")
    try:
        descriptor = bio.validar_descriptor(datos.descriptor)
    except bio.DescriptorInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    ip = ip_cliente(request)
    try:
        vida.verificar(flujo.get("retos", []), datos.vida)
    except vida.PruebaFallida as e:
        restantes = inscripcion.registrar_fallo(db, estado["id"])
        auditoria.registrar(db, "PRUEBA_VIDA", actor="registraduria", ip=ip, resultado="rechazado",
                            descripcion=f"Inscripción en curso: {e}; intentos restantes: {restantes}")
        if restantes == 0:
            raise HTTPException(status.HTTP_423_LOCKED, "Se agotaron los intentos: la inscripción se canceló y no "
                                                        "se guardó ningún dato. Empiece de nuevo.") from None
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"{PRUEBA_FALLIDA} Intentos restantes: {restantes}") from None

    distancia = bio.distancia(descriptor, cara_cedula)
    if distancia >= settings.umbral_cedula:
        restantes = inscripcion.registrar_fallo(db, estado["id"])
        auditoria.registrar(db, "VERIFICAR_BIOMETRIA", actor="registraduria", ip=ip, resultado="rechazado",
                            descripcion=f"Inscripción en curso: rostro distinto a la cédula; intentos restantes: {restantes}")
        if restantes == 0:
            raise HTTPException(status.HTTP_423_LOCKED, "Se agotaron los intentos: la inscripción se canceló y no "
                                                        "se guardó ningún dato. Empiece de nuevo.")
        # 422 y no 401: el 401 se reserva para la inscripción vencida, que obliga a empezar de nuevo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"El rostro no coincide con la foto de la cédula. Intentos restantes: {restantes}")
    otra = inscripcion.rostro_duplicado(db, descriptor, estado["indice"])
    if otra is not None:
        auditoria.registrar(db, "BIOMETRIA_DUPLICADA", actor="registraduria", ip=ip, resultado="rechazado",
                            descripcion=f"Inscripción en curso: el rostro coincide con persona #{otra}")
        raise HTTPException(status.HTTP_409_CONFLICT, "Este rostro ya está registrado con otro documento de identidad")

    try:
        persona, votante = inscripcion.confirmar(db, estado, descriptor, distancia, ip)
    except inscripcion.InscripcionRechazada as e:
        raise _rechazo(e) from None
    return {"inscrito": True, "nombre": campo_persona(db, persona, "nombres"),
            "habilitado": votante.estado_habilitacion == "habilitado",
            "plantilla_hasta": settings.fin_piloto.isoformat()}
