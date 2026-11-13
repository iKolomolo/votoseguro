"""Rutas sin autenticación: verificación de comprobantes, resultados cerrados y transparencia."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import get_settings
from ..crypto import ecc, llavero
from ..models import Candidato, Eleccion, Participacion, Persona, Votante
from ..seguridad import DB, ip_cliente
from ..servicios import auditoria, autorizacion, elecciones, limites, politica
from ..servicios.consultas import campo_persona, eleccion_dict, elecciones_visibles, resultados

router = APIRouter(prefix="/api/publico", tags=["público"])


@router.get("/autorizacion")
def texto_autorizacion():
    """Texto vigente de la autorización de datos, con su versión y huella SHA-256."""
    return autorizacion.texto()


@router.get("/politica")
def politica_tratamiento():
    """Política de Tratamiento de Datos Personales vigente (Decreto 1377 art. 13), con versión y huella SHA-256."""
    return politica.texto()


@router.get("/candidatos/{id_candidato}/imagen")
def imagen_candidato(id_candidato: int, db: DB):
    candidato = db.get(Candidato, id_candidato)
    if candidato is None or candidato.imagen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sin imagen")
    return Response(candidato.imagen, media_type=candidato.imagen_tipo or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=300"})


class Comprobante(BaseModel):
    codigo: str = Field(min_length=4, max_length=40)


@router.post("/verificar", dependencies=[limites.por_ip("verificar", "limite_verificar_ip", 60)])
def verificar(datos: Comprobante, db: DB):
    """Verificabilidad (principio del voto): confirma que el comprobante está registrado e íntegro. El código va en
    el cuerpo y no en la dirección, para que no quede en los registros de acceso del servidor ni del proveedor."""
    return elecciones.verificar_comprobante(db, datos.codigo)


class ConsultaParticipacion(BaseModel):
    tipo_documento: Literal["CC", "CE", "PA", "PPT"]
    documento: str = Field(pattern=r"^[0-9A-Za-z]{5,15}$")
    fecha_nacimiento: date


NO_ENCONTRADO = "No encontramos una inscripción con esos datos. Revise el documento y la fecha de nacimiento."


@router.post("/participacion", dependencies=[limites.por_ip("participacion", "limite_verificar_ip", 60)])
def participacion(datos: ConsultaParticipacion, db: DB, request: Request):
    """Verificación de comprobante por cédula: con el documento y la fecha de nacimiento (dato que debe conocer el
    titular, como en las consultas de la Registraduría) dice si la persona votó, en qué votación y qué día. Nunca por
    quién: el voto no está asociado a la persona. La respuesta es la misma si el documento no existe o la fecha no
    coincide, y cada documento admite pocos intentos fallidos, para que no se pueda adivinar la fecha."""
    settings = get_settings()
    indice = llavero.indice_documento(datos.tipo_documento, datos.documento)
    clave = f"participacion:{indice}"
    if limites.contador(db, clave) >= settings.max_intentos_biometricos:
        espera = limites.en_minutos(limites.segundos_restantes(db, clave))
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Hubo demasiados intentos fallidos con este documento. Espere {espera} y vuelva a "
                            "intentarlo.")
    persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))
    votante = None if persona is None else db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
    coincide = votante is not None and (
        campo_persona(db, persona, "fecha_nacimiento") or "")[:10] == datos.fecha_nacimiento.isoformat()
    ip = ip_cliente(request)
    if not coincide:
        limites.sumar(db, clave, settings.minutos_pausa_biometrica * 60)
        auditoria.registrar(db, "CONSULTAR_PARTICIPACION", actor="publico", ip=ip, resultado="rechazado",
                            commit=False, descripcion="Documento o fecha de nacimiento no coinciden")
        db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_ENCONTRADO)
    limites.reiniciar(db, clave)
    filas = db.execute(
        select(Participacion.fecha_hora, Eleccion.nombre, Eleccion.codigo)
        .join(Eleccion, Eleccion.id_eleccion == Participacion.id_eleccion)
        .where(Participacion.id_votante == votante.id_votante)
        .order_by(Participacion.fecha_hora.desc())
    ).all()
    auditoria.registrar(db, "CONSULTAR_PARTICIPACION", actor="publico", ip=ip, commit=False,
                        descripcion=f"Consulta de participación del votante #{votante.id_votante}")
    db.commit()
    return {
        "nombre": f"{campo_persona(db, persona, 'nombres')} {campo_persona(db, persona, 'apellidos')}",
        "tipo_documento": persona.tipo_documento,
        "documento": campo_persona(db, persona, "documento"),
        "votaciones": [{"eleccion": n, "codigo": c, "fecha": f.date().isoformat()} for f, n, c in filas],
    }


@router.get("/elecciones")
def listar(db: DB):
    return [eleccion_dict(db, e) for e in elecciones_visibles(db)]


@router.get("/elecciones/{id_eleccion}/resultados")
def resultados_publicos(id_eleccion: int, db: DB):
    eleccion = db.get(Eleccion, id_eleccion)
    if eleccion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votación no encontrada")
    if eleccion.estado != "finalizada":
        raise HTTPException(status.HTTP_409_CONFLICT, "Los resultados se publican al cerrar la votación")
    return resultados(db, eleccion)


@router.get("/elecciones/{id_eleccion}/llave-publica")
def llave_publica(id_eleccion: int, db: DB):
    """Transparencia: cualquiera puede ver con qué llave ECC se cifran los votos de la elección."""
    eleccion = db.get(Eleccion, id_eleccion)
    if eleccion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votación no encontrada")
    pub = ecc.importar_publica(eleccion.clave_publica)
    return {"curva": ecc.NOMBRE_CURVA, "pem": ecc.publica_pem(pub),
            "huella": ecc.sha256_hex(eleccion.clave_publica)[:32]}
