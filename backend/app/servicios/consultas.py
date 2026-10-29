"""Consultas compartidas entre las rutas del votante, públicas y de administración."""
import unicodedata
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crypto import llavero
from ..models import Candidato, Eleccion, Participacion, Persona, Resultado, Votante
from .elecciones import estado_calculado


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


def edad(nacimiento: date, hoy: date | None = None) -> int:
    hoy = hoy or date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def campo_persona(db: Session, persona: Persona, campo: str) -> str | None:
    return llavero.descifrar_texto(db, getattr(persona, campo), f"persona:{campo}:{persona.documento_indice}")


def cifrar_campo(db: Session, indice: str, campo: str, valor: str | None) -> bytes | None:
    return llavero.cifrar_texto(db, valor, f"persona:{campo}:{indice}")


def candidato_dict(c: Candidato, numero: int | None = None) -> dict:
    return {
        "id_candidato": c.id_candidato, "numero": numero, "nombre": c.nombre, "partido": c.partido,
        "descripcion": c.descripcion, "color": c.color, "estado": c.estado,
        "imagen_url": f"/api/publico/candidatos/{c.id_candidato}/imagen" if c.imagen else None,
    }


def candidatos_de(eleccion: Eleccion) -> list[dict]:
    return [candidato_dict(i.candidato, i.numero_candidato) for i in eleccion.inscripciones if i.estado == "inscrito"]


def total_habilitados(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Votante).where(Votante.estado_habilitacion == "habilitado")) or 0


def total_participacion(db: Session, id_eleccion: int) -> int:
    return db.scalar(select(func.count()).select_from(Participacion)
                     .where(Participacion.id_eleccion == id_eleccion)) or 0


def eleccion_dict(db: Session, e: Eleccion) -> dict:
    return {
        "id_eleccion": e.id_eleccion, "codigo": e.codigo, "nombre": e.nombre, "descripcion": e.descripcion,
        "tipo": e.tipo, "fecha_inicio": e.fecha_inicio.isoformat(), "fecha_fin": e.fecha_fin.isoformat(),
        "estado": estado_calculado(e), "archivada": e.archivada,
        "fecha_cierre": e.fecha_cierre.isoformat() if e.fecha_cierre else None,
        "participacion": total_participacion(db, e.id_eleccion), "habilitados": total_habilitados(db),
        "num_candidatos": sum(1 for i in e.inscripciones if i.estado == "inscrito"),
        "integridad_ok": e.integridad_ok,
    }


def resultados(db: Session, e: Eleccion) -> dict:
    """Resultados de una elección finalizada, ordenados de mayor a menor."""
    votos = {r.id_candidato: r.votos for r in db.scalars(select(Resultado).where(Resultado.id_eleccion == e.id_eleccion))}
    total = sum(votos.values())
    filas = []
    for cand in candidatos_de(e):
        v = votos.get(cand["id_candidato"], 0)
        filas.append({**cand, "votos": v, "porcentaje": round(100 * v / total, 1) if total else 0.0})
    filas.sort(key=lambda f: (-f["votos"], f["numero"] or 0))
    habilitados = total_habilitados(db)
    votaron = total_participacion(db, e.id_eleccion)
    ventaja = filas[0]["votos"] - filas[1]["votos"] if len(filas) > 1 else (filas[0]["votos"] if filas else 0)
    return {
        "eleccion": eleccion_dict(db, e),
        "candidatos": filas,
        "total_votos": total,
        "habilitados": habilitados,
        "votaron": votaron,
        "participacion": round(100 * votaron / habilitados, 1) if habilitados else 0.0,
        "abstencion": round(100 * (habilitados - votaron) / habilitados, 1) if habilitados else 0.0,
        "ventaja": {"votos": ventaja, "porcentaje": round(100 * ventaja / total, 1) if total else 0.0},
        "integridad_ok": e.integridad_ok,
    }


def elecciones_visibles(db: Session) -> list[Eleccion]:
    return list(db.scalars(select(Eleccion).where(Eleccion.archivada.is_(False)).order_by(Eleccion.fecha_inicio.desc())))
