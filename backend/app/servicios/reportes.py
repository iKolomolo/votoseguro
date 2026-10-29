"""Reportes de resultados en PDF y CSV (RQF22, RQF23)."""
import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from fpdf import FPDF

from ..config import get_settings

AZUL = (0, 61, 165)
GRIS = (75, 85, 99)
BORDE = (200, 214, 232)


def _latin1(texto) -> str:
    """Las fuentes base de PDF usan Latin-1: cubre tildes y ñ, pero no guiones largos ni emojis."""
    return str(texto).replace("—", "-").replace("–", "-").encode("latin-1", "replace").decode("latin-1")


def _fecha(iso: str | None) -> str:
    if not iso:
        return "-"
    return datetime.fromisoformat(iso).astimezone(ZoneInfo(get_settings().zona_horaria)).strftime("%d/%m/%Y %H:%M")


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def pdf_resultados(datos: dict, generado_por: str) -> bytes:
    e = datos["eleccion"]
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_fill_color(*AZUL)
    pdf.rect(0, 0, 210, 34, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, 9)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "VOTOSEGURO COLOMBIA - REPORTE OFICIAL DE RESULTADOS")
    pdf.set_xy(15, 15)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, _latin1(e["nombre"]))
    pdf.set_xy(15, 24)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _latin1(f"{e['codigo']}  |  {e['tipo']}  |  Inicio: {_fecha(e['fecha_inicio'])}  |  "
                           f"Cierre: {_fecha(e['fecha_cierre'] or e['fecha_fin'])}"))

    pdf.set_text_color(15, 23, 42)
    pdf.set_y(44)
    resumen = [("Habilitados", _miles(datos["habilitados"])), ("Votaron", _miles(datos["votaron"])),
               ("Participación", f"{datos['participacion']}%"), ("Abstención", f"{datos['abstencion']}%")]
    ancho = 45
    for i, (etiqueta, valor) in enumerate(resumen):
        x = 15 + i * (ancho + 0)
        pdf.set_draw_color(*BORDE)
        pdf.rect(x, 44, ancho - 3, 20)
        pdf.set_xy(x, 47)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(ancho - 3, 7, valor, align="C")
        pdf.set_xy(x, 55)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRIS)
        pdf.cell(ancho - 3, 5, _latin1(etiqueta), align="C")
        pdf.set_text_color(15, 23, 42)

    pdf.set_y(74)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Resultados por candidato", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(240, 244, 250)
    for texto, w, al in (("N.", 12, "C"), ("Candidato", 70, "L"), ("Partido", 50, "L"), ("Votos", 25, "R"),
                         ("%", 23, "R")):
        pdf.cell(w, 7, texto, border="B", align=al, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for c in datos["candidatos"]:
        pdf.cell(12, 7, f"{c['numero']:02d}", align="C")
        pdf.cell(70, 7, _latin1(c["nombre"])[:40])
        pdf.cell(50, 7, _latin1(c["partido"])[:30])
        pdf.cell(25, 7, _miles(c["votos"]), align="R")
        pdf.cell(23, 7, f"{c['porcentaje']}%", align="R")
        pdf.ln()
        # Barra proporcional
        y = pdf.get_y()
        r, g, b = (int(c["color"][i:i + 2], 16) for i in (1, 3, 5))
        pdf.set_fill_color(243, 244, 246)
        pdf.rect(27, y, 153, 2, "F")
        pdf.set_fill_color(r, g, b)
        pdf.rect(27, y, 153 * c["porcentaje"] / 100, 2, "F")
        pdf.ln(4)

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, _latin1(f"Total de votos escrutados: {_miles(datos['total_votos'])}"), new_x="LMARGIN", new_y="NEXT")
    integridad = datos["integridad_ok"]
    pdf.set_text_color(*((26, 122, 74) if integridad else (185, 28, 28)))
    pdf.cell(0, 6, _latin1("Verificación de integridad: " + (
        "cada participación registrada corresponde a un voto válido." if integridad
        else "ALERTA - el número de votos válidos no coincide con las participaciones.")),
        new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(*GRIS)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_y(-28)
    pdf.multi_cell(0, 4, _latin1(
        "Los votos se cifraron con ECIES sobre la curva NIST P-256 (ECDH + HKDF-SHA256 + AES-256-GCM) usando la llave "
        "pública de esta elección, y se descifraron únicamente después del cierre. Cada voto está firmado con ECDSA "
        f"P-256. Generado por {generado_por} el "
        f"{datetime.now(ZoneInfo(get_settings().zona_horaria)):%d/%m/%Y %H:%M}."))
    return bytes(pdf.output())


def csv_resultados(datos: dict) -> str:
    salida = io.StringIO()
    escritor = csv.writer(salida)
    e = datos["eleccion"]
    escritor.writerow(["Elección", e["nombre"], "Código", e["codigo"]])
    escritor.writerow(["Habilitados", datos["habilitados"], "Votaron", datos["votaron"],
                       "Participación %", datos["participacion"]])
    escritor.writerow([])
    escritor.writerow(["Número", "Candidato", "Partido", "Votos", "Porcentaje"])
    for c in datos["candidatos"]:
        escritor.writerow([c["numero"], c["nombre"], c["partido"], c["votos"], c["porcentaje"]])
    return "﻿" + salida.getvalue()  # BOM para que Excel reconozca UTF-8
