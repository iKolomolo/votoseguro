"""Métricas de supervisión de la jornada (RQF32, RQNF03, RQNF21). Se guardan en memoria del proceso."""
import threading
import time
from collections import deque
from datetime import UTC, datetime

_INICIO = datetime.now(UTC)
_VENTANA_ACTIVOS = 15 * 60  # segundos
_lock = threading.Lock()
_votantes_activos: dict[int, float] = {}
_chequeos: deque[tuple[float, bool]] = deque(maxlen=2000)
_errores: deque[tuple[float, str]] = deque(maxlen=200)
_latencia_db_ms: float | None = None


def marcar_votante_activo(id_votante: int) -> None:
    with _lock:
        _votantes_activos[id_votante] = time.time()


def votantes_activos() -> int:
    limite = time.time() - _VENTANA_ACTIVOS
    with _lock:
        for k in [k for k, t in _votantes_activos.items() if t < limite]:
            del _votantes_activos[k]
        return len(_votantes_activos)


def registrar_chequeo(ok: bool, latencia_ms: float | None) -> None:
    global _latencia_db_ms
    with _lock:
        _chequeos.append((time.time(), ok))
        if latencia_ms is not None:
            _latencia_db_ms = latencia_ms


def registrar_error(mensaje: str) -> None:
    with _lock:
        _errores.append((time.time(), mensaje[:300]))


def disponibilidad_ultima_hora() -> float | None:
    limite = time.time() - 3600
    with _lock:
        recientes = [ok for t, ok in _chequeos if t >= limite]
    if not recientes:
        return None
    return round(100 * sum(recientes) / len(recientes), 1)


def resumen() -> dict:
    with _lock:
        errores = [{"fecha": datetime.fromtimestamp(t, UTC).isoformat(), "mensaje": m} for t, m in _errores]
        latencia = _latencia_db_ms
    return {
        "inicio": _INICIO.isoformat(),
        "segundos_activo": int((datetime.now(UTC) - _INICIO).total_seconds()),
        "latencia_db_ms": None if latencia is None else round(latencia, 1),
        "disponibilidad": disponibilidad_ultima_hora(),
        "votantes_activos": votantes_activos(),
        "errores_recientes": errores[-20:][::-1],
        "total_errores": len(errores),
    }
