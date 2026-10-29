"""Lectura del número impreso en la cédula con OCR (Tesseract).

El número se lee en el servidor a partir de la misma imagen que se guarda cifrada, así que no depende de lo que
declare el navegador. Las cédulas lo imprimen con puntos ("1.020.304.050"); se normaliza a solo dígitos (o a
letras y dígitos, para pasaportes) antes de comparar con el número que escribió el votante.
"""
import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..crypto import biometria as bio
from ..crypto import ecc, llavero
from ..models import DocumentoIdentidad

ANCHO_OCR = 2000
# Series de al menos 5 caracteres que pueden llevar puntos, espacios o guiones entre grupos.
_SERIE = re.compile(r"[0-9A-Z](?:[0-9A-Z]|[.\s-](?=[0-9A-Z])){4,}")


class ImagenInvalida(ValueError):
    pass


class OcrNoDisponible(RuntimeError):
    pass


def abrir(datos: bytes) -> Image.Image:
    """Abre la imagen, corrige la orientación de la cámara (EXIF) y rechaza archivos que no sean imágenes."""
    try:
        imagen = Image.open(io.BytesIO(datos))
        imagen.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ImagenInvalida("El archivo no es una imagen válida") from e
    if min(imagen.size) < 200:
        raise ImagenInvalida("La imagen es demasiado pequeña; tome la foto más cerca de la cédula")
    return ImageOps.exif_transpose(imagen)


def _preparar(imagen: Image.Image) -> Image.Image:
    gris = ImageOps.grayscale(imagen)
    if gris.width < ANCHO_OCR:
        gris = gris.resize((ANCHO_OCR, round(gris.height * ANCHO_OCR / gris.width)), Image.Resampling.LANCZOS)
    return ImageOps.autocontrast(gris, cutoff=1)


def normalizar(numero: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", numero.upper())


def leer_numeros(datos: bytes) -> set[str]:
    """Devuelve las series alfanuméricas que el OCR encontró en la imagen, ya normalizadas."""
    try:
        import pytesseract
    except ImportError as e:
        raise OcrNoDisponible("El servidor no tiene instalado el lector de documentos (Tesseract)") from e
    imagen = _preparar(abrir(datos))
    candidatos: set[str] = set()
    # psm 11: texto disperso (la cédula tiene campos sueltos); psm 6: bloque uniforme. Se combinan ambos.
    for psm in (11, 6):
        try:
            texto = pytesseract.image_to_string(imagen, config=f"--psm {psm}")
        except pytesseract.TesseractNotFoundError as e:
            raise OcrNoDisponible("El servidor no tiene instalado el lector de documentos (Tesseract)") from e
        candidatos.update(normalizar(m.group()) for m in _SERIE.finditer(texto.upper()))
    return {c for c in candidatos if len(c) >= 5}


def coincide(numero: str, candidatos: set[str]) -> bool:
    """El número escrito debe aparecer completo en alguna serie leída. El OCR puede pegarle palabras vecinas
    ("NUMERO1020304050"), pero no más dígitos: así un prefijo del número real no se acepta."""
    patron = re.compile(rf"(?<!\d){re.escape(normalizar(numero))}(?!\d)")
    return bool(normalizar(numero)) and any(patron.search(c) for c in candidatos)


def _contexto(id_persona: int, campo: str) -> bytes:
    return f"doc:{id_persona}:{campo}".encode()


def guardar(db: Session, fila: DocumentoIdentidad, imagen: bytes, tipo: str, cara: list[float]) -> None:
    """Cifra con ECIES la imagen y el descriptor de la cara impresa (llave del sistema "documento")."""
    pub = llavero.publica(db, "documento")
    fila.imagen = ecc.cifrar(pub, imagen, _contexto(fila.id_persona, "imagen"))
    fila.imagen_tipo = tipo
    fila.descriptor = ecc.cifrar(pub, bio.a_bytes(cara), _contexto(fila.id_persona, "descriptor"))


def descifrar(db: Session, fila: DocumentoIdentidad) -> tuple[bytes, list[float]]:
    privada = llavero.privada(db, "documento")
    imagen = ecc.descifrar(privada, fila.imagen, _contexto(fila.id_persona, "imagen"))
    cara = bio.desde_bytes(ecc.descifrar(privada, fila.descriptor, _contexto(fila.id_persona, "descriptor")))
    return imagen, cara
