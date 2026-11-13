"""Inscripción atómica en la Registraduría.

Mientras la inscripción está en curso no se escribe nada en la base de datos. Lo recogido en cada paso (datos,
autorización, lectura de la cédula y descriptor de la cara impresa) viaja **sellado** dentro del token del
navegador: cifrado con ECIES (llave del sistema "documento") y firmado por el JWT, así que el navegador no lo
puede leer ni modificar. Solo al terminar, `confirmar` guarda todo en una única transacción; si algo falla se
hace rollback. Si el ciudadano abandona o vence el plazo, el token caduca y no queda ningún dato suyo.
"""
import base64
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crypto import biometria as bio
from ..crypto import ecc, llavero
from ..models import Biometria, Persona, VerificacionDocumento, Votante
from . import auditoria, autorizacion, documento, limites
from .consultas import EDAD_MINIMA, campo_persona, cifrar_campo, edad, es_menor


class InscripcionRechazada(Exception):
    def __init__(self, estado_http: int, mensaje: str, detalle: str | None = None):
        super().__init__(mensaje)
        self.estado_http = estado_http
        # Para la auditoría: qué falló, sin datos personales. No se muestra al ciudadano.
        self.detalle = detalle


# ---------- Estado sellado ----------

def nuevo_estado(datos: dict, aceptada: dict) -> dict:
    ahora = datetime.now(UTC)
    vence = ahora + timedelta(minutes=get_settings().minutos_inscripcion)
    return {"id": secrets.token_hex(12), "vence": vence.isoformat(), "datos": datos, "autorizacion": aceptada,
            "indice": llavero.indice_documento(datos["tipo_documento"], datos["documento"])}


def minutos_restantes(estado: dict) -> float:
    return max((datetime.fromisoformat(estado["vence"]) - datetime.now(UTC)).total_seconds() / 60, 0)


def _contexto(id_inscripcion: str) -> bytes:
    return f"inscripcion:{id_inscripcion}".encode()


def sellar(db: Session, estado: dict) -> str:
    claro = json.dumps(estado, ensure_ascii=False).encode()
    paquete = ecc.cifrar(llavero.publica(db, "documento"), claro, _contexto(estado["id"]))
    return estado["id"] + "." + base64.urlsafe_b64encode(paquete).decode()


def abrir(db: Session, sello: str) -> dict:
    try:
        id_inscripcion, datos = sello.split(".", 1)
        claro = ecc.descifrar(llavero.privada(db, "documento"), base64.urlsafe_b64decode(datos),
                              _contexto(id_inscripcion))
        estado = json.loads(claro)
    except Exception:
        raise InscripcionRechazada(400, "La inscripción no es válida. Empiece de nuevo.") from None
    if estado.get("id") != id_inscripcion:
        raise InscripcionRechazada(400, "La inscripción no es válida. Empiece de nuevo.")
    if cancelada(db, id_inscripcion):
        raise InscripcionRechazada(423, "Esta inscripción se canceló por intentos fallidos y no se guardó ningún "
                                        "dato. Empiece de nuevo.")
    if minutos_restantes(estado) <= 0:
        raise InscripcionRechazada(401, "El tiempo para completar la inscripción terminó y no se guardó ningún "
                                        "dato. Empiece de nuevo.")
    return estado


def cara_de(estado: dict) -> list[float] | None:
    cedula = estado.get("cedula") or {}
    return bio.desde_bytes(base64.b64decode(cedula["cara"])) if cedula.get("cara") else None


def con_cedula(estado: dict, frente: bytes, reverso: bytes, verificada: bool | None,
               cara: list[float] | None) -> dict:
    """Agrega la lectura de la cédula al estado. De las imágenes solo quedan sus huellas."""
    return {**estado, "cedula": {
        "hash": documento.huella(frente), "hash_reverso": documento.huella(reverso),
        "numero_coincide": verificada, "datos_coinciden": verificada, "fecha": datetime.now(UTC).isoformat(),
        "cara": base64.b64encode(bio.a_bytes(cara)).decode() if cara is not None else None,
    }}


# ---------- Intentos del cotejo facial (por inscripción) ----------
# No hay registro del ciudadano mientras la inscripción está en curso, así que los intentos se cuentan en la tabla
# de límites (servicios/limites.py), que sobrevive a reinicios. Al agotarlos, la inscripción queda cancelada.

def _clave_intentos(id_inscripcion: str) -> str:
    return f"inscripcion:{id_inscripcion}"


def cancelada(db: Session, id_inscripcion: str) -> bool:
    return limites.contador(db, _clave_intentos(id_inscripcion)) >= get_settings().max_intentos_biometricos


def registrar_fallo(db: Session, id_inscripcion: str) -> int:
    """Suma un intento fallido y devuelve los que quedan. Con 0, la inscripción queda cancelada. Hace commit."""
    s = get_settings()
    usados = limites.sumar(db, _clave_intentos(id_inscripcion), s.minutos_inscripcion * 60 * 2)
    db.commit()
    return max(s.max_intentos_biometricos - usados, 0)


# ---------- Validaciones y confirmación ----------

def revisar_documento(db: Session, indice: str) -> None:
    """Rechaza documentos ya inscritos con biometría o bloqueados. Un inscrito sin biometría (voto presencial o
    biometría revocada) puede volver a inscribirse: sus datos se confirman otra vez contra la cédula."""
    persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))
    if persona is None:
        return
    votante = db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
    if votante is None or db.scalar(select(Biometria.id_biometria).where(Biometria.id_persona == persona.id_persona)):
        raise InscripcionRechazada(409, "Este documento ya está inscrito. Puede ir a votar.")
    if votante.estado_habilitacion == "bloqueado":
        raise InscripcionRechazada(423, "La inscripción de este documento está bloqueada")


def rostro_duplicado(db: Session, descriptor: list[float], indice: str) -> int | None:
    """Persona que ya tiene registrado ese rostro con otro documento (Figura 10), o None."""
    umbral = get_settings().umbral_biometrico
    for otra in db.scalars(select(Biometria).where(Biometria.estado == "activa")):
        contexto = f"bio:{otra.id_persona}".encode()
        semilla = ecc.descifrar(llavero.privada(db, "biometria"), otra.semilla, contexto + b":semilla")
        plantilla = bio.desde_bytes(ecc.descifrar(llavero.privada(db, "biometria"), otra.plantilla_biometrica, contexto))
        if bio.distancia(bio.transformar(descriptor, semilla), plantilla) < umbral:
            persona = db.get(Persona, otra.id_persona)
            if persona is not None and persona.documento_indice != indice:
                return otra.id_persona
    return None


def confirmar(db: Session, estado: dict, descriptor: list[float] | None, distancia: float | None,
              ip: str | None) -> tuple[Persona, Votante]:
    """Guarda la inscripción completa en una sola transacción: persona y votante (si no existían), prueba de la
    autorización, evidencia de la cédula y, con autorización biométrica, la plantilla cancelable. Ante cualquier
    error hace rollback: o queda todo, o no queda nada."""
    datos, indice, cedula = estado["datos"], estado["indice"], estado["cedula"]
    try:
        # La fecha ya se confirmó contra la cédula: se revisa otra vez la edad con ella antes de guardar nada.
        if es_menor(datos["fecha_nacimiento"]):
            raise InscripcionRechazada(422, f"Debe tener al menos {EDAD_MINIMA} años cumplidos para inscribirse "
                                            "como votante.", "Menor de edad")
        revisar_documento(db, indice)
        persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))
        nueva = persona is None
        if nueva:
            nacimiento = datetime.fromisoformat(datos["fecha_nacimiento"]).date()
            persona = Persona(
                tipo_documento=datos["tipo_documento"], documento_indice=indice,
                documento=cifrar_campo(db, indice, "documento", datos["documento"]),
                nombres=cifrar_campo(db, indice, "nombres", datos["nombres"].strip()),
                apellidos=cifrar_campo(db, indice, "apellidos", datos["apellidos"].strip()),
                correo=cifrar_campo(db, indice, "correo", datos["correo"].strip()),
                telefono=cifrar_campo(db, indice, "telefono", datos.get("telefono")),
                fecha_nacimiento=cifrar_campo(db, indice, "fecha_nacimiento", datos["fecha_nacimiento"]),
            )
            db.add(persona)
            db.flush()
            mayor = edad(nacimiento) >= 18
            votante = Votante(id_persona=persona.id_persona, mesa="Mesa virtual 01",
                              estado_habilitacion="habilitado" if mayor else "no_habilitado",
                              fecha_habilitacion=datetime.now(UTC) if mayor else None)
            db.add(votante)
            db.flush()
        else:
            votante = db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
            # Reinscripción: los datos ya se confirmaron contra la cédula, así que se actualizan (rectificación,
            # Ley 1581 art. 8 lit. a). Se registra qué campos cambiaron, sin sus valores.
            rectificados = [campo for campo in ("nombres", "apellidos", "fecha_nacimiento", "correo")
                            if campo_persona(db, persona, campo) != datos[campo].strip()]
            for campo in rectificados:
                setattr(persona, campo, cifrar_campo(db, indice, campo, datos[campo].strip()))
            if "fecha_nacimiento" in rectificados and votante.estado_habilitacion in ("habilitado", "no_habilitado"):
                mayor = edad(datetime.fromisoformat(datos["fecha_nacimiento"]).date()) >= 18
                votante.estado_habilitacion = "habilitado" if mayor else "no_habilitado"
            if rectificados:
                auditoria.registrar(db, "RECTIFICAR_DATOS", actor="registraduria", ip=ip, commit=False,
                                    descripcion=f"Votante #{votante.id_votante}: actualizados según la cédula: "
                                                f"{', '.join(rectificados)}")

        evidencia = db.scalar(select(VerificacionDocumento).where(VerificacionDocumento.id_persona == persona.id_persona))
        if evidencia is None:
            evidencia = VerificacionDocumento(id_persona=persona.id_persona)
            db.add(evidencia)
        evidencia.hash_imagen = cedula["hash"]
        evidencia.hash_reverso = cedula.get("hash_reverso")
        evidencia.numero_coincide = cedula["numero_coincide"]
        evidencia.datos_coinciden = cedula.get("datos_coinciden")
        evidencia.distancia_cotejo = round(distancia, 4) if distancia is not None else None
        evidencia.resultado = "verificado"
        evidencia.fecha = datetime.fromisoformat(cedula["fecha"])
        evidencia.version = documento.VERSION

        aceptada = estado["autorizacion"]
        autorizacion.registrar(db, persona.id_persona, indice, aceptada["acepto_biometria"])

        if descriptor is not None:
            semilla = bio.nueva_semilla()
            contexto = f"bio:{persona.id_persona}".encode()
            pub = llavero.publica(db, "biometria")
            db.add(Biometria(
                id_persona=persona.id_persona,
                plantilla_biometrica=ecc.cifrar(pub, bio.a_bytes(bio.transformar(descriptor, semilla)), contexto),
                semilla=ecc.cifrar(pub, semilla, contexto + b":semilla"),
            ))
            votante.intentos_biometricos = 0

        detalle = "con plantilla biométrica" if descriptor is not None else "sin biometría (voto presencial)"
        auditoria.registrar(db, "REGISTRAR_VOTANTE" if nueva else "REINSCRIBIR_VOTANTE", actor="registraduria",
                            ip=ip, commit=False,
                            descripcion=f"Votante #{votante.id_votante} inscrito {detalle}; autorización "
                                        f"v{aceptada['version']}; cédula verificada (imagen descartada)")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise InscripcionRechazada(409, "Este documento acaba de inscribirse. Si no fue usted, contáctenos.") from None
    except Exception:
        db.rollback()
        raise
    return persona, votante
