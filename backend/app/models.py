"""Modelo de datos basado en el MER del documento (Figura 8).

Cambios respecto al MER, justificados en el README:
- Los datos personales de PERSONA se guardan cifrados con ECIES (LargeBinary) y el documento se busca
  mediante un índice ciego (HMAC), para cumplir la Ley 1581 de 2012.
- VOTO usa un identificador aleatorio (UUID), una hora truncada y el hash del comprobante, para que no
  pueda relacionarse con PARTICIPACION.
- Se agregan RESULTADO, CLAVE_SISTEMA y RESPALDO, y los campos de llaves ECC en ELECCION.
"""
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, TypeDecorator, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class FechaUTC(TypeDecorator):
    """Fecha con zona horaria, siempre en UTC. SQLite (usado en las pruebas) no guarda la zona."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor, dialect):
        return valor.astimezone(UTC) if valor is not None and valor.tzinfo else valor

    def process_result_value(self, valor, dialect):
        if valor is not None and valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor


Fecha = FechaUTC()


class Rol(Base):
    __tablename__ = "rol"
    id_rol: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255))


class Persona(Base):
    __tablename__ = "persona"
    id_persona: Mapped[int] = mapped_column(primary_key=True)
    tipo_documento: Mapped[str] = mapped_column(String(10))
    documento_indice: Mapped[str] = mapped_column(String(64), unique=True)
    documento: Mapped[bytes] = mapped_column(LargeBinary)
    nombres: Mapped[bytes] = mapped_column(LargeBinary)
    apellidos: Mapped[bytes] = mapped_column(LargeBinary)
    correo: Mapped[bytes] = mapped_column(LargeBinary)
    telefono: Mapped[bytes | None] = mapped_column(LargeBinary)
    fecha_nacimiento: Mapped[bytes] = mapped_column(LargeBinary)
    fecha_registro: Mapped[datetime] = mapped_column(Fecha, server_default=func.now())
    estado: Mapped[str] = mapped_column(String(20), default="activo")


class Usuario(Base):
    __tablename__ = "usuario"
    id_usuario: Mapped[int] = mapped_column(primary_key=True)
    id_persona: Mapped[int | None] = mapped_column(ForeignKey("persona.id_persona"))
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"))
    correo: Mapped[str] = mapped_column(String(150), unique=True)
    nombre_usuario: Mapped[str] = mapped_column(String(80))
    password: Mapped[str] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(String(20), default="activo")
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(Fecha)
    fecha_creacion: Mapped[datetime] = mapped_column(Fecha, server_default=func.now())

    rol: Mapped[Rol] = relationship(lazy="joined")


class Candidato(Base):
    __tablename__ = "candidato"
    id_candidato: Mapped[int] = mapped_column(primary_key=True)
    id_persona: Mapped[int | None] = mapped_column(ForeignKey("persona.id_persona"))
    nombre: Mapped[str] = mapped_column(String(150))
    partido: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    imagen: Mapped[bytes | None] = mapped_column(LargeBinary)
    imagen_tipo: Mapped[str | None] = mapped_column(String(40))
    color: Mapped[str] = mapped_column(String(9), default="#003da5")
    estado: Mapped[str] = mapped_column(String(20), default="activo")


class Biometria(Base):
    __tablename__ = "biometria"
    id_biometria: Mapped[int] = mapped_column(primary_key=True)
    id_persona: Mapped[int] = mapped_column(ForeignKey("persona.id_persona"), unique=True)
    plantilla_biometrica: Mapped[bytes] = mapped_column(LargeBinary)
    semilla: Mapped[bytes] = mapped_column(LargeBinary)
    fecha_registro: Mapped[datetime] = mapped_column(Fecha, server_default=func.now())
    estado: Mapped[str] = mapped_column(String(20), default="activa")


class DocumentoIdentidad(Base):
    """Foto de la cédula presentada al enrolarse. La imagen y el descriptor de su rostro van cifrados (ECIES)."""
    __tablename__ = "documento_identidad"
    id_documento: Mapped[int] = mapped_column(primary_key=True)
    id_persona: Mapped[int] = mapped_column(ForeignKey("persona.id_persona"), unique=True)
    imagen: Mapped[bytes] = mapped_column(LargeBinary)
    imagen_tipo: Mapped[str] = mapped_column(String(40))
    descriptor: Mapped[bytes] = mapped_column(LargeBinary)
    # pendiente (número leído, falta comparar el rostro) | verificado
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    fecha_registro: Mapped[datetime] = mapped_column(Fecha, server_default=func.now())


class Votante(Base):
    __tablename__ = "votante"
    id_votante: Mapped[int] = mapped_column(primary_key=True)
    id_persona: Mapped[int] = mapped_column(ForeignKey("persona.id_persona"), unique=True)
    # habilitado | no_habilitado | sancionado | bloqueado
    estado_habilitacion: Mapped[str] = mapped_column(String(20), default="habilitado")
    fecha_habilitacion: Mapped[datetime | None] = mapped_column(Fecha)
    mesa: Mapped[str | None] = mapped_column(String(40))
    intentos_biometricos: Mapped[int] = mapped_column(Integer, default=0)

    persona: Mapped[Persona] = relationship(lazy="joined")


class Auditoria(Base):
    __tablename__ = "auditoria"
    id_auditoria: Mapped[int] = mapped_column(primary_key=True)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("usuario.id_usuario"))
    actor: Mapped[str] = mapped_column(String(150))
    accion: Mapped[str] = mapped_column(String(80))
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha_hora: Mapped[datetime] = mapped_column(Fecha)
    direccion_ip: Mapped[str | None] = mapped_column(String(45))
    resultado: Mapped[str] = mapped_column(String(30))
    # Cadena de hashes: cada registro incluye el hash del anterior, así que alterar uno rompe la cadena.
    hash_anterior: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Eleccion(Base):
    __tablename__ = "eleccion"
    id_eleccion: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(30), default="Municipal")
    fecha_inicio: Mapped[datetime] = mapped_column(Fecha)
    fecha_fin: Mapped[datetime] = mapped_column(Fecha)
    # programada | activa | finalizada
    estado: Mapped[str] = mapped_column(String(20), default="programada")
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_creacion: Mapped[datetime] = mapped_column(Fecha, server_default=func.now())
    fecha_cierre: Mapped[datetime | None] = mapped_column(Fecha)
    # Par ECC propio de cada elección: los votos se cifran con la pública; la privada, envuelta con la
    # clave maestra, solo se usa en el escrutinio después del cierre.
    clave_publica: Mapped[bytes] = mapped_column(LargeBinary)
    clave_privada: Mapped[bytes] = mapped_column(LargeBinary)
    votos_escrutados: Mapped[int | None] = mapped_column(Integer)
    integridad_ok: Mapped[bool | None] = mapped_column(Boolean)

    inscripciones: Mapped[list["InscripcionCandidato"]] = relationship(
        back_populates="eleccion", order_by="InscripcionCandidato.numero_candidato"
    )


class InscripcionCandidato(Base):
    __tablename__ = "inscripcion_candidato"
    __table_args__ = (
        UniqueConstraint("id_eleccion", "id_candidato"),
        UniqueConstraint("id_eleccion", "numero_candidato"),
    )
    id_inscripcion: Mapped[int] = mapped_column(primary_key=True)
    id_eleccion: Mapped[int] = mapped_column(ForeignKey("eleccion.id_eleccion"))
    id_candidato: Mapped[int] = mapped_column(ForeignKey("candidato.id_candidato"))
    numero_candidato: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(20), default="inscrito")

    eleccion: Mapped[Eleccion] = relationship(back_populates="inscripciones")
    candidato: Mapped[Candidato] = relationship(lazy="joined")


class Participacion(Base):
    __tablename__ = "participacion"
    __table_args__ = (UniqueConstraint("id_votante", "id_eleccion"),)
    id_participacion: Mapped[int] = mapped_column(primary_key=True)
    id_votante: Mapped[int] = mapped_column(ForeignKey("votante.id_votante"))
    id_eleccion: Mapped[int] = mapped_column(ForeignKey("eleccion.id_eleccion"))
    fecha_hora: Mapped[datetime] = mapped_column(Fecha)


class Voto(Base):
    """Voto anónimo: no tiene llave foránea hacia el votante."""
    __tablename__ = "voto"
    id_voto: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_eleccion: Mapped[int] = mapped_column(ForeignKey("eleccion.id_eleccion"))
    voto_cifrado: Mapped[bytes] = mapped_column(LargeBinary)
    # Solo se guarda la hora (sin minutos) para dificultar correlaciones por tiempo con PARTICIPACION.
    fecha_hora: Mapped[datetime] = mapped_column(Fecha)
    hash_voto: Mapped[str] = mapped_column(String(64))
    codigo_hash: Mapped[str] = mapped_column(String(64), unique=True)
    firma: Mapped[bytes] = mapped_column(LargeBinary)


class Resultado(Base):
    __tablename__ = "resultado"
    __table_args__ = (UniqueConstraint("id_eleccion", "id_candidato"),)
    id_resultado: Mapped[int] = mapped_column(primary_key=True)
    id_eleccion: Mapped[int] = mapped_column(ForeignKey("eleccion.id_eleccion"))
    id_candidato: Mapped[int] = mapped_column(ForeignKey("candidato.id_candidato"))
    votos: Mapped[int] = mapped_column(Integer)


class ClaveSistema(Base):
    __tablename__ = "clave_sistema"
    id_clave: Mapped[int] = mapped_column(primary_key=True)
    proposito: Mapped[str] = mapped_column(String(30), unique=True)
    clave_publica: Mapped[bytes] = mapped_column(LargeBinary)
    clave_privada: Mapped[bytes] = mapped_column(LargeBinary)
    fecha_creacion: Mapped[datetime] = mapped_column(Fecha, server_default=func.now())


class Respaldo(Base):
    __tablename__ = "respaldo"
    id_respaldo: Mapped[int] = mapped_column(primary_key=True)
    archivo: Mapped[str] = mapped_column(String(255))
    fecha: Mapped[datetime] = mapped_column(Fecha)
    tamano: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))
    firma: Mapped[bytes] = mapped_column(LargeBinary)
    automatico: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_por: Mapped[str] = mapped_column(String(150))
