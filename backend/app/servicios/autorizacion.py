"""Autorización para el tratamiento de datos personales (Ley 1581 de 2012, arts. 6, 9 y 12; Decreto 1377 de 2013,
arts. 5 a 8).

El texto vive aquí, con versión y huella SHA-256, para que la prueba de cada autorización diga exactamente qué
leyó el titular. El navegador lo muestra tal cual y devuelve la versión y la huella que aceptó. El marcado
**así** indica negrilla.
"""
import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Autorizacion

VERSION = "1.4"
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]


class AutorizacionInvalida(ValueError):
    pass


@lru_cache
def texto() -> dict:
    s = get_settings()
    fin = f"{s.fin_piloto.day} de {_MESES[s.fin_piloto.month - 1]} de {s.fin_piloto.year}"
    contenido = {
        "version": VERSION,
        "titulo": "Autorización para el tratamiento de datos personales",
        "subtitulo": "VotoSeguro — prototipo académico",
        "secciones": [
            {"titulo": "Responsables", "texto": (
                f"{s.responsables}, estudiantes de la Universidad Manuela Beltrán (Bogotá D.C.), autores del trabajo "
                "de grado \"Prototipo de un sistema web de votación electrónica basado en criptografía de curva "
                f"elíptica y plantilla biométrica\". Contacto: {s.correo_privacidad}. Dirección: "
                f"{s.direccion_responsables}. Teléfono: {s.telefono_responsables}.")},
            {"titulo": "Qué es esto", "texto": (
                "VotoSeguro es una **simulación académica**. No pertenece a la Registraduría Nacional del Estado "
                "Civil, no está conectada con ella y **no tiene efectos electorales ni jurídicos**.")},
            {"titulo": "Datos que se recogen", "texto": (
                "Tipo y número de documento, nombres, apellidos, fecha de nacimiento y correo electrónico, y fotos "
                "de las dos caras de su cédula, de las que solo se leen el número, los nombres, los apellidos y la "
                "fecha de nacimiento. Con la segunda casilla, también: la imagen de su rostro impresa en la cédula "
                "y la captura de su rostro con la cámara.")},
            {"titulo": "Datos sensibles", "texto": (
                "La imagen de su rostro y la plantilla biométrica que se obtiene de ella son **datos sensibles** "
                "(Ley 1581 de 2012, art. 5) y **usted no está obligado(a) a entregarlos**. Este piloto existe "
                "precisamente para evaluar la verificación de identidad con el rostro, así que **sin esta "
                "autorización no es posible participar**. Su participación es **totalmente voluntaria**: si decide "
                "no autorizarla, simplemente no participa, sin ninguna consecuencia para usted. Puede revocarla en "
                "cualquier momento; su plantilla se borra de inmediato y, desde ese momento, ya no podrá votar en el "
                "piloto salvo que vuelva a inscribirse.")},
            {"titulo": "Para qué se usan", "lista": [
                "Inscribirlo(a) como votante del piloto y verificar que es mayor de edad.",
                "Comprobar que el número, los nombres, los apellidos y la fecha de nacimiento que escribió coinciden "
                "con su cédula (lectura automática de las fotos de las dos caras).",
                "Comparar su rostro con la foto de la cédula y verificar su identidad cada vez que vote.",
                "Impedir que una persona vote dos veces o se inscriba con dos documentos.",
                "Evaluar el funcionamiento del prototipo con **estadísticas anónimas**.",
            ]},
            {"titulo": "Qué NO se hace", "texto": (
                "Las fotos de su cédula **no se guardan**: se usan en el momento y se descartan. No se analiza la "
                "huella dactilar del reverso ni los demás datos impresos. Su voto **no queda "
                "asociado** a su identidad. Sus datos no se venden, no se comparten con terceros y no se usan para "
                "otros fines.")},
            {"titulo": "Cómo se protegen", "texto": (
                "Todos los datos se guardan cifrados con criptografía de curva elíptica. La plantilla de su rostro es "
                "cancelable: se puede anular y no permite reconstruir su imagen. Solo los responsables del proyecto "
                "acceden al sistema, y sus ingresos y acciones quedan registrados.")},
            {"titulo": "Dónde se alojan", "texto": (
                "En servidores de Render (sistema y base de datos) y Vercel (sitio web), ubicados en **Estados "
                "Unidos**, país que la Superintendencia de Industria y Comercio considera con nivel adecuado de "
                "protección. Estas empresas actúan solo como encargadas del almacenamiento.")},
            {"titulo": "Por cuánto tiempo", "texto": (
                "Su inscripción solo se guarda cuando la termina: si no la completa en "
                f"{s.minutos_inscripcion} minutos, se descarta y no queda ningún dato suyo. Los datos de la cara impresa "
                "en la cédula se usan solo durante la inscripción y no se guardan. Sus datos personales y su plantilla "
                f"biométrica se borran a más tardar el **{fin}**, o antes si usted lo pide. Después de esa fecha solo se conserva durante 3 años una constancia de que "
                "aceptó esta autorización, sin su nombre ni su número de documento legible.")},
            {"titulo": "Sus derechos", "texto": (
                "Conocer, actualizar y rectificar sus datos; pedir prueba de esta autorización; saber cómo se han "
                "usado; **revocar** esta autorización y **pedir que se borren** sus datos en cualquier momento; y "
                "presentar quejas ante la Superintendencia de Industria y Comercio. Puede ejercerlos en **\"Mis datos "
                f"personales\"** o escribiendo a {s.correo_privacidad}. Las consultas se responden en máximo 10 días "
                "hábiles y los reclamos en máximo 15.")},
        ],
        "casillas": {
            "datos": "Autorizo el tratamiento de mis datos personales en los términos anteriores.",
            "biometria": (
                "Autorizo, además, el tratamiento de mis **datos biométricos** (imagen de mi rostro en la cédula y en "
                "la cámara) para verificar mi identidad. Sé que **no estoy obligado(a)** a entregarlos y que el "
                "piloto los necesita: si no los autorizo, no participo, sin ninguna otra consecuencia."),
        },
    }
    contenido["hash"] = hashlib.sha256(json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return contenido



def validar(version: str, huella: str, acepto_datos: bool, acepto_biometria: bool) -> None:
    """Comprueba que el titular aceptó la versión vigente del texto y las dos casillas, que son necesarias para
    participar: el piloto evalúa la verificación con el rostro. Siguen separadas porque la de datos sensibles debe
    ser expresa (Ley 1581, art. 6)."""
    vigente = texto()
    if version != vigente["version"] or huella != vigente["hash"]:
        raise AutorizacionInvalida("El texto de la autorización cambió. Recargue la página y léalo de nuevo.")
    if not acepto_datos:
        raise AutorizacionInvalida("Debe autorizar el tratamiento de sus datos personales para inscribirse.")
    if not acepto_biometria:
        raise AutorizacionInvalida("Para participar en el piloto debe autorizar también sus datos biométricos.")


def registrar(db: Session, id_persona: int, documento_indice: str, acepto_biometria: bool) -> Autorizacion:
    """Guarda la prueba de la autorización (Decreto 1377 art. 8). No hace commit."""
    fila = Autorizacion(
        id_persona=id_persona, documento_indice=documento_indice, version_texto=VERSION, hash_texto=texto()["hash"],
        acepto_datos=True, acepto_biometria=acepto_biometria, fecha=datetime.now(UTC),
    )
    db.add(fila)
    return fila


def vigente(db: Session, id_persona: int) -> Autorizacion | None:
    """La última autorización del titular."""
    return db.scalar(select(Autorizacion).where(Autorizacion.id_persona == id_persona)
                     .order_by(Autorizacion.id_autorizacion.desc()).limit(1))


def revocar_biometria(db: Session, id_persona: int) -> None:
    """Deja constancia de que el titular revocó la autorización biométrica. No hace commit."""
    fila = vigente(db, id_persona)
    if fila is not None and fila.acepto_biometria and fila.revocada_en is None:
        fila.revocada_en = datetime.now(UTC)
        fila.alcance_revocacion = "biometria"
