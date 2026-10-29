"""Las pruebas usan una base SQLite temporal y una clave maestra efímera.

Para correrlas contra PostgreSQL (incluye el trigger de inmutabilidad del voto):
    VOTOSEGURO_TEST_DATABASE_URL=postgresql+psycopg://... pytest
"""
import base64
import os
import secrets
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="votoseguro-test-"))
os.environ["VOTOSEGURO_DATABASE_URL"] = os.environ.get("VOTOSEGURO_TEST_DATABASE_URL", f"sqlite:///{_tmp / 'test.db'}")
os.environ["VOTOSEGURO_MASTER_KEY"] = base64.b64encode(secrets.token_bytes(32)).decode()
os.environ["VOTOSEGURO_DIRECTORIO_RESPALDOS"] = str(_tmp / "respaldos")
os.environ["VOTOSEGURO_DIRECTORIO_LOGS"] = str(_tmp / "logs")
os.environ["VOTOSEGURO_SEMBRAR_DATOS_DEMO"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ADMIN = {"correo": "admin@votoseguro.gov.co", "password": "Admin2026*"}


@pytest.fixture(scope="session")
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(cliente):
    r = cliente.post("/api/admin/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session", autouse=True)
def ocr_simulado():
    """Las pruebas no dependen de Tesseract: la "foto" de la cédula lleva el número en un metadato PNG."""
    from app.servicios import documento

    def leer_numeros(datos):
        return {documento.normalizar(documento.abrir(datos).info.get("numero", ""))} - {""}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(documento, "leer_numeros", leer_numeros)
        yield
