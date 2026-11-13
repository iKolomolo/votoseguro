"""Flujo del votante: identificación -> biometría -> elegibilidad -> votación (Figura 9).

La inscripción (datos, cédula y rostro) se hace antes en la Registraduría (rutas/registraduria.py); aquí el
votante solo presenta su documento y su rostro.
"""
import base64
import secrets
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..crypto import biometria as bio
from ..crypto import ecc, llavero
from ..models import Biometria, Eleccion, Participacion, Persona, VerificacionDocumento, Votante
from ..seguridad import DB, VotanteActual, crear_token, ip_cliente, token_flujo
from ..servicios import auditoria, autorizacion, elecciones, limites, retencion, vida
from ..servicios.consultas import campo_persona, candidatos_de, edad, eleccion_dict, elecciones_visibles

router = APIRouter(prefix="/api/votante", tags=["votante"])


class Documento(BaseModel):
    tipo_documento: Literal["CC", "CE", "PA", "PPT"]
    documento: str = Field(pattern=r"^[0-9A-Za-z]{5,15}$")


# ---------- Identificación y verificación facial ----------
# Para no revelar quién participa, la identificación responde IGUAL esté o no inscrito el documento: siempre entrega
# un token, que lleva el documento sellado (cifrado con ECIES, de longitud fija), así que ni el token delata nada.
# Solo al verificar el rostro se sabe si coincide; si no, la respuesta es la misma para un documento no inscrito,
# sin rostro registrado, bloqueado o con un rostro distinto. Los intentos fallidos se cuentan por documento (exista o
# no) y, al llegar al máximo, el documento se pausa unos minutos en vez de bloquearse: así nadie puede bloquear la
# cuenta de otra persona solo con conocer su número.

_CONTEXTO_IDENTIFICACION = b"identificacion-v1"
NO_VERIFICADO = ("No pudimos verificar su identidad. Revise el número de documento y que su rostro se vea completo y "
                 "con buena luz. Si no se ha inscrito o revocó el uso de su rostro, inscríbase en la Registraduría.")


@router.post("/identificacion",
             dependencies=[limites.por_ip("identificacion", "limite_identificacion_ip", 900)])
def identificacion(datos: Documento, db: DB):
    """Paso 1 (RQF01): recibe el documento. No consulta si está inscrito: eso se sabe al verificar el rostro."""
    indice = llavero.indice_documento(datos.tipo_documento, datos.documento)
    sello = ecc.cifrar(llavero.publica(db, "documento"), indice.encode(), _CONTEXTO_IDENTIFICACION)
    token = crear_token("identificacion", "flujo", get_settings().minutos_token_flujo, etapa="identificado",
                        doc=base64.urlsafe_b64encode(sello).decode(), retos=vida.nuevos_retos())
    return {"token": token}


def _indice_del_token(db, flujo: dict) -> str:
    try:
        sello = base64.urlsafe_b64decode(flujo["doc"])
        return ecc.descifrar(llavero.privada(db, "documento"), sello, _CONTEXTO_IDENTIFICACION).decode()
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión no es válida. Empiece de nuevo.") from None


def votante_del_flujo(db, flujo: dict) -> Votante:
    votante = db.get(Votante, int(flujo["sub"]))
    if votante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votante no encontrado")
    if votante.estado_habilitacion == "bloqueado":
        raise HTTPException(status.HTTP_423_LOCKED, "Cuenta bloqueada")
    return votante


class Descriptor(BaseModel):
    descriptor: list[float] = Field(min_length=bio.DIMENSION, max_length=bio.DIMENSION)
    # Prueba de vida: puntos faciales de frente y de cada reto pedido en el token (servicios/vida.py).
    vida: dict | None = None


PRUEBA_FALLIDA = ("No se comprobó la prueba de vida. Siga las instrucciones de la pantalla: mire de frente y haga "
                  "cada movimiento cuando se le pida.")


def plantilla_de(db, fila: Biometria) -> tuple[list[float], bytes]:
    contexto = f"bio:{fila.id_persona}".encode()
    semilla = ecc.descifrar(llavero.privada(db, "biometria"), fila.semilla, contexto + b":semilla")
    plantilla = bio.desde_bytes(ecc.descifrar(llavero.privada(db, "biometria"), fila.plantilla_biometrica, contexto))
    return plantilla, semilla


_senuelo: Biometria | None = None


def _plantilla_senuelo(db) -> tuple[list[float], bytes]:
    """Plantilla aleatoria para documentos sin rostro registrado: se descifra y compara igual que una real, para que
    el tiempo de respuesta no delate si el documento está inscrito."""
    global _senuelo
    if _senuelo is None:
        semilla = bio.nueva_semilla()
        aleatorio = [secrets.SystemRandom().uniform(-1, 1) for _ in range(bio.DIMENSION)]
        publica = llavero.publica(db, "biometria")
        _senuelo = Biometria(id_persona=0, semilla=ecc.cifrar(publica, semilla, b"bio:0:semilla"),
                             plantilla_biometrica=ecc.cifrar(publica, bio.a_bytes(bio.transformar(aleatorio, semilla)),
                                                             b"bio:0"))
    return plantilla_de(db, _senuelo)


@router.post("/biometria")
def biometria(datos: Descriptor, db: DB, request: Request,
              flujo: Annotated[dict, Depends(token_flujo("identificado"))]):
    """Paso 2 (RQF03, RQF27): compara el rostro con la plantilla registrada en la Registraduría."""
    settings = get_settings()
    try:
        descriptor = bio.validar_descriptor(datos.descriptor)
    except bio.DescriptorInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    indice = _indice_del_token(db, flujo)
    clave = f"biometria:{indice}"
    if limites.contador(db, clave) >= settings.max_intentos_biometricos:
        espera = limites.en_minutos(limites.segundos_restantes(db, clave))
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Hubo demasiados intentos fallidos con este documento. Por seguridad, espere {espera} y "
                            "vuelva a intentarlo.")
    ip = ip_cliente(request)
    try:
        vida.verificar(flujo.get("retos", []), datos.vida)
    except vida.PruebaFallida as e:
        usados = limites.sumar(db, clave, settings.minutos_pausa_biometrica * 60)
        auditoria.registrar(db, "PRUEBA_VIDA", actor="votante", ip=ip, resultado="rechazado", commit=False,
                            descripcion=f"Verificación para votar: {e} (intento {usados})")
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, PRUEBA_FALLIDA) from None

    persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))
    votante = None if persona is None else db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
    fila = None if votante is None else db.scalar(
        select(Biometria).where(Biometria.id_persona == persona.id_persona, Biometria.estado == "activa"))
    plantilla, semilla = plantilla_de(db, fila) if fila is not None else _plantilla_senuelo(db)
    coincide = bio.distancia(bio.transformar(descriptor, semilla), plantilla) < settings.umbral_biometrico
    if not coincide or fila is None:
        usados = limites.sumar(db, clave, settings.minutos_pausa_biometrica * 60)
        auditoria.registrar(db, "VERIFICAR_BIOMETRIA", actor="votante", ip=ip, resultado="rechazado", commit=False,
                            descripcion=(f"Votante #{votante.id_votante}: el rostro no coincide" if fila is not None
                                         else "Documento sin rostro registrado") + f" (intento {usados})")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            f"{NO_VERIFICADO} Después de {settings.max_intentos_biometricos} intentos fallidos "
                            f"deberá esperar {settings.minutos_pausa_biometrica} minutos.")
    limites.reiniciar(db, clave)
    if votante.estado_habilitacion == "bloqueado":
        # Solo se informa a quien demostró ser el titular.
        db.commit()
        raise HTTPException(status.HTTP_423_LOCKED,
                            f"Su inscripción está bloqueada. Escríbanos a {settings.correo_privacidad} para revisarla.")
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


# ---------- Derechos del titular sobre su plantilla (Ley 1581 art. 8) ----------
# Se usa el mismo token "verificado" que entrega la verificación facial: solo el titular, después de probar
# su identidad con documento y rostro, puede consultar o revocar su propia plantilla.

@router.get("/mis-datos")
def mis_datos(db: DB, flujo: Annotated[dict, Depends(token_flujo("verificado"))]):
    """Qué datos biométricos se conservan del titular y hasta cuándo (Ley 1581 art. 8 lit. a y d)."""
    votante = votante_del_flujo(db, flujo)
    persona = votante.persona
    plantilla = db.scalar(select(Biometria).where(Biometria.id_persona == persona.id_persona))
    cedula = db.scalar(select(VerificacionDocumento).where(VerificacionDocumento.id_persona == persona.id_persona))
    return {
        "nombre": f"{campo_persona(db, persona, 'nombres')} {campo_persona(db, persona, 'apellidos')}",
        "tipo_documento": persona.tipo_documento,
        "documento": campo_persona(db, persona, "documento"),
        "correo": campo_persona(db, persona, "correo"),
        "inscrito_el": persona.fecha_registro.isoformat() if persona.fecha_registro else None,
        "plantilla": None if plantilla is None else {
            "registrada_el": plantilla.fecha_registro.isoformat() if plantilla.fecha_registro else None,
            "se_borra_el": get_settings().fin_piloto.isoformat(),
            "dias_restantes": retencion.dias_restantes(),
        },
        "cedula_verificada_el": cedula.fecha.isoformat() if cedula and cedula.resultado == "verificado" else None,
        "autorizacion": None if (aut := autorizacion.vigente(db, persona.id_persona)) is None else {
            "version": aut.version_texto, "hash": aut.hash_texto, "fecha": aut.fecha.isoformat(),
            "acepto_datos": aut.acepto_datos, "acepto_biometria": aut.acepto_biometria,
            "revocada_en": aut.revocada_en.isoformat() if aut.revocada_en else None,
        },
    }


@router.post("/revocar-biometria")
def revocar_biometria(db: DB, request: Request, flujo: Annotated[dict, Depends(token_flujo("verificado"))]):
    """El titular revoca la autorización de sus datos biométricos (Ley 1581 art. 8 lit. e; Decreto 1377 art. 9):
    se borran su plantilla cancelable y la evidencia del cotejo con la cédula. Sus votos ya emitidos no cambian."""
    votante = votante_del_flujo(db, flujo)
    if not retencion.suprimir_biometria(db, votante.id_persona):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay una plantilla biométrica registrada")
    autorizacion.revocar_biometria(db, votante.id_persona)
    auditoria.registrar(db, "REVOCAR_BIOMETRIA", actor="titular", ip=ip_cliente(request), commit=False,
                        descripcion=f"Votante #{votante.id_votante} revocó su plantilla biométrica")
    db.commit()
    return {"revocada": True}


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
