"""Plantilla biométrica cancelable.

El navegador (face-api.js) entrega un descriptor facial de 128 valores. Antes de guardarlo se le
aplica una transformación secreta por usuario (permutación + inversión de signos derivadas de una
semilla aleatoria). La transformación conserva la distancia euclidiana, así que la comparación sigue
funcionando, pero la plantilla guardada no es el descriptor original. Si se filtra, basta con
generar una semilla nueva y volver a enrolar ("revocar" la plantilla), como proponen
Abd El-Rahiem et al. (2022). Tanto la plantilla como la semilla se guardan cifradas con ECIES.
"""
import math
import os
import random
import struct

DIMENSION = 128
_FORMATO = f"<{DIMENSION}f"


class DescriptorInvalido(ValueError):
    pass


def validar_descriptor(valores: list[float]) -> list[float]:
    if len(valores) != DIMENSION:
        raise DescriptorInvalido(f"El descriptor debe tener {DIMENSION} valores")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in valores):
        raise DescriptorInvalido("El descriptor contiene valores no numéricos")
    norma = math.sqrt(sum(v * v for v in valores))
    # Los descriptores de face-api tienen norma cercana a 1; valores muy lejanos indican datos falsos.
    if not 0.3 <= norma <= 3.0:
        raise DescriptorInvalido("El descriptor no parece provenir de un rostro válido")
    return [float(v) for v in valores]


def nueva_semilla() -> bytes:
    return os.urandom(32)


def transformar(descriptor: list[float], semilla: bytes) -> list[float]:
    rng = random.Random(int.from_bytes(semilla, "big"))
    permutacion = list(range(DIMENSION))
    rng.shuffle(permutacion)
    signos = [1.0 if rng.random() < 0.5 else -1.0 for _ in range(DIMENSION)]
    return [signos[i] * descriptor[permutacion[i]] for i in range(DIMENSION)]


def distancia(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def a_bytes(vector: list[float]) -> bytes:
    return struct.pack(_FORMATO, *vector)


def desde_bytes(datos: bytes) -> list[float]:
    return list(struct.unpack(_FORMATO, datos))
