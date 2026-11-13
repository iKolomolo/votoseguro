"""Política de retención (Decreto 1377 de 2013, art. 11): los datos solo se conservan mientras se necesitan.

Aquí se cumplen los plazos que promete la Política de Tratamiento (servicios/politica.py, numerales 6, 14 y 23):

- Copias de seguridad: se borran a los `dias_respaldo` días (7).
- Participación: `dias_reclamacion` días (30) después del cierre de cada elección se desvincula del votante; el
  conteo de participación se conserva.
- Supresión de un titular a su solicitud: se borran sus datos personales, su plantilla y la evidencia de la cédula.
  Solo se niega mientras haya votado en una elección abierta o cerrada hace menos de 30 días (voto único).
- Prueba de la autorización: tras la supresión queda seudonimizada (sin nombre ni número legible, solo el índice
  ciego HMAC) y se borra a los `anios_prueba_autorizacion` años (3).
- Fin del piloto: se suprimen todos los titulares. Un año después se depura la bitácora.

`aplicar` se ejecuta en cada ciclo de supervisión y es idempotente.
"""
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (Auditoria, Autorizacion, Biometria, Eleccion, Participacion, Persona, Respaldo, Supresion,
                      VerificacionDocumento, Votante)
from . import auditoria, limites


class SupresionAplazada(Exception):
    """La supresión no procede todavía: el titular votó en una elección abierta o cerrada hace poco."""

    def __init__(self, mensaje: str, desde: date | None):
        super().__init__(mensaje)
        self.desde = desde


def hoy() -> date:
    return datetime.now(ZoneInfo(get_settings().zona_horaria)).date()


def piloto_terminado() -> bool:
    return hoy() > get_settings().fin_piloto


def dias_restantes() -> int:
    return max((get_settings().fin_piloto - hoy()).days, 0)


def suprimir_biometria(db: Session, id_persona: int) -> int:
    """Borra la plantilla y la evidencia del cotejo con la cédula de un titular.
    No hace commit. Devuelve cuántas plantillas se borraron."""
    borradas = db.execute(delete(Biometria).where(Biometria.id_persona == id_persona)).rowcount
    db.execute(delete(VerificacionDocumento).where(VerificacionDocumento.id_persona == id_persona))
    return borradas


def _limite_reclamacion() -> datetime:
    return datetime.now(UTC) - timedelta(days=get_settings().dias_reclamacion)


def revisar_supresion(db: Session, votante: Votante) -> None:
    """Lanza SupresionAplazada si el votante participó en una elección abierta o cerrada hace menos del plazo de
    reclamaciones: hasta entonces su participación garantiza que no vote dos veces (Decreto 1377, art. 9)."""
    dias = get_settings().dias_reclamacion
    pendientes = db.scalars(select(Eleccion).join(Participacion, Participacion.id_eleccion == Eleccion.id_eleccion)
                            .where(Participacion.id_votante == votante.id_votante)).all()
    abiertas = [e for e in pendientes if e.estado != "finalizada"]
    recientes = [e for e in pendientes if e.estado == "finalizada" and e.fecha_cierre and e.fecha_cierre > _limite_reclamacion()]
    if abiertas:
        raise SupresionAplazada(
            f"Votó en {abiertas[0].nombre}, que sigue abierta. Sus datos se podrán borrar {dias} días después de "
            "su cierre, cuando termine el plazo de reclamaciones.", None)
    if recientes:
        desde = (max(e.fecha_cierre for e in recientes) + timedelta(days=dias + 1)).date()
        raise SupresionAplazada(
            f"Votó en {recientes[0].nombre}, cerrada hace menos de {dias} días (plazo de reclamaciones). Sus datos "
            f"se podrán borrar desde el {desde:%d/%m/%Y}.", desde)


def suprimir_titular(db: Session, votante: Votante, *, forzar: bool = False) -> None:
    """Borra todos los datos personales de un votante (Ley 1581, art. 8 lit. e). No hace commit.

    - Plantilla, evidencia de la cédula, votante y persona: se borran.
    - Participación: se desvincula (queda el conteo, no la persona).
    - Prueba de la autorización: queda seudonimizada (sin persona, solo el índice ciego) para poder demostrar el
      consentimiento; se borra a los 3 años.
    - Se anota el índice ciego en SUPRESION para volver a aplicar el borrado si se restaura un respaldo anterior.
    `forzar` (fin del piloto) omite la revisión del voto único.
    """
    if not forzar:
        revisar_supresion(db, votante)
    persona = db.get(Persona, votante.id_persona)
    ahora = datetime.now(UTC)
    suprimir_biometria(db, votante.id_persona)
    db.execute(update(Participacion).where(Participacion.id_votante == votante.id_votante).values(id_votante=None))
    db.execute(update(Autorizacion).where(Autorizacion.id_persona == votante.id_persona)
               .values(id_persona=None, suprimida_en=ahora))
    db.delete(votante)
    db.flush()
    if persona is not None:
        db.add(Supresion(documento_indice=persona.documento_indice, fecha=ahora))
        db.delete(persona)
    db.flush()


def reaplicar_supresiones(db: Session, desde: datetime) -> int:
    """Tras restaurar un respaldo: vuelve a borrar a quienes pidieron la supresión después de la fecha del respaldo.
    No hace commit."""
    total = 0
    for s in db.scalars(select(Supresion).where(Supresion.fecha > desde)):
        persona = db.scalar(select(Persona).where(Persona.documento_indice == s.documento_indice))
        votante = persona and db.scalar(select(Votante).where(Votante.id_persona == persona.id_persona))
        if votante is not None:
            suprimir_titular(db, votante, forzar=True)
            total += 1
    return total


def caducar_respaldos(db: Session) -> int:
    """Borra los respaldos (archivo y registro) más antiguos que `dias_respaldo`. No hace commit."""
    s = get_settings()
    limite = datetime.now(UTC) - timedelta(days=s.dias_respaldo)
    viejos = db.scalars(select(Respaldo).where(Respaldo.fecha < limite)).all()
    for r in viejos:
        (s.directorio_respaldos / r.archivo).unlink(missing_ok=True)
        db.delete(r)
    # Archivos sin registro (por ejemplo, de una base que se borró): también caducan.
    if s.directorio_respaldos.exists():
        conocidos = set(db.scalars(select(Respaldo.archivo)))
        for archivo in s.directorio_respaldos.glob("*.vsbak"):
            if archivo.name not in conocidos and archivo.stat().st_mtime < limite.timestamp():
                archivo.unlink(missing_ok=True)
    # Las anotaciones de supresión solo sirven mientras exista un respaldo anterior a ellas.
    db.execute(delete(Supresion).where(Supresion.fecha < limite))
    return len(viejos)


def desvincular_participaciones(db: Session) -> int:
    """Cerrado el plazo de reclamaciones, la participación ya no se asocia a ningún votante. No hace commit."""
    cerradas = select(Eleccion.id_eleccion).where(Eleccion.estado == "finalizada",
                                                  Eleccion.fecha_cierre < _limite_reclamacion())
    return db.execute(update(Participacion).where(Participacion.id_votante.is_not(None),
                                                  Participacion.id_eleccion.in_(cerradas))
                      .values(id_votante=None)).rowcount


def purgar_autorizaciones(db: Session) -> int:
    """Borra las pruebas de autorización seudonimizadas hace más de `anios_prueba_autorizacion` años."""
    limite = datetime.now(UTC) - timedelta(days=365 * get_settings().anios_prueba_autorizacion)
    return db.execute(delete(Autorizacion).where(Autorizacion.suprimida_en < limite)).rowcount


def aplicar(db: Session) -> dict[str, int]:
    """Aplica todos los plazos de conservación. Devuelve lo que borró en esta pasada."""
    s = get_settings()
    hecho = {"respaldos": caducar_respaldos(db), "participaciones": desvincular_participaciones(db),
             "autorizaciones": purgar_autorizaciones(db), "titulares": 0, "bitacora": 0}
    limites.purgar(db)  # contadores de intentos vencidos (no se informa: no son datos de titulares)
    if piloto_terminado():
        for votante in db.scalars(select(Votante)).all():
            suprimir_titular(db, votante, forzar=True)
            hecho["titulares"] += 1
        db.execute(delete(Biometria))  # por si quedara alguna plantilla sin votante
        if hecho["titulares"]:
            auditoria.registrar(db, "SUPRIMIR_DATOS_FIN_PILOTO", commit=False,
                                descripcion=f"{hecho['titulares']} titular(es) suprimidos: el piloto terminó el "
                                            f"{s.fin_piloto.isoformat()}")
        # Un año después del fin del piloto se depura la bitácora completa y empieza una cadena nueva.
        fin_bitacora = datetime.combine(s.fin_piloto + timedelta(days=s.dias_bitacora_post_piloto + 1),
                                        datetime.min.time(), UTC)
        if datetime.now(UTC) >= fin_bitacora and db.scalar(
                select(Auditoria.id_auditoria).where(Auditoria.fecha_hora < fin_bitacora).limit(1)):
            hecho["bitacora"] = db.execute(delete(Auditoria)).rowcount
            auditoria.registrar(db, "DEPURAR_BITACORA", commit=False,
                                descripcion=f"{hecho['bitacora']} registros borrados un año después del fin del piloto")
    if hecho["respaldos"] or hecho["participaciones"] or hecho["autorizaciones"]:
        auditoria.registrar(db, "APLICAR_RETENCION", commit=False, descripcion=(
            f"Respaldos borrados: {hecho['respaldos']}, participaciones desvinculadas: {hecho['participaciones']}, "
            f"pruebas de autorización borradas: {hecho['autorizaciones']}"))
    db.commit()
    return hecho
