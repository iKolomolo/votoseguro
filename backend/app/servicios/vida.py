"""Prueba de vida comprobada por el servidor.

El servidor elige al azar los retos (girar la cabeza a la izquierda o a la derecha, sonreír, abrir la boca) y los
pone en el token del paso. El navegador los pide en ese orden y envía, junto con el descriptor del rostro, los 68
puntos faciales del momento en que miraba de frente y del momento en que cumplió cada reto. Aquí se recalculan las
medidas y se comprueba que cada reto se cumplió de verdad, en el orden pedido.

Por qué detiene una foto: al inclinar una foto plana, todos sus puntos se comprimen por igual y las proporciones
(dónde queda la nariz entre los bordes de la cara, el ancho de la boca, la apertura de los labios) no cambian. Una
cabeza real que gira, sonríe o abre la boca sí las cambia.

Límite: los puntos los calcula el navegador. Alguien con conocimientos técnicos podría fabricar puntos coherentes;
para impedirlo del todo haría falta analizar el video en el servidor. Sí obliga a que ya no baste con enviar un
descriptor sacado de una foto, y los intentos fallidos cuentan para la pausa por documento.
"""
import math
import secrets

RETOS = ("izquierda", "derecha", "sonreir", "boca")
POR_VERIFICACION = 3

# Umbrales algo más tolerantes que los del navegador (biometria/CapturaFacial.tsx), que exige un poco más:
# así una prueba que el navegador aceptó no la rechaza el servidor por redondeos.
GIRO_MINIMO = 0.08  # desplazamiento de la nariz, como fracción del ancho de la cara
FRONTAL_MAXIMO = 0.18
SONRISA_MINIMA = 1.07  # boca 7 % más ancha que de frente
APERTURA_MINIMA = 0.3  # alto / ancho de la boca por dentro
APERTURA_AUMENTO = 0.2
ESCALA = (0.6, 1.6)  # la cara no puede cambiar tanto de tamaño entre un momento y otro


class PruebaFallida(ValueError):
    pass


def nuevos_retos() -> list[str]:
    azar = secrets.SystemRandom()
    return azar.sample(RETOS, POR_VERIFICACION)


def _puntos(valor) -> list[tuple[float, float]]:
    if not isinstance(valor, list) or len(valor) != 68:
        raise PruebaFallida("Faltan los puntos del rostro")
    puntos = []
    for p in valor:
        if not isinstance(p, list) or len(p) != 2 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in p):
            raise PruebaFallida("Puntos del rostro inválidos")
        puntos.append((float(p[0]), float(p[1])))
    return puntos


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def medidas(p: list[tuple[float, float]]) -> dict[str, float]:
    ancho = _dist(p[0], p[16])
    if ancho < 20 or abs(p[16][0] - p[0][0]) < 1:
        raise PruebaFallida("Rostro demasiado pequeño")
    return {
        "ancho": ancho,
        "giro": (p[30][0] - p[0][0]) / (p[16][0] - p[0][0]),
        "boca": _dist(p[48], p[54]) / ancho,
        "apertura": _dist(p[62], p[66]) / max(_dist(p[60], p[64]), 1e-6),
    }


def _cumple(reto: str, m: dict, ref: dict) -> bool:
    # Las coordenadas son de la imagen sin espejo: la izquierda de la persona queda a la derecha.
    if reto == "izquierda":
        return m["giro"] - ref["giro"] > GIRO_MINIMO
    if reto == "derecha":
        return ref["giro"] - m["giro"] > GIRO_MINIMO
    if reto == "sonreir":
        return m["boca"] > ref["boca"] * SONRISA_MINIMA
    if reto == "boca":
        return m["apertura"] > APERTURA_MINIMA and m["apertura"] - ref["apertura"] > APERTURA_AUMENTO
    return False


def verificar(retos: list[str], prueba: dict | None) -> None:
    """Lanza PruebaFallida si la prueba no demuestra los retos pedidos, en orden."""
    if not retos:
        raise PruebaFallida("La sesión no tiene retos de prueba de vida. Empiece de nuevo.")
    if not isinstance(prueba, dict) or not isinstance(prueba.get("retos"), list) or len(prueba["retos"]) != len(retos):
        raise PruebaFallida("No se completó la prueba de vida")
    ref = medidas(_puntos(prueba.get("frente")))
    if abs(ref["giro"] - 0.5) > FRONTAL_MAXIMO:
        raise PruebaFallida("La prueba de vida debe empezar mirando de frente")
    for reto, puntos in zip(retos, prueba["retos"]):
        m = medidas(_puntos(puntos))
        if not ESCALA[0] < m["ancho"] / ref["ancho"] < ESCALA[1] or not _cumple(reto, m, ref):
            raise PruebaFallida("No se comprobó la prueba de vida")
