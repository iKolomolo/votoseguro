"""Punto de entrada de la API de VotoSeguro."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from .config import BASE_DIR, get_settings
from .crypto import llavero
from .db import SessionLocal, crear_esquema
from .models import Respaldo
from .rutas import admin, admin_elecciones, publico, registraduria, votante
from .semilla import sembrar
from .servicios import elecciones, monitor, respaldos, retencion

settings = get_settings()
settings.directorio_logs.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(),
              RotatingFileHandler(settings.directorio_logs / "votoseguro.log", maxBytes=2_000_000, backupCount=5)],
)
log = logging.getLogger("votoseguro")


def _ciclo() -> None:
    """Supervisión periódica: salud de la BD, apertura/cierre automático y respaldo automático."""
    with SessionLocal() as db:
        inicio = time.perf_counter()
        try:
            db.execute(text("SELECT 1"))
            monitor.registrar_chequeo(True, (time.perf_counter() - inicio) * 1000)
        except Exception as e:
            monitor.registrar_chequeo(False, None)
            monitor.registrar_error(f"BD no disponible: {e}")
            return
        for cambio in elecciones.sincronizar_estados(db):
            log.info("Cambio de estado: %s", cambio)
        hecho = retencion.aplicar(db)
        if any(hecho.values()):
            log.warning("Retención aplicada: %s", hecho)
        ultimo = db.scalar(select(Respaldo.fecha).order_by(Respaldo.fecha.desc()).limit(1))
        if ultimo is None or datetime.now(UTC) - ultimo >= timedelta(minutes=settings.minutos_respaldo_automatico):
            respaldos.crear(db, creado_por="sistema", automatico=True)


async def _bucle() -> None:
    while True:
        try:
            await asyncio.to_thread(_ciclo)
        except Exception as e:  # el bucle no debe detenerse por un fallo puntual
            log.exception("Error en el ciclo de supervisión")
            monitor.registrar_error(f"Ciclo de supervisión: {e}")
        await asyncio.sleep(settings.segundos_ciclo_monitor)


@asynccontextmanager
async def lifespan(_: FastAPI):
    crear_esquema()
    with SessionLocal() as db:
        llavero.inicializar(db)
        sembrar(db)
        elecciones.migrar_anonimato(db)
    tarea = asyncio.create_task(_bucle())
    yield
    tarea.cancel()


# La documentación interactiva de la API (/docs, /redoc, /openapi.json) describe todas las rutas: en producción va
# apagada. Para verla en desarrollo: VOTOSEGURO_DOCUMENTACION_API=true.
_docs = settings.documentacion_api
app = FastAPI(title="VotoSeguro API", version="1.0.0", lifespan=lifespan,
              description="Prototipo de votación electrónica con ECC P-256 y plantilla biométrica cancelable.",
              docs_url="/docs" if _docs else None, redoc_url="/redoc" if _docs else None,
              openapi_url="/openapi.json" if _docs else None)

# Política de contenido del sitio: solo código, estilos, imágenes y modelos del mismo origen. Los estilos en línea
# los usa React (atributo style); blob:/data: son las vistas previas de la cédula y las fotos de los candidatos.
CSP_SITIO = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
             "media-src 'self' blob:; connect-src 'self'; font-src 'self'; worker-src 'self' blob:; object-src 'none'; "
             "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
CSP_API = "default-src 'none'; frame-ancestors 'none'"
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_origin_regex=settings.cors_origen_regex,
                   allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    respuesta.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    respuesta.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    # HSTS: los navegadores solo lo aplican sobre HTTPS (Render); en http://localhost lo ignoran.
    respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        respuesta.headers.setdefault("Cache-Control", "no-store")
        respuesta.headers.setdefault("Content-Security-Policy", CSP_API)
    elif not request.url.path.startswith(("/docs", "/redoc")):
        respuesta.headers.setdefault("Content-Security-Policy", CSP_SITIO)
    return respuesta


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception):
    log.exception("Error no controlado en %s %s", request.method, request.url.path)
    monitor.registrar_error(f"{request.method} {request.url.path}: {type(exc).__name__}")
    return JSONResponse({"detail": "Error interno del servidor"}, status_code=500)


for modulo in (votante, registraduria, publico, admin, admin_elecciones):
    app.include_router(modulo.router)


@app.get("/api/salud")
def salud():
    return {"estado": "ok", "hora": datetime.now(UTC).isoformat()}


# Si existe el build del frontend, se sirve desde la misma aplicación (una sola URL en producción).
_DIST = BASE_DIR.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")
    if (_DIST / "models").exists():
        app.mount("/models", StaticFiles(directory=_DIST / "models"), name="models")

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str):
        if ruta.startswith("api/"):
            return JSONResponse({"detail": "No encontrado"}, status_code=404)
        archivo = (_DIST / ruta).resolve()
        if ruta and archivo.is_file() and archivo.is_relative_to(_DIST):
            return FileResponse(archivo)
        return FileResponse(_DIST / "index.html")
