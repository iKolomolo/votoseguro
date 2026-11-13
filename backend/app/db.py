from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _sqlite_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


# Inmutabilidad del voto (RQF14): en PostgreSQL un trigger rechaza UPDATE y DELETE sobre la tabla voto.
# La única excepción es la restauración de un respaldo, que activa la variable de sesión votoseguro.restaurando.
_TRIGGER_VOTO = """
CREATE OR REPLACE FUNCTION voto_inmutable() RETURNS trigger AS $$
BEGIN
  IF current_setting('votoseguro.restaurando', true) = 'on' THEN
    RETURN COALESCE(OLD, NEW);
  END IF;
  RAISE EXCEPTION 'Los votos emitidos son inmutables';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_voto_inmutable ON voto;
CREATE TRIGGER trg_voto_inmutable BEFORE UPDATE OR DELETE ON voto
  FOR EACH ROW EXECUTE FUNCTION voto_inmutable();
"""


def crear_esquema() -> None:
    from . import models  # noqa: F401  (registra las tablas)

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        # Tablas de versiones anteriores. La imagen de la cédula ya no se conserva (Decreto 1377 arts. 4 y 11) y la
        # inscripción ya no deja datos a medias: ambas se eliminan con todo su contenido.
        conn.execute(text("DROP TABLE IF EXISTS documento_identidad"))
        conn.execute(text("DROP TABLE IF EXISTS cotejo_pendiente"))
    _agregar_columnas()
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text(_TRIGGER_VOTO))


# Columnas nuevas en tablas que ya existían: create_all no las agrega, así que se agregan aquí.
_COLUMNAS_NUEVAS = [
    ("verificacion_documento", "hash_reverso", "VARCHAR(64)"),
    ("verificacion_documento", "datos_coinciden", "BOOLEAN"),
    ("autorizacion", "suprimida_en", "TIMESTAMP WITH TIME ZONE"),
]


def _agregar_columnas() -> None:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tablas = set(inspector.get_table_names())
    with engine.begin() as conn:
        for tabla, columna, tipo in _COLUMNAS_NUEVAS:
            if tabla in tablas and columna not in {c["name"] for c in inspector.get_columns(tabla)}:
                conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))
        # La participación se desvincula del votante al cumplir su plazo: id_votante pasa a admitir NULL.
        if engine.dialect.name == "postgresql" and "participacion" in tablas:
            conn.execute(text("ALTER TABLE participacion ALTER COLUMN id_votante DROP NOT NULL"))
