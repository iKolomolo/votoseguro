import random

import pytest
from cryptography.exceptions import InvalidTag

from app.crypto import biometria as bio
from app.crypto import ecc


def test_ecies_ida_y_vuelta():
    privada = ecc.generar_par()
    paquete = ecc.cifrar(privada.public_key(), b"candidato 2", b"eleccion:EL-1")
    assert b"candidato" not in paquete
    assert ecc.descifrar(privada, paquete, b"eleccion:EL-1") == b"candidato 2"


def test_ecies_es_probabilistico():
    """Dos votos iguales producen textos cifrados distintos: no se puede deducir el voto comparándolos."""
    pub = ecc.generar_par().public_key()
    assert ecc.cifrar(pub, b"x") != ecc.cifrar(pub, b"x")


def test_ecies_rechaza_alteraciones_y_otro_contexto():
    privada = ecc.generar_par()
    paquete = bytearray(ecc.cifrar(privada.public_key(), b"voto", b"eleccion:A"))
    with pytest.raises(InvalidTag):
        ecc.descifrar(privada, bytes(paquete), b"eleccion:B")  # voto movido a otra elección
    paquete[-1] ^= 1
    with pytest.raises(InvalidTag):
        ecc.descifrar(privada, bytes(paquete), b"eleccion:A")


def test_ecies_otra_llave_no_descifra():
    paquete = ecc.cifrar(ecc.generar_par().public_key(), b"secreto")
    with pytest.raises(InvalidTag):
        ecc.descifrar(ecc.generar_par(), paquete)


def test_firma_ecdsa():
    privada = ecc.generar_par()
    firma = ecc.firmar(privada, b"mensaje")
    assert ecc.verificar_firma(privada.public_key(), firma, b"mensaje")
    assert not ecc.verificar_firma(privada.public_key(), firma, b"mensaje alterado")


def test_envoltura_de_llave_privada():
    maestra = bytes(32)
    privada = ecc.generar_par()
    envuelta = ecc.envolver_privada(privada, maestra, b"ctx")
    recuperada = ecc.desenvolver_privada(envuelta, maestra, b"ctx")
    assert recuperada.private_numbers() == privada.private_numbers()
    with pytest.raises(InvalidTag):
        ecc.desenvolver_privada(envuelta, bytes([1]) * 32, b"ctx")


def _descriptor(rng):
    return [rng.gauss(0, 0.09) for _ in range(128)]


def test_plantilla_cancelable_conserva_distancias():
    rng = random.Random(7)
    a, b = _descriptor(rng), _descriptor(rng)
    semilla = bio.nueva_semilla()
    ta, tb = bio.transformar(a, semilla), bio.transformar(b, semilla)
    assert ta != a
    assert abs(bio.distancia(ta, tb) - bio.distancia(a, b)) < 1e-9


def test_plantilla_revocada_no_coincide_con_la_anterior():
    """Con una semilla nueva, la plantilla filtrada ya no sirve para suplantar al usuario."""
    rng = random.Random(8)
    rostro = _descriptor(rng)
    vieja = bio.transformar(rostro, bio.nueva_semilla())
    nueva = bio.transformar(rostro, bio.nueva_semilla())
    assert bio.distancia(vieja, nueva) > 0.5


def test_validar_descriptor():
    with pytest.raises(bio.DescriptorInvalido):
        bio.validar_descriptor([0.0] * 127)
    with pytest.raises(bio.DescriptorInvalido):
        bio.validar_descriptor([0.0] * 128)  # norma cero: no es un rostro
    with pytest.raises(bio.DescriptorInvalido):
        bio.validar_descriptor([float("nan")] * 128)
    assert len(bio.validar_descriptor(_descriptor(random.Random(1)))) == 128


def test_indice_ciego_normaliza():
    clave = bytes(32)
    assert ecc.indice_ciego(clave, " abc123 ") == ecc.indice_ciego(clave, "ABC123")
    assert ecc.indice_ciego(clave, "1") != ecc.indice_ciego(bytes([1]) * 32, "1")
