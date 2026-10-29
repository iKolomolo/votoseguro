"""Rutas sin autenticación: verificación de comprobantes, resultados cerrados y transparencia."""
from fastapi import APIRouter, HTTPException, Response, status

from ..crypto import ecc
from ..models import Candidato, Eleccion
from ..seguridad import DB
from ..servicios import elecciones
from ..servicios.consultas import eleccion_dict, elecciones_visibles, resultados

router = APIRouter(prefix="/api/publico", tags=["público"])


@router.get("/candidatos/{id_candidato}/imagen")
def imagen_candidato(id_candidato: int, db: DB):
    candidato = db.get(Candidato, id_candidato)
    if candidato is None or candidato.imagen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sin imagen")
    return Response(candidato.imagen, media_type=candidato.imagen_tipo or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=300"})


@router.get("/verificar/{codigo}")
def verificar(codigo: str, db: DB):
    """Verificabilidad (principio del voto): confirma que el comprobante está registrado e íntegro."""
    return elecciones.verificar_comprobante(db, codigo)


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
