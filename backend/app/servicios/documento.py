"""Verificación de la cédula por OCR (Tesseract): número, nombres, apellidos y fecha de nacimiento.

Se leen las dos caras. Cédula amarilla: número, apellidos y nombres al frente; fecha de nacimiento atrás. Cédula
digital: todo al frente y, atrás, la zona MRZ (tres líneas con "<<") con apellidos, nombres y fecha. Lo que escribe el
ciudadano debe coincidir con lo que dice su cédula.

Las imágenes no se guardan en ningún lado (Decreto 1377 de 2013, arts. 4 y 11): se procesan en memoria durante la
petición y solo queda su huella SHA-256 como evidencia (ver servicios/inscripcion.py). Del reverso solo se leen esos
datos: la huella dactilar y los demás datos impresos no se analizan.
"""
import hashlib
import io
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache

from PIL import Image, ImageOps, UnidentifiedImageError

ANCHO_OCR = 2000
# Versión del procedimiento de verificación, guardada con cada evidencia.
VERSION = "ocr-cotejo-2"
# Series de al menos 5 caracteres que pueden llevar puntos, espacios o guiones entre grupos (nunca saltos de
# línea: si no, el número se pegaría a la línea siguiente).
_SERIE = re.compile(r"[0-9A-Z](?:[0-9A-Z]|[. \t-](?=[0-9A-Z])){4,}")


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


@lru_cache
def _idioma() -> str:
    """Español si está instalado (lee la Ñ y las tildes); si no, el inglés que trae Tesseract."""
    import pytesseract
    try:
        return "spa" if "spa" in pytesseract.get_languages(config="") else "eng"
    except Exception:
        return "eng"


def leer_texto(datos: bytes) -> str:
    """Texto que el OCR encontró en una cara de la cédula (dos lecturas combinadas)."""
    try:
        import pytesseract
    except ImportError as e:
        raise OcrNoDisponible("El servidor no tiene instalado el lector de documentos (Tesseract)") from e
    imagen = _preparar(abrir(datos))
    textos = []
    # psm 6: bloque uniforme (conserva las líneas, sirve para las etiquetas y la MRZ); psm 11: texto disperso.
    for psm in (6, 11):
        try:
            textos.append(pytesseract.image_to_string(imagen, lang=_idioma(), config=f"--psm {psm}"))
        except pytesseract.TesseractNotFoundError as e:
            raise OcrNoDisponible("El servidor no tiene instalado el lector de documentos (Tesseract)") from e
    return "\n".join(textos)


# ---------- Número ----------

def series(texto: str) -> set[str]:
    """Series alfanuméricas de al menos 5 caracteres (los números de documento), ya normalizadas."""
    return {c for c in (normalizar(m.group()) for m in _SERIE.finditer(texto.upper())) if len(c) >= 5}


def coincide(numero: str, candidatos: set[str]) -> bool:
    """El número escrito debe aparecer completo en alguna serie leída. El OCR puede pegarle palabras vecinas
    ("NUMERO1020304050"), pero no más dígitos: así un prefijo del número real no se acepta."""
    patron = re.compile(rf"(?<!\d){re.escape(normalizar(numero))}(?!\d)")
    return bool(normalizar(numero)) and any(patron.search(c) for c in candidatos)


# ---------- Nombres y apellidos ----------

# Etiquetas impresas y partículas que no cuentan como palabras del nombre ("DE LA TORRE" -> "TORRE").
_ETIQUETAS = {"APELLIDOS", "APELLIDO", "SURNAME", "SURNAMES", "NOMBRES", "NOMBRE", "NAMES", "NAME", "GIVEN"}
_PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E"}


def _plano(texto: str) -> str:
    """Mayúsculas sin tildes; la Ñ queda como N."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _palabras(texto: str) -> list[str]:
    return [p for p in re.findall(r"[A-Z]{2,}", _plano(texto)) if p not in _ETIQUETAS | _PARTICULAS]


def _parecidas(a: str, b: str) -> bool:
    """Tolera un carácter mal leído por el OCR en palabras de 5 letras o más."""
    return a == b or (min(len(a), len(b)) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.8)


def _mismas(escritas: list[str], leidas: list[str]) -> bool:
    """Mismas palabras, ni más ni menos (en cualquier orden, con tolerancia al OCR)."""
    pendientes = list(leidas)
    for palabra in escritas:
        par = next((x for x in pendientes if _parecidas(palabra, x)), None)
        if par is None:
            return False
        pendientes.remove(par)
    return not pendientes


def _mrz(texto: str) -> tuple[list[str], list[str], set[str]]:
    """Apellidos, nombres y fechas de nacimiento de la zona MRZ (reverso de la cédula digital)."""
    apellidos: list[str] = []
    nombres: list[str] = []
    fechas: set[str] = set()
    for linea in _plano(texto).replace("«", "<<").splitlines():
        compacta = re.sub(r"\s", "", linea)
        if m := re.fullmatch(r"([A-Z]+(?:<[A-Z]+)*)<<([A-Z]+(?:<[A-Z]+)*)<*", compacta):
            apellidos = [p for p in m.group(1).split("<") if p not in _PARTICULAS]
            nombres = [p for p in m.group(2).split("<") if p not in _PARTICULAS]
        elif m := re.match(r"(\d{2})(\d{2})(\d{2})\d[MFX<]", compacta):
            anio, mes, dia = (int(x) for x in m.groups())
            siglo = 2000 if anio <= date.today().year % 100 else 1900
            try:
                fechas.add(date(siglo + anio, mes, dia).isoformat())
            except ValueError:
                pass
    return apellidos, nombres, fechas


def _rotulados(texto: str, etiqueta: str) -> list[list[str]]:
    """Palabras de las líneas junto a una etiqueta impresa. En la cédula amarilla el valor va encima de la
    etiqueta; en la digital, en la misma línea o debajo. Se prueban las tres posiciones."""
    lineas = [linea for linea in _plano(texto).splitlines() if linea.strip()]
    candidatos = []
    for i, linea in enumerate(lineas):
        if etiqueta in linea:
            candidatos.append(_palabras(linea))
            for j in (i - 1, i + 1):
                if 0 <= j < len(lineas):
                    candidatos.append(_palabras(lineas[j]))
    return [c for c in candidatos if c]


def nombre_confirmado(escrito: str, texto: str, etiqueta: str, mrz: list[str]) -> bool:
    """Si se ubica el campo en la cédula (por su etiqueta o en la MRZ), debe coincidir completo. Si la foto no
    permite ubicarlo, cada palabra escrita debe aparecer en la cédula."""
    escritas = _palabras(escrito)
    if not escritas:
        return False
    campos = _rotulados(texto, etiqueta) + ([mrz] if mrz else [])
    del_campo = [c for c in campos if any(_parecidas(p, x) for p in escritas for x in c)]
    if del_campo:
        return any(_mismas(escritas, c) for c in del_campo)
    todas = _palabras(texto)
    return all(any(_parecidas(p, x) for x in todas) for p in escritas)


# ---------- Fecha de nacimiento ----------

_MESES = {"ENE": 1, "JAN": 1, "FEB": 2, "MAR": 3, "ABR": 4, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8,
          "AUG": 8, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12, "DEC": 12}
# Confusiones típicas del OCR: letras leídas en lugar de dígitos, y al revés en el mes ("N0V" -> "NOV").
_A_DIGITO = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "T": "1", "Z": "2", "S": "5", "B": "8",
                           "G": "6"})
_A_LETRA = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"})
# Día, mes (tres letras o número) y año, con guiones, barras, puntos o espacios; admite letras confundidas.
# El OCR a veces mete un espacio dentro del día ("2 1-JUL-2004") o una letra de más en el mes ("21-YJUL-2004").
_FECHA = re.compile(r"(?<![0-9A-Z])([0-9] [0-9]|[0-9OQDILTZSBG]{1,2})\s*[-/.,]?\s*([A-Z0-9]{3,4}|[0-9OI]{1,2})\s*"
                    r"[-/.,]?\s*([0-9OQDILTZSBG]{4})(?![0-9])")


def _mes(texto: str) -> int | None:
    if len(texto) <= 2 and texto.translate(_A_DIGITO).isdigit():
        numero = int(texto.translate(_A_DIGITO))
        return numero if 1 <= numero <= 12 else None
    letras = texto.translate(_A_LETRA)
    if letras in _MESES:
        return _MESES[letras]
    # Cuatro letras: una sobra ("YJUL", "JULL"). Vale si quitándola queda exactamente un mes.
    if len(letras) == 4:
        exactos = {_MESES[v] for v in (letras[1:], letras[:3]) if v in _MESES}
        if len(exactos) == 1:
            return exactos.pop()
    # Una letra mal leída ("NQV", "DlC"): el mes más parecido, si no hay empate.
    parecidos = [(SequenceMatcher(None, letras, m).ratio(), n) for m, n in _MESES.items()]
    mejor = max(parecidos)
    return mejor[1] if mejor[0] >= 0.66 and sum(1 for r, n in parecidos if r == mejor[0] and n != mejor[1]) == 0 else None


def _fechas_en(linea: str) -> list[str]:
    encontradas = []
    for dia, mes, anio in _FECHA.findall(linea):
        numero_mes = _mes(mes)
        try:
            if numero_mes:
                encontradas.append(date(int(anio.translate(_A_DIGITO)), numero_mes,
                                        int(dia.replace(" ", "").translate(_A_DIGITO))).isoformat())
        except ValueError:
            pass
    encontradas += [f"{a}-{m}-{d}" for a, m, d in re.findall(r"(\d{4})-(\d{2})-(\d{2})", linea)]
    return encontradas


def fechas(texto: str) -> set[str]:
    """Todas las fechas impresas ("15-MAY-2005", "15 MAY 2005", "15/05/2005", "2005-05-15") y las de la MRZ."""
    return set(_mrz(texto)[2]) | {f for linea in _plano(texto).splitlines() for f in _fechas_en(linea)}


def fechas_de_nacimiento(texto: str) -> set[str]:
    """Fechas de nacimiento de la cédula, sin confundirlas con la de expedición ni la de vencimiento.

    En la cédula amarilla la fecha va a la derecha de "FECHA DE NACIMIENTO" (o en la línea siguiente si el OCR la
    separa); en la digital, junto a "Fecha de nacimiento" y en la MRZ. Si se encuentra la etiqueta, solo cuentan las
    fechas que la acompañan. Si la foto no deja leerla, cuentan las fechas que no sean de expedición o vencimiento.
    """
    lineas = [linea for linea in _plano(texto).splitlines() if linea.strip()]
    rotuladas: set[str] = set()
    for k, linea in enumerate(lineas):
        if "NACIM" in linea and "LUGAR" not in linea:
            despues = linea[linea.index("NACIM"):]
            rotuladas.update(_fechas_en(despues))
            if not _fechas_en(despues) and k + 1 < len(lineas):
                rotuladas.update(_fechas_en(lineas[k + 1]))
    mrz = _mrz(texto)[2]
    if rotuladas or mrz:
        return rotuladas | mrz
    otras: set[str] = set()
    for k, linea in enumerate(lineas):
        vecinas = " ".join(lineas[max(k - 1, 0):k + 2])
        if not re.search(r"EXPEDIC|VENCIM|EXPIRA", vecinas):
            otras.update(_fechas_en(linea))
    return otras


# ---------- Verificación completa ----------

CAMPOS = {"numero": "número de documento", "nombres": "nombres", "apellidos": "apellidos",
          "fecha_nacimiento": "fecha de nacimiento"}


def verificar(texto: str, datos: dict) -> dict[str, bool]:
    """Qué datos escritos confirma la cédula (texto de ambas caras)."""
    apellidos_mrz, nombres_mrz, _ = _mrz(texto)
    return {
        "numero": coincide(datos["documento"], series(texto)),
        "nombres": nombre_confirmado(datos["nombres"], texto, "NOMBRE", nombres_mrz),
        "apellidos": nombre_confirmado(datos["apellidos"], texto, "APELLIDO", apellidos_mrz),
        "fecha_nacimiento": datos["fecha_nacimiento"] in fechas_de_nacimiento(texto),
    }


def huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()
