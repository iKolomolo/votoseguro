"""Administración: sesión, cuentas, tablero, supervisión, auditoría, respaldos y votantes."""
import time
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from ..config import get_settings
from ..models import Auditoria, Biometria, DocumentoIdentidad, Eleccion, Respaldo, Rol, Usuario, Votante
from ..seguridad import (
    DB, Gestor, SuperAdmin, UsuarioActual, crear_token, hash_password, ip_cliente, verificar_password,
)
from ..servicios import auditoria, documento, monitor, respaldos
from ..servicios.consultas import campo_persona, eleccion_dict, total_habilitados, total_participacion
from ..servicios.elecciones import estado_calculado

router = APIRouter(prefix="/api/admin", tags=["administración"])

CORREO = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def usuario_dict(u: Usuario) -> dict:
    return {"id_usuario": u.id_usuario, "correo": u.correo, "nombre": u.nombre_usuario, "rol": u.rol.nombre,
            "estado": u.estado, "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None}


class Login(BaseModel):
    correo: str = Field(max_length=150)
    password: str = Field(max_length=200)


@router.post("/login")
def login(datos: Login, db: DB, request: Request):
    ip = ip_cliente(request)
    usuario = db.scalar(select(Usuario).where(Usuario.correo == datos.correo.strip().lower()))
    if usuario is not None and usuario.estado == "bloqueado":
        auditoria.registrar(db, "LOGIN", actor=datos.correo, ip=ip, resultado="bloqueado")
        raise HTTPException(status.HTTP_423_LOCKED, "Cuenta bloqueada. Contacte al superadministrador.")
    if usuario is None or usuario.estado != "activo" or not verificar_password(usuario.password, datos.password):
        if usuario is not None:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= get_settings().max_intentos_login:
                usuario.estado = "bloqueado"
        auditoria.registrar(db, "LOGIN", actor=datos.correo[:150], ip=ip, resultado="rechazado", commit=False)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    usuario.intentos_fallidos = 0
    usuario.ultimo_acceso = datetime.now(UTC)
    auditoria.registrar(db, "LOGIN", actor=usuario.correo, id_usuario=usuario.id_usuario, ip=ip, commit=False)
    db.commit()
    token = crear_token(str(usuario.id_usuario), "admin", get_settings().minutos_token_admin, rol=usuario.rol.nombre)
    return {"token": token, "usuario": usuario_dict(usuario)}


@router.get("/yo")
def yo(usuario: UsuarioActual):
    return usuario_dict(usuario)


class CambioPassword(BaseModel):
    actual: str
    nueva: str = Field(min_length=10, max_length=200)


@router.post("/yo/password")
def cambiar_password(datos: CambioPassword, usuario: UsuarioActual, db: DB, request: Request):
    if not verificar_password(usuario.password, datos.actual):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    usuario.password = hash_password(datos.nueva)
    auditoria.registrar(db, "CAMBIAR_PASSWORD", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), commit=False)
    db.commit()
    return {"ok": True}


# ---------- Cuentas del equipo electoral (RQF17) ----------

@router.get("/roles")
def roles(_: UsuarioActual, db: DB):
    return [{"id_rol": r.id_rol, "nombre": r.nombre, "descripcion": r.descripcion} for r in db.scalars(select(Rol))]


@router.get("/usuarios")
def usuarios(_: SuperAdmin, db: DB):
    return [usuario_dict(u) for u in db.scalars(select(Usuario).order_by(Usuario.id_usuario))]


class NuevoUsuario(BaseModel):
    correo: str = Field(pattern=CORREO, max_length=150)
    nombre: str = Field(min_length=3, max_length=80)
    rol: str
    password: str = Field(min_length=10, max_length=200)


def _rol(db, nombre: str) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.nombre == nombre))
    if rol is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rol inexistente")
    return rol


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: NuevoUsuario, actual: SuperAdmin, db: DB, request: Request):
    correo = datos.correo.strip().lower()
    if db.scalar(select(Usuario.id_usuario).where(Usuario.correo == correo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")
    usuario = Usuario(correo=correo, nombre_usuario=datos.nombre, rol=_rol(db, datos.rol),
                      password=hash_password(datos.password))
    db.add(usuario)
    auditoria.registrar(db, "CREAR_USUARIO", actor=actual.correo, id_usuario=actual.id_usuario,
                        ip=ip_cliente(request), descripcion=f"{correo} ({datos.rol})", commit=False)
    db.commit()
    return usuario_dict(usuario)


class EdicionUsuario(BaseModel):
    rol: str | None = None
    estado: Literal["activo", "inactivo", "bloqueado"] | None = None
    password: str | None = Field(default=None, min_length=10, max_length=200)


@router.patch("/usuarios/{id_usuario}")
def editar_usuario(id_usuario: int, datos: EdicionUsuario, actual: SuperAdmin, db: DB, request: Request):
    usuario = db.get(Usuario, id_usuario)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    if usuario.id_usuario == actual.id_usuario and (datos.estado not in (None, "activo") or datos.rol):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puede desactivar ni cambiar el rol de su propia cuenta")
    cambios = []
    if datos.rol:
        usuario.rol = _rol(db, datos.rol)
        cambios.append(f"rol={datos.rol}")
    if datos.estado:
        usuario.estado = datos.estado
        if datos.estado == "activo":
            usuario.intentos_fallidos = 0
        cambios.append(f"estado={datos.estado}")
    if datos.password:
        usuario.password = hash_password(datos.password)
        cambios.append("contraseña restablecida")
    auditoria.registrar(db, "EDITAR_USUARIO", actor=actual.correo, id_usuario=actual.id_usuario,
                        ip=ip_cliente(request), descripcion=f"{usuario.correo}: {', '.join(cambios)}", commit=False)
    db.commit()
    return usuario_dict(usuario)


# ---------- Tablero y supervisión (RQF29, RQF32) ----------

def _actividad(db, limite: int) -> list[dict]:
    return [{
        "id": a.id_auditoria, "accion": a.accion, "descripcion": a.descripcion, "actor": a.actor,
        "fecha": a.fecha_hora.isoformat(), "resultado": a.resultado, "ip": a.direccion_ip, "hash": a.hash,
    } for a in db.scalars(select(Auditoria).order_by(Auditoria.id_auditoria.desc()).limit(limite))]


def _estado_sistema(db) -> list[dict]:
    inicio = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latencia = (time.perf_counter() - inicio) * 1000
        bd = {"nombre": "Base de datos", "ok": True, "valor": "En línea"}
    except Exception:
        latencia = None
        bd = {"nombre": "Base de datos", "ok": False, "valor": "Sin conexión"}
    ultimo = db.scalar(select(Respaldo).order_by(Respaldo.fecha.desc()).limit(1))
    if ultimo:
        minutos = int((datetime.now(UTC) - ultimo.fecha).total_seconds() // 60)
        texto = f"Hace {minutos} min" if minutos < 120 else f"Hace {minutos // 60} h"
        respaldo = {"nombre": "Respaldo automático", "ok": minutos <= 2 * get_settings().minutos_respaldo_automatico,
                    "valor": texto}
    else:
        respaldo = {"nombre": "Respaldo automático", "ok": False, "valor": "Sin respaldos"}
    activos = monitor.votantes_activos()
    return [
        {"nombre": "Servidor de votación", "ok": True,
         "valor": f"{latencia:.1f} ms" if latencia is not None else "—"},
        bd,
        {"nombre": "Cifrado ECC P-256", "ok": True, "valor": "Activo"},
        respaldo,
        {"nombre": "Usuarios simultáneos", "ok": activos < 100, "valor": f"{activos}/100", "alerta": activos >= 80},
    ]


@router.get("/dashboard")
def dashboard(_: UsuarioActual, db: DB):
    todas = list(db.scalars(select(Eleccion).where(Eleccion.archivada.is_(False)).order_by(Eleccion.fecha_inicio)))
    activa = next((e for e in todas if estado_calculado(e) == "activa"), None)
    proxima = next((e for e in todas if estado_calculado(e) == "programada"), None)
    principal = activa or proxima
    habilitados = total_habilitados(db)
    votos = total_participacion(db, principal.id_eleccion) if principal else 0
    return {
        "eleccion": eleccion_dict(db, principal) if principal else None,
        "votos_emitidos": votos,
        "habilitados": habilitados,
        "participacion": round(100 * votos / habilitados, 1) if habilitados else 0.0,
        "votantes_activos": monitor.votantes_activos(),
        "disponibilidad": monitor.disponibilidad_ultima_hora(),
        "sistema": _estado_sistema(db),
        "actividad": _actividad(db, 5),
    }


@router.get("/monitor")
def supervisar(_: UsuarioActual, db: DB):
    return {**monitor.resumen(), "sistema": _estado_sistema(db)}


# ---------- Auditoría (RQF25) ----------

@router.get("/auditoria")
def listar_auditoria(_: UsuarioActual, db: DB, limite: int = 100, accion: str | None = None):
    consulta = select(Auditoria).order_by(Auditoria.id_auditoria.desc()).limit(min(limite, 500))
    if accion:
        consulta = consulta.where(Auditoria.accion == accion)
    return [{
        "id": a.id_auditoria, "accion": a.accion, "descripcion": a.descripcion, "actor": a.actor,
        "fecha": a.fecha_hora.isoformat(), "resultado": a.resultado, "ip": a.direccion_ip, "hash": a.hash,
    } for a in db.scalars(consulta)]


@router.get("/auditoria/verificar")
def verificar_auditoria(_: UsuarioActual, db: DB):
    return auditoria.verificar_cadena(db)


# ---------- Respaldos (RQF30, RQF31) ----------

def _respaldo_dict(db, r: Respaldo) -> dict:
    valido, _ = respaldos.verificar(db, r)
    return {"id_respaldo": r.id_respaldo, "archivo": r.archivo, "fecha": r.fecha.isoformat(), "tamano": r.tamano,
            "hash": r.hash, "automatico": r.automatico, "creado_por": r.creado_por, "valido": valido}


@router.get("/respaldos")
def listar_respaldos(_: UsuarioActual, db: DB):
    return [_respaldo_dict(db, r) for r in db.scalars(select(Respaldo).order_by(Respaldo.fecha.desc()).limit(50))]


@router.post("/respaldos", status_code=status.HTTP_201_CREATED)
def crear_respaldo(usuario: Gestor, db: DB):
    return _respaldo_dict(db, respaldos.crear(db, creado_por=usuario.correo))


@router.post("/respaldos/{id_respaldo}/restaurar")
def restaurar_respaldo(id_respaldo: int, usuario: SuperAdmin, db: DB, request: Request):
    respaldo = db.get(Respaldo, id_respaldo)
    if respaldo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Respaldo no encontrado")
    try:
        respaldos.restaurar(db, respaldo, actor=usuario.correo, ip=ip_cliente(request))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    return {"ok": True}


# ---------- Votantes (gestión del censo, Figura 10) ----------

def _enmascarar(documento: str) -> str:
    return "•" * max(len(documento) - 4, 0) + documento[-4:]


@router.get("/votantes")
def listar_votantes(_: UsuarioActual, db: DB):
    con_biometria = set(db.scalars(select(Biometria.id_persona).where(Biometria.estado == "activa")))
    con_cedula = set(db.scalars(select(DocumentoIdentidad.id_persona)))
    salida = []
    for v in db.scalars(select(Votante).order_by(Votante.id_votante.desc())):
        p = v.persona
        salida.append({
            "id_votante": v.id_votante,
            "nombre": f"{campo_persona(db, p, 'nombres')} {campo_persona(db, p, 'apellidos')}",
            "documento": f"{p.tipo_documento} {_enmascarar(campo_persona(db, p, 'documento'))}",
            "estado": v.estado_habilitacion, "biometria": p.id_persona in con_biometria,
            "cedula": p.id_persona in con_cedula,
            "fecha_registro": p.fecha_registro.isoformat() if p.fecha_registro else None,
        })
    return salida


class EstadoVotante(BaseModel):
    estado: Literal["habilitado", "no_habilitado", "sancionado", "bloqueado"]


@router.patch("/votantes/{id_votante}")
def cambiar_estado_votante(id_votante: int, datos: EstadoVotante, usuario: Gestor, db: DB, request: Request):
    votante = db.get(Votante, id_votante)
    if votante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votante no encontrado")
    votante.estado_habilitacion = datos.estado
    if datos.estado == "habilitado":
        votante.intentos_biometricos = 0
        votante.fecha_habilitacion = datetime.now(UTC)
    auditoria.registrar(db, "CAMBIAR_ESTADO_VOTANTE", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"Votante #{id_votante} -> {datos.estado}", commit=False)
    db.commit()
    return {"ok": True}


@router.post("/votantes/{id_votante}/revocar-biometria")
def revocar_biometria(id_votante: int, usuario: Gestor, db: DB, request: Request):
    """Plantilla cancelable: se elimina y el votante debe volver a enrolarse con una semilla nueva."""
    votante = db.get(Votante, id_votante)
    if votante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Votante no encontrado")
    # También se borra la cédula: al volver a enrolarse debe presentarla de nuevo.
    for modelo in (Biometria, DocumentoIdentidad):
        fila = db.scalar(select(modelo).where(modelo.id_persona == votante.id_persona))
        if fila is not None:
            db.delete(fila)
    auditoria.registrar(db, "REVOCAR_BIOMETRIA", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"Votante #{id_votante}", commit=False)
    db.commit()
    return {"ok": True}


@router.get("/votantes/{id_votante}/cedula")
def ver_cedula(id_votante: int, usuario: SuperAdmin, db: DB, request: Request):
    """Imagen de la cédula presentada al enrolarse. Solo el superadministrador, y cada consulta queda auditada."""
    votante = db.get(Votante, id_votante)
    fila = None if votante is None else db.scalar(
        select(DocumentoIdentidad).where(DocumentoIdentidad.id_persona == votante.id_persona))
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El votante no tiene cédula registrada")
    imagen, _ = documento.descifrar(db, fila)
    auditoria.registrar(db, "VER_CEDULA", actor=usuario.correo, id_usuario=usuario.id_usuario,
                        ip=ip_cliente(request), descripcion=f"Votante #{id_votante}")
    return Response(imagen, media_type=fila.imagen_tipo, headers={"Cache-Control": "no-store"})
