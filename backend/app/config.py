"""Configuración de la aplicación, leída de variables de entorno o del archivo .env."""
import base64
import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
log = logging.getLogger("votoseguro")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="VOTOSEGURO_", extra="ignore")

    database_url: str = "postgresql+psycopg://votoseguro:votoseguro@localhost:5432/votoseguro"
    # Clave maestra (32 bytes en base64). Envuelve las llaves privadas ECC guardadas en la BD.
    master_key: str | None = None
    cors_origins: list[str] = ["http://localhost:5173"]
    # Permite además los dominios que cumplan esta expresión (p. ej. las vistas previas de Vercel).
    cors_origen_regex: str | None = None
    zona_horaria: str = "America/Bogota"

    # Biometría: distancia euclidiana máxima entre descriptores faciales (face-api, 128-d).
    umbral_biometrico: float = 0.5
    max_intentos_biometricos: int = 5
    max_intentos_login: int = 5

    # Cédula: la foto impresa suele ser vieja y pequeña, por eso el umbral es más tolerante que el del rostro.
    umbral_cedula: float = 0.6
    # Lee el número de la cédula con Tesseract. Se puede desactivar en desarrollo si no está instalado.
    verificar_numero_cedula: bool = True
    max_mb_cedula: int = 5

    # Duración de los tokens (minutos).
    minutos_token_flujo: int = 15
    minutos_token_votante: int = 30
    minutos_token_admin: int = 480

    # Tareas automáticas.
    segundos_ciclo_monitor: int = 20
    minutos_respaldo_automatico: int = 60
    directorio_respaldos: Path = BASE_DIR / "respaldos"
    directorio_logs: Path = BASE_DIR / "logs"

    # Datos iniciales.
    admin_correo: str = "admin@votoseguro.gov.co"
    admin_password: str = "Admin2026*"
    sembrar_datos_demo: bool = True

    @field_validator("database_url")
    @classmethod
    def driver_psycopg(cls, v: str) -> str:
        # Render y otros proveedores entregan "postgres://" o "postgresql://"; SQLAlchemy necesita el driver psycopg 3.
        for prefijo in ("postgres://", "postgresql://"):
            if v.startswith(prefijo):
                return "postgresql+psycopg://" + v[len(prefijo):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_master_key() -> bytes:
    """Devuelve la clave maestra. En desarrollo la genera y la guarda en backend/.master_key."""
    settings = get_settings()
    if settings.master_key:
        key = base64.b64decode(settings.master_key)
    else:
        path = BASE_DIR / ".master_key"
        if path.exists():
            key = base64.b64decode(path.read_text().strip())
        else:
            key = secrets.token_bytes(32)
            path.write_text(base64.b64encode(key).decode())
            os.chmod(path, 0o600)
            log.warning("Clave maestra generada en %s. En producción use VOTOSEGURO_MASTER_KEY.", path)
    if len(key) != 32:
        raise ValueError("La clave maestra debe tener exactamente 32 bytes")
    return key
