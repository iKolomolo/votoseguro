"""Datos iniciales: roles, cuenta de superadministrador y, opcionalmente, elecciones de demostración."""
import logging
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .crypto import llavero
from .models import Candidato, Eleccion, InscripcionCandidato, Persona, Rol, Usuario, Votante
from .seguridad import ROL_ADMIN, ROL_SUPERADMIN, ROL_SUPERVISOR, hash_password
from .servicios import auditoria, elecciones
from .servicios.consultas import cifrar_campo

log = logging.getLogger("votoseguro")

ROLES = [
    (ROL_SUPERADMIN, "Control total: cuentas, respaldos, restauración y gestión electoral"),
    (ROL_ADMIN, "Gestiona procesos electorales, candidatos, votantes y reportes"),
    (ROL_SUPERVISOR, "Solo lectura: supervisa la jornada, resultados y auditoría"),
]

# Partidos ficticios: el prototipo no usa nombres de partidos reales.
CANDIDATOS_DEMO = [
    ("María Claudia Torres Restrepo", "Movimiento Ciudad Viva", "#003da5"),
    ("Carlos Andrés Mejía Ríos", "Partido Renovación Andina", "#1a7a4a"),
    ("Sandra Milena Gutiérrez López", "Alianza Bogotá Futuro", "#f59e0b"),
    ("Jorge Luis Herrera Pinto", "Coalición Tierra y Progreso", "#8b5cf6"),
]
NOMBRES = ["Ana", "Luis", "Camila", "Andrés", "Laura", "Julián", "Valentina", "Santiago", "Paula", "Diego",
           "Daniela", "Felipe", "Natalia", "Sebastián", "Carolina", "Mateo"]
APELLIDOS = ["Rodríguez", "Gómez", "Martínez", "López", "García", "Hernández", "Díaz", "Moreno", "Rojas",
             "Vargas", "Castro", "Ramírez", "Suárez", "Ortiz", "Pérez", "Cárdenas"]


def sembrar(db: Session) -> None:
    for nombre, descripcion in ROLES:
        if db.scalar(select(Rol).where(Rol.nombre == nombre)) is None:
            db.add(Rol(nombre=nombre, descripcion=descripcion))
    db.flush()

    settings = get_settings()
    if db.scalar(select(func.count()).select_from(Usuario)) == 0:
        rol = db.scalar(select(Rol).where(Rol.nombre == ROL_SUPERADMIN))
        db.add(Usuario(correo=settings.admin_correo.lower(), nombre_usuario="Superadministrador", rol=rol,
                       password=hash_password(settings.admin_password)))
        auditoria.registrar(db, "INICIALIZAR_SISTEMA", descripcion="Roles y cuenta inicial creados", commit=False)
        db.commit()
        log.warning("Cuenta inicial: %s (cambie la contraseña)", settings.admin_correo)
        if settings.sembrar_datos_demo:
            _demo(db)
    db.commit()


def _persona_demo(db: Session, n: int, rng: random.Random) -> Votante:
    documento = str(1_020_000_000 + n)
    indice = llavero.indice_documento("CC", documento)
    nombre, apellido = rng.choice(NOMBRES), f"{rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
    persona = Persona(
        tipo_documento="CC", documento_indice=indice,
        documento=cifrar_campo(db, indice, "documento", documento),
        nombres=cifrar_campo(db, indice, "nombres", nombre),
        apellidos=cifrar_campo(db, indice, "apellidos", apellido),
        correo=cifrar_campo(db, indice, "correo", f"votante{n}@correo.co"),
        telefono=None,
        fecha_nacimiento=cifrar_campo(db, indice, "fecha_nacimiento",
                                      date(rng.randint(1956, 2006), rng.randint(1, 12), rng.randint(1, 28)).isoformat()),
    )
    db.add(persona)
    db.flush()
    votante = Votante(id_persona=persona.id_persona, estado_habilitacion="habilitado",
                      fecha_habilitacion=datetime.now(UTC), mesa="Mesa virtual 01")
    db.add(votante)
    db.flush()
    return votante


def _con_candidatos(db: Session, eleccion: Eleccion) -> None:
    for numero, (nombre, partido, color) in enumerate(CANDIDATOS_DEMO, start=1):
        candidato = Candidato(nombre=nombre, partido=partido, color=color,
                              descripcion=f"Candidato(a) de demostración por {partido}.")
        db.add(candidato)
        db.flush()
        db.add(InscripcionCandidato(id_eleccion=eleccion.id_eleccion, id_candidato=candidato.id_candidato,
                                    numero_candidato=numero))
    db.flush()
    db.refresh(eleccion)


def _demo(db: Session) -> None:
    """Tres elecciones como en el diseño: una cerrada con votos, una activa y una próxima."""
    rng = random.Random(2026)
    ahora = datetime.now(UTC)
    votantes = [_persona_demo(db, n, rng) for n in range(1, 61)]

    cerrada = elecciones.crear(db, nombre="Elección Gobernador de Cundinamarca", descripcion="Proceso de demostración",
                               tipo="Departamental", fecha_inicio=ahora - timedelta(minutes=5),
                               fecha_fin=ahora + timedelta(hours=1))
    _con_candidatos(db, cerrada)
    ids = [i.id_candidato for i in cerrada.inscripciones]
    for votante in votantes[:47]:
        elecciones.emitir_voto(db, votante, cerrada, rng.choices(ids, weights=[41, 31, 20, 8])[0])
    elecciones.cerrar(db, cerrada, actor="sistema")
    cerrada.fecha_inicio, cerrada.fecha_fin = ahora - timedelta(days=30, hours=8), ahora - timedelta(days=30)
    cerrada.fecha_cierre = cerrada.fecha_fin

    activa = elecciones.crear(db, nombre="Elección Alcalde Municipal de Bogotá", descripcion="Proceso de demostración",
                              tipo="Municipal", fecha_inicio=ahora - timedelta(hours=1),
                              fecha_fin=ahora + timedelta(hours=10))
    activa.estado = "activa"
    _con_candidatos(db, activa)
    ids = [i.id_candidato for i in activa.inscripciones]
    for votante in votantes[:21]:
        elecciones.emitir_voto(db, votante, activa, rng.choice(ids))

    proxima = elecciones.crear(db, nombre="Consulta Popular — Presupuesto Participativo",
                               descripcion="Proceso de demostración", tipo="Distrital",
                               fecha_inicio=ahora + timedelta(days=9), fecha_fin=ahora + timedelta(days=9, hours=8))
    _con_candidatos(db, proxima)
    auditoria.registrar(db, "DATOS_DEMO", descripcion="Se crearon 60 votantes y 3 elecciones de demostración",
                        commit=False)
    db.commit()
