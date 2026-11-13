"""Deja la base recién creada con los roles, las llaves del sistema y 3 superadministradores, sin datos demo.

Uso (con Docker, desde la carpeta del proyecto, después de `docker compose down -v`):
    docker compose run --rm -T -e VOTOSEGURO_SEMBRAR_DATOS_DEMO=false app python - < backend/scripts/crear_admins.py
Cada ejecución genera contraseñas nuevas y las imprime una sola vez."""
import secrets

from sqlalchemy import select

from app.crypto import llavero
from app.db import SessionLocal, crear_esquema
from app.models import Rol, Usuario
from app.semilla import ROLES
from app.seguridad import ROL_SUPERADMIN, hash_password
from app.servicios import auditoria

ADMINS = [
    ("Mario Mendoza", "mario.mendoza@votoseguro.local"),
    ("Julieth Riveros", "julieth.riveros@votoseguro.local"),
    ("Nicolas Marcelo", "nicolas.marcelo@votoseguro.local"),
]
# Sin caracteres ambiguos (0/O, 1/l/I) para que se puedan copiar a mano sin errores.
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"

crear_esquema()
with SessionLocal() as db:
    llavero.inicializar(db)
    for nombre, descripcion in ROLES:
        db.add(Rol(nombre=nombre, descripcion=descripcion))
    db.flush()
    rol = db.scalar(select(Rol).where(Rol.nombre == ROL_SUPERADMIN))
    for nombre, correo in ADMINS:
        clave = "".join(secrets.choice(ALFABETO) for _ in range(14)) + "*"
        db.add(Usuario(correo=correo, nombre_usuario=nombre, rol=rol, password=hash_password(clave)))
        print(f"{nombre} | {correo} | {clave}")
    auditoria.registrar(db, "INICIALIZAR_SISTEMA", descripcion="Roles y 3 superadministradores creados", commit=False)
    db.commit()
print("usuarios:", len(db.scalars(select(Usuario)).all()))
