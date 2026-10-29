"""Gestión de procesos electorales, candidatos, resultados y reportes (RQF06-RQF09, RQF18-RQF24)."""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from ..models import Candidato, Eleccion, InscripcionCandidato
from ..seguridad import DB, Gestor, UsuarioActual, ip_cliente
from ..servicios import auditoria, elecciones, reportes
from ..servicios.consultas import candidatos_de, candidato_dict, eleccion_dict, resultados

router = APIRouter(prefix="/api/admin", tags=["gestión electoral"])

TIPOS_IMAGEN = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGEN = 2 * 1024 * 1024


def _eleccion(db, id_eleccion: int) -> Eleccion:
    eleccion = db.get(Eleccion, id_eleccion)
    if eleccion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votación no encontrada")
    return eleccion


def _exigir_programada(eleccion: Eleccion) -> None:
    if elecciones.estado_calculado(eleccion) != "programada":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Solo se puede modificar una votación que aún no ha iniciado")


class DatosEleccion(BaseModel):
    nombre: str = Field(min_length=5, max_length=120)
    descripcion: str | None = Field(default=None, max_length=2000)
    tipo: str = Field(default="Municipal", max_length=30)
    fecha_inicio: datetime
    fecha_fin: datetime

    @model_validator(mode="after")
    def fechas(self):
        for campo in ("fecha_inicio", "fecha_fin"):
            if getattr(self, campo).tzinfo is None:
                raise ValueError("Las fechas deben incluir zona horaria")
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("La fecha de cierre debe ser posterior a la de inicio")
        return self


@router.get("/elecciones")
def listar(_: UsuarioActual, db: DB, incluir_archivadas: bool = False):
    consulta = select(Eleccion).order_by(Eleccion.fecha_inicio.desc())
    if not incluir_archivadas:
        consulta = consulta.where(Eleccion.archivada.is_(False))
    return [eleccion_dict(db, e) for e in db.scalars(consulta)]


@router.post("/elecciones", status_code=status.HTTP_201_CREATED)
def crear(datos: DatosEleccion, usuario: Gestor, db: DB, request: Request):
    if datos.fecha_fin <= datetime.now(UTC):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La fecha de cierre ya pasó")
    eleccion = elecciones.crear(db, **datos.model_dump())
    auditoria.registrar(db, "CREAR_ELECCION", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"Creó elección {eleccion.codigo}", commit=False)
    db.commit()
    return eleccion_dict(db, eleccion)


@router.get("/elecciones/{id_eleccion}")
def detalle(id_eleccion: int, _: UsuarioActual, db: DB):
    eleccion = _eleccion(db, id_eleccion)
    return {**eleccion_dict(db, eleccion), "candidatos": candidatos_de(eleccion)}


@router.put("/elecciones/{id_eleccion}")
def editar(id_eleccion: int, datos: DatosEleccion, usuario: Gestor, db: DB, request: Request):
    eleccion = _eleccion(db, id_eleccion)
    _exigir_programada(eleccion)
    for campo, valor in datos.model_dump().items():
        setattr(eleccion, campo, valor)
    auditoria.registrar(db, "EDITAR_ELECCION", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"Editó {eleccion.codigo}", commit=False)
    db.commit()
    return eleccion_dict(db, eleccion)


@router.post("/elecciones/{id_eleccion}/cerrar")
def cerrar(id_eleccion: int, usuario: Gestor, db: DB, request: Request):
    eleccion = _eleccion(db, id_eleccion)
    try:
        elecciones.cerrar(db, eleccion, actor=usuario.correo, id_usuario=usuario.id_usuario, ip=ip_cliente(request))
    except elecciones.ErrorVotacion as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    db.commit()
    return eleccion_dict(db, eleccion)


@router.post("/elecciones/{id_eleccion}/archivar")
def archivar(id_eleccion: int, usuario: Gestor, db: DB, request: Request, archivar: bool = True):
    """RQF19: oculta la elección del historial, pero sus datos permanecen en la base de datos."""
    eleccion = _eleccion(db, id_eleccion)
    if eleccion.estado != "finalizada":
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se pueden archivar votaciones cerradas")
    eleccion.archivada = archivar
    auditoria.registrar(db, "ARCHIVAR_ELECCION" if archivar else "DESARCHIVAR_ELECCION", actor=usuario.correo,
                        id_usuario=usuario.id_usuario, ip=ip_cliente(request), descripcion=eleccion.codigo,
                        commit=False)
    db.commit()
    return eleccion_dict(db, eleccion)


# ---------- Candidatos ----------

async def _leer_imagen(imagen: UploadFile | None) -> tuple[bytes, str] | None:
    if imagen is None or not imagen.filename:
        return None
    if imagen.content_type not in TIPOS_IMAGEN:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La imagen debe ser JPG, PNG o WEBP")
    datos = await imagen.read(MAX_IMAGEN + 1)
    if len(datos) > MAX_IMAGEN:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera 2 MB")
    return datos, imagen.content_type


@router.get("/elecciones/{id_eleccion}/candidatos")
def listar_candidatos(id_eleccion: int, _: UsuarioActual, db: DB):
    return candidatos_de(_eleccion(db, id_eleccion))


Texto = Annotated[str, Form(min_length=2, max_length=150)]
Color = Annotated[str, Form(pattern=r"^#[0-9a-fA-F]{6}$")]


@router.post("/elecciones/{id_eleccion}/candidatos", status_code=status.HTTP_201_CREATED)
async def agregar_candidato(
    id_eleccion: int, usuario: Gestor, db: DB, request: Request,
    nombre: Texto, partido: Texto, color: Color = "#003da5",
    descripcion: Annotated[str | None, Form(max_length=2000)] = None,
    numero: Annotated[int | None, Form(ge=1, le=99)] = None,
    imagen: Annotated[UploadFile | None, File()] = None,
):
    eleccion = _eleccion(db, id_eleccion)
    _exigir_programada(eleccion)
    if numero is None:
        numero = (db.scalar(select(func.max(InscripcionCandidato.numero_candidato))
                            .where(InscripcionCandidato.id_eleccion == id_eleccion)) or 0) + 1
    elif db.scalar(select(InscripcionCandidato.id_inscripcion).where(
            InscripcionCandidato.id_eleccion == id_eleccion, InscripcionCandidato.numero_candidato == numero)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"El número {numero} ya está asignado")
    archivo = await _leer_imagen(imagen)
    candidato = Candidato(nombre=nombre.strip(), partido=partido.strip(), descripcion=descripcion, color=color,
                          imagen=archivo[0] if archivo else None, imagen_tipo=archivo[1] if archivo else None)
    db.add(candidato)
    db.flush()
    db.add(InscripcionCandidato(id_eleccion=id_eleccion, id_candidato=candidato.id_candidato,
                                numero_candidato=numero))
    auditoria.registrar(db, "AGREGAR_CANDIDATO", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"#{numero:02d} {candidato.nombre} en {eleccion.codigo}",
                        commit=False)
    db.commit()
    return candidato_dict(candidato, numero)


@router.put("/candidatos/{id_candidato}")
async def editar_candidato(
    id_candidato: int, usuario: Gestor, db: DB, request: Request,
    nombre: Texto, partido: Texto, color: Color = "#003da5",
    descripcion: Annotated[str | None, Form(max_length=2000)] = None,
    imagen: Annotated[UploadFile | None, File()] = None,
):
    """RQF18. No se permite si el candidato participa en una votación en curso o cerrada."""
    candidato = db.get(Candidato, id_candidato)
    if candidato is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidato no encontrado")
    for insc in db.scalars(select(InscripcionCandidato).where(InscripcionCandidato.id_candidato == id_candidato)):
        _exigir_programada(insc.eleccion)
    archivo = await _leer_imagen(imagen)
    candidato.nombre, candidato.partido, candidato.color = nombre.strip(), partido.strip(), color
    candidato.descripcion = descripcion
    if archivo:
        candidato.imagen, candidato.imagen_tipo = archivo
    auditoria.registrar(db, "EDITAR_CANDIDATO", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=candidato.nombre, commit=False)
    db.commit()
    return candidato_dict(candidato)


@router.delete("/elecciones/{id_eleccion}/candidatos/{id_candidato}")
def quitar_candidato(id_eleccion: int, id_candidato: int, usuario: Gestor, db: DB, request: Request):
    eleccion = _eleccion(db, id_eleccion)
    _exigir_programada(eleccion)
    insc = db.scalar(select(InscripcionCandidato).where(
        InscripcionCandidato.id_eleccion == id_eleccion, InscripcionCandidato.id_candidato == id_candidato))
    if insc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El candidato no está inscrito en esta votación")
    db.delete(insc)
    auditoria.registrar(db, "QUITAR_CANDIDATO", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"{insc.candidato.nombre} de {eleccion.codigo}",
                        commit=False)
    db.commit()
    return {"ok": True}


# ---------- Resultados, reportes e historial ----------

def _resultados(db, id_eleccion: int) -> tuple[Eleccion, dict]:
    eleccion = _eleccion(db, id_eleccion)
    if eleccion.estado != "finalizada":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Los votos permanecen cifrados hasta el cierre. Cierre la votación para ver resultados.")
    return eleccion, resultados(db, eleccion)


@router.get("/elecciones/{id_eleccion}/resultados")
def ver_resultados(id_eleccion: int, _: UsuarioActual, db: DB):
    return _resultados(db, id_eleccion)[1]


@router.get("/elecciones/{id_eleccion}/reporte.pdf")
def reporte_pdf(id_eleccion: int, usuario: UsuarioActual, db: DB, request: Request):
    eleccion, datos = _resultados(db, id_eleccion)
    pdf = reportes.pdf_resultados(datos, generado_por=usuario.correo)
    auditoria.registrar(db, "GENERAR_REPORTE", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"PDF de {eleccion.codigo}")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="resultados-{eleccion.codigo}.pdf"'})


@router.get("/elecciones/{id_eleccion}/reporte.csv")
def reporte_csv(id_eleccion: int, usuario: UsuarioActual, db: DB, request: Request):
    eleccion, datos = _resultados(db, id_eleccion)
    auditoria.registrar(db, "GENERAR_REPORTE", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"CSV de {eleccion.codigo}")
    return Response(reportes.csv_resultados(datos), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="resultados-{eleccion.codigo}.csv"'})


@router.get("/historial")
def historial(_: UsuarioActual, db: DB):
    """RQF24: elecciones cerradas, incluidas las archivadas, con su ganador."""
    salida = []
    for e in db.scalars(select(Eleccion).where(Eleccion.estado == "finalizada").order_by(Eleccion.fecha_fin.desc())):
        r = resultados(db, e)
        ganador = r["candidatos"][0] if r["candidatos"] and r["total_votos"] else None
        salida.append({**r["eleccion"], "total_votos": r["total_votos"], "participacion_pct": r["participacion"],
                       "ganador": {"nombre": ganador["nombre"], "votos": ganador["votos"]} if ganador else None})
    return salida
