"""Criptografía de curva elíptica (NIST P-256).

- ECIES: cifrado híbrido. Se genera un par efímero, se acuerda un secreto con ECDH contra la llave
  pública del destinatario, se deriva una clave AES-256 con HKDF-SHA256 y se cifra con AES-GCM.
  Formato: pub_efimera (65 bytes, sin comprimir) || nonce (12 bytes) || texto_cifrado + tag (16 bytes).
- ECDSA (SHA-256): firma de comprobantes, respaldos y registros de auditoría.
- Envoltura de llaves privadas con la clave maestra (AES-256-GCM).
- Índice ciego (HMAC-SHA256) para buscar documentos sin guardarlos en claro.
"""
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CURVA = ec.SECP256R1()
NOMBRE_CURVA = "P-256"
_INFO_ECIES = b"votoseguro-ecies-v1"
_LARGO_PUB = 65
_LARGO_NONCE = 12


def generar_par() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(CURVA)


def exportar_publica(llave: ec.EllipticCurvePublicKey) -> bytes:
    return llave.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def importar_publica(der: bytes) -> ec.EllipticCurvePublicKey:
    llave = serialization.load_der_public_key(der)
    if not isinstance(llave, ec.EllipticCurvePublicKey):
        raise ValueError("La llave no es de curva elíptica")
    return llave


def publica_pem(llave: ec.EllipticCurvePublicKey) -> str:
    return llave.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def _derivar(secreto: bytes, largo: int, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=largo, salt=None, info=info).derive(secreto)


def cifrar(publica: ec.EllipticCurvePublicKey, datos: bytes, contexto: bytes = b"") -> bytes:
    """Cifra `datos` para el dueño de `publica`. `contexto` se autentica (AAD) pero no se cifra."""
    efimera = ec.generate_private_key(CURVA)
    compartido = efimera.exchange(ec.ECDH(), publica)
    pub_efimera = efimera.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    clave = _derivar(compartido, 32, _INFO_ECIES + pub_efimera)
    nonce = os.urandom(_LARGO_NONCE)
    return pub_efimera + nonce + AESGCM(clave).encrypt(nonce, datos, contexto)


def descifrar(privada: ec.EllipticCurvePrivateKey, paquete: bytes, contexto: bytes = b"") -> bytes:
    """Descifra un paquete ECIES. Lanza InvalidTag si fue alterado o el contexto no coincide."""
    pub_efimera = paquete[:_LARGO_PUB]
    nonce = paquete[_LARGO_PUB:_LARGO_PUB + _LARGO_NONCE]
    cuerpo = paquete[_LARGO_PUB + _LARGO_NONCE:]
    efimera = ec.EllipticCurvePublicKey.from_encoded_point(CURVA, pub_efimera)
    compartido = privada.exchange(ec.ECDH(), efimera)
    clave = _derivar(compartido, 32, _INFO_ECIES + pub_efimera)
    return AESGCM(clave).decrypt(nonce, cuerpo, contexto)


def firmar(privada: ec.EllipticCurvePrivateKey, datos: bytes) -> bytes:
    return privada.sign(datos, ec.ECDSA(hashes.SHA256()))


def verificar_firma(publica: ec.EllipticCurvePublicKey, firma: bytes, datos: bytes) -> bool:
    try:
        publica.verify(firma, datos, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


def envolver_privada(privada: ec.EllipticCurvePrivateKey, clave_maestra: bytes, contexto: bytes) -> bytes:
    der = privada.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    nonce = os.urandom(_LARGO_NONCE)
    return nonce + AESGCM(clave_maestra).encrypt(nonce, der, contexto)


def desenvolver_privada(envuelta: bytes, clave_maestra: bytes, contexto: bytes) -> ec.EllipticCurvePrivateKey:
    der = AESGCM(clave_maestra).decrypt(envuelta[:_LARGO_NONCE], envuelta[_LARGO_NONCE:], contexto)
    llave = serialization.load_der_private_key(der, password=None)
    if not isinstance(llave, ec.EllipticCurvePrivateKey):
        raise ValueError("La llave no es de curva elíptica")
    return llave


def sub_clave(clave_maestra: bytes, proposito: str) -> bytes:
    """Deriva una clave simétrica independiente para un propósito (JWT, índice ciego...)."""
    return _derivar(clave_maestra, 32, b"votoseguro-subclave:" + proposito.encode())


def indice_ciego(clave: bytes, valor: str) -> str:
    return hmac.new(clave, valor.strip().upper().encode(), hashlib.sha256).hexdigest()


def sha256_hex(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()
