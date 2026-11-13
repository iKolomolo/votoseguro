"""Pruebas de extremo a extremo de la API: flujo del votante, principios del voto y administración."""
import io
import json
import random
from datetime import UTC, date, datetime, timedelta

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

_rng = random.Random(2026)


def rostro():
    return [_rng.gauss(0, 0.09) for _ in range(128)]


def con_ruido(descriptor, sigma=0.008):
    return [v + _rng.gauss(0, sigma) for v in descriptor]


def aceptar(biometria=True, datos=True):
    """Lo que envía la pantalla de autorización: versión y huella del texto vigente y las dos casillas."""
    from app.servicios.autorizacion import texto
    return {"version": texto()["version"], "hash": texto()["hash"], "acepto_datos": datos, "acepto_biometria": biometria}


def puntos_cara(reto=None):
    """68 puntos faciales sintéticos: de frente, o cumpliendo un reto de la prueba de vida."""
    p = [[50.0, 50.0] for _ in range(68)]
    p[0], p[16], p[30] = [0.0, 50.0], [100.0, 50.0], [50.0, 50.0]
    p[48], p[54], p[60], p[64], p[62], p[66] = [35.0, 80.0], [65.0, 80.0], [40.0, 80.0], [60.0, 80.0], [50.0, 79.0], [50.0, 81.0]
    if reto == "izquierda":
        p[30] = [62.0, 50.0]
    elif reto == "derecha":
        p[30] = [38.0, 50.0]
    elif reto == "sonreir":
        p[48], p[54] = [30.0, 80.0], [70.0, 80.0]
    elif reto == "boca":
        p[62], p[66] = [50.0, 72.0], [50.0, 90.0]
    return p


def vida_de(encabezados, retos=None):
    """La prueba de vida que enviaría el navegador para los retos del token."""
    import jwt
    token = encabezados["Authorization"].split()[1]
    retos = retos if retos is not None else jwt.decode(token, options={"verify_signature": False}).get("retos", [])
    return {"frente": puntos_cara(), "retos": [puntos_cara(r) for r in retos]}


def datos_persona(documento, biometria=True, **extra):
    return {"tipo_documento": "CC", "documento": documento, "nombres": "Julieth Camila",
            "apellidos": "Riveros Acevedo", "fecha_nacimiento": "2001-07-15", "correo": "j@correo.co",
            "autorizacion": aceptar(biometria), **extra}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _png(texto):
    """PNG de prueba; el OCR simulado (conftest) lee el texto del metadato "texto"."""
    info = PngInfo()
    info.add_text("texto", texto)
    salida = io.BytesIO()
    Image.new("RGB", (640, 400), "white").save(salida, "PNG", pnginfo=info)
    return salida.getvalue()


def foto_cedula(numero, nombres="JULIETH CAMILA", apellidos="RIVEROS ACEVEDO"):
    """Frente de una cédula amarilla: el valor va encima de su etiqueta."""
    return _png(f"REPUBLICA DE COLOMBIA\nNUMERO {numero}\n{apellidos}\nAPELLIDOS\n{nombres}\nNOMBRES")


def reverso_cedula(nacimiento="15-JUL-2001", expedicion="20-AGO-2019"):
    """Reverso de una cédula amarilla: la fecha de nacimiento a la derecha de su etiqueta, arriba; la de
    expedición, abajo."""
    return _png(f"FECHA DE NACIMIENTO {nacimiento}\nBOGOTA D.C.\nLUGAR DE NACIMIENTO\n1.65 O+ F\n"
                f"ESTATURA G.S. RH SEXO\n{expedicion} BOGOTA D.C.\nFECHA Y LUGAR DE EXPEDICION")


def documento(numero):
    return {"tipo_documento": "CC", "documento": numero}


def presentar_cedula(cliente, token, numero, cara, nombres="JULIETH CAMILA", apellidos="RIVEROS ACEVEDO",
                     nacimiento="15-JUL-2001", expedicion="20-AGO-2019"):
    return cliente.post("/api/registraduria/cedula", headers=bearer(token),
                        files={"imagen": ("frente.png", foto_cedula(numero, nombres, apellidos), "image/png"),
                               "reverso": ("reverso.png", reverso_cedula(nacimiento, expedicion), "image/png")},
                        data={"descriptor": json.dumps(cara)})


def inscribir(cliente, numero, cara, **extra):
    """Inscripción en la Registraduría: datos, cédula (con la misma cara, algo de ruido) y rostro."""
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona(numero, **extra))
    assert r.status_code == 200, r.text
    # La cédula de prueba muestra la misma fecha de nacimiento que se escribió.
    nacimiento = date.fromisoformat(extra.get("fecha_nacimiento", "2001-07-15"))
    meses = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
    r = presentar_cedula(cliente, r.json()["token"], numero, con_ruido(cara),
                         nacimiento=f"{nacimiento.day:02d}-{meses[nacimiento.month - 1]}-{nacimiento.year}")
    assert r.status_code == 200, r.text
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": cara, "vida": vida_de(bearer(r.json()["token"]))}, headers=bearer(r.json()["token"]))
    assert r.status_code == 200, r.text
    return r.json()


def ingresar(cliente, numero, cara, **extra):
    """Inscribe al ciudadano y recorre el flujo de votación; devuelve la respuesta de elegibilidad."""
    inscribir(cliente, numero, cara, **extra)
    r = cliente.post("/api/votante/identificacion", json=documento(numero))
    assert r.status_code == 200, r.text
    r = cliente.post("/api/votante/biometria", json={"descriptor": cara, "vida": vida_de(bearer(r.json()["token"]))}, headers=bearer(r.json()["token"]))
    assert r.status_code == 200, r.text
    r = cliente.get("/api/votante/elegibilidad", headers=bearer(r.json()["token"]))
    assert r.status_code == 200, r.text
    return r.json()


def eleccion_activa(cliente, token):
    elecciones = cliente.get("/api/votante/elecciones", headers=bearer(token)).json()
    return next(e for e in elecciones if e["estado"] == "activa")


@pytest.fixture(scope="module")
def votante(cliente):
    cara = rostro()
    elegibilidad = ingresar(cliente, "52000001", cara)
    assert elegibilidad["habilitado"]
    return {"cara": cara, "token": elegibilidad["token"]}


def test_flujo_completo_y_voto_unico(cliente, votante):
    eleccion = eleccion_activa(cliente, votante["token"])
    candidatos = cliente.get(f"/api/votante/elecciones/{eleccion['id_eleccion']}/candidatos",
                             headers=bearer(votante["token"])).json()["candidatos"]
    voto = {"id_eleccion": eleccion["id_eleccion"], "id_candidato": candidatos[0]["id_candidato"]}

    r = cliente.post("/api/votante/votos", json=voto, headers=bearer(votante["token"]))
    assert r.status_code == 201, r.text
    codigo = r.json()["codigo"]
    assert codigo.startswith("VS-")

    # Elegibilidad: un solo voto por votante y elección (RQF05).
    r = cliente.post("/api/votante/votos", json=voto, headers=bearer(votante["token"]))
    assert r.status_code == 409

    # Verificabilidad: el comprobante existe, está íntegro y no revela el candidato.
    v = cliente.post("/api/publico/verificar", json={"codigo": codigo}).json()
    assert v["encontrado"] and v["integro"] and v["firma_valida"]
    assert "candidato" not in str(v).lower()
    assert cliente.post("/api/publico/verificar", json={"codigo": "VS-2026-NOEXISTE"}).json() == {"encontrado": False}
    # El código ya no viaja en la dirección (quedaría en los registros de acceso).
    assert cliente.get("/api/publico/verificar/VS-2026-NOEXISTE").status_code in (404, 405)

    # Consulta de participación con cédula y fecha de nacimiento: dice si votó, en qué votación y qué día, nunca por
    # quién. Una fecha equivocada responde igual que un documento que no existe.
    consulta = {**documento("52000001"), "fecha_nacimiento": "2001-07-15"}
    errada = cliente.post("/api/publico/participacion", json={**consulta, "fecha_nacimiento": "2001-07-16"})
    inexistente = cliente.post("/api/publico/participacion", json={**documento("52999999"), "fecha_nacimiento": "2001-07-15"})
    assert errada.status_code == inexistente.status_code == 404 and errada.json() == inexistente.json()
    p = cliente.post("/api/publico/participacion", json=consulta).json()
    assert p["documento"] == "52000001" and p["tipo_documento"] == "CC" and p["nombre"]
    assert [v["eleccion"] for v in p["votaciones"]] == [eleccion["nombre"]]
    assert len(p["votaciones"][0]["fecha"]) == 10 and "candidato" not in str(p).lower()


def test_segundo_ingreso_verifica_el_rostro(cliente, votante):
    r = cliente.post("/api/votante/identificacion", json=documento("52000001"))
    flujo = bearer(r.json()["token"])
    r = cliente.post("/api/votante/biometria", json={"descriptor": rostro(), "vida": vida_de(flujo)}, headers=flujo)
    assert r.status_code == 401 and "No pudimos verificar su identidad" in r.json()["detail"]
    r = cliente.post("/api/votante/biometria", json={"descriptor": con_ruido(votante["cara"]), "vida": vida_de(flujo)}, headers=flujo)
    assert r.status_code == 200


def verificar_rostro(cliente, numero, cara):
    r = cliente.post("/api/votante/identificacion", json=documento(numero))
    assert r.status_code == 200, r.text
    return cliente.post("/api/votante/biometria", json={"descriptor": cara, "vida": vida_de(bearer(r.json()["token"]))}, headers=bearer(r.json()["token"]))


def test_votar_exige_inscripcion_en_la_registraduria(cliente):
    r = verificar_rostro(cliente, "52999999", rostro())
    assert r.status_code == 401 and "Registraduría" in r.json()["detail"]
    # Una inscripción a medias (sin rostro) tampoco permite votar.
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000006"))
    cara = rostro()
    presentar_cedula(cliente, r.json()["token"], "52000006", cara)
    assert verificar_rostro(cliente, "52000006", con_ruido(cara)).status_code == 401


def test_identificacion_no_revela_quien_participa(cliente, votante):
    """Con solo un número de documento no se puede saber si esa persona participa (punto 7)."""
    import jwt

    respuestas = {}
    for numero in ("52000001", "59999999"):  # inscrito / no inscrito
        r = cliente.post("/api/votante/identificacion", json=documento(numero))
        assert r.status_code == 200
        contenido = jwt.decode(r.json()["token"], options={"verify_signature": False})
        assert numero not in str(contenido)
        respuestas[numero] = (sorted(contenido), contenido["sub"], len(contenido["doc"]))
        r = cliente.post("/api/votante/biometria", json={"descriptor": rostro(), "vida": vida_de(bearer(r.json()["token"]))}, headers=bearer(r.json()["token"]))
        respuestas[numero] += (r.status_code, r.json()["detail"])
    assert respuestas["52000001"] == respuestas["59999999"]


def test_no_se_puede_inscribir_dos_veces(cliente, votante):
    # El primer paso no dice si el documento ya está inscrito (revelaría quién participa)...
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000001"))
    assert r.status_code == 200
    # ...lo dice después de comprobar la cédula.
    r = presentar_cedula(cliente, r.json()["token"], "52000001", rostro())
    assert r.status_code == 409 and "ya está inscrito" in r.json()["detail"]


def _conteos():
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import Autorizacion, Biometria, Persona, VerificacionDocumento, Votante
    with SessionLocal() as db:
        return {m.__name__: db.scalar(select(func.count()).select_from(m))
                for m in (Persona, Votante, Autorizacion, VerificacionDocumento, Biometria)}


def test_inscripcion_no_guarda_nada_hasta_terminar(cliente):
    import jwt

    antes = _conteos()
    # Paso 1 y paso 2 completos, pero sin terminar: no se guarda nada.
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000009"))
    token = r.json()["token"]
    # El token lleva los datos sellados (cifrados): no se leen en claro.
    contenido = str(jwt.decode(token, options={"verify_signature": False}))
    assert "Julieth" not in contenido and "52000009" not in contenido and "j@correo.co" not in contenido
    r = presentar_cedula(cliente, token, "52000009", rostro())
    assert r.status_code == 200 and r.json()["completa"] is False
    assert _conteos() == antes
    # Se puede empezar otra vez sin conflicto: no quedó una inscripción a medias.
    assert cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000009")).status_code == 200
    assert verificar_rostro(cliente, "52000009", rostro()).status_code == 401
    assert _conteos() == antes


def test_reinscripcion_rectifica_los_datos_segun_la_cedula(cliente, admin):
    from app.db import SessionLocal
    from app.servicios.consultas import campo_persona, cifrar_campo

    # Inscrito y luego revocó su biometría: puede volver a inscribirse.
    inscribir(cliente, "52000017", rostro())
    with SessionLocal() as db:
        from sqlalchemy import select

        from app.models import Votante
        id_votante = db.scalar(select(Votante.id_votante).where(Votante.id_persona == _persona(db, "52000017").id_persona))
    assert cliente.post(f"/api/admin/votantes/{id_votante}/revocar-biometria", headers=admin).status_code == 200
    # Un dato mal guardado en una versión anterior (antes se escribía sin confirmarlo con la cédula).
    with SessionLocal() as db:
        persona = _persona(db, "52000017")
        persona.apellidos = cifrar_campo(db, persona.documento_indice, "apellidos", "Marcelo")
        db.commit()
    # Al reinscribirse, la cédula confirma los datos correctos y los guardados se rectifican.
    inscribir(cliente, "52000017", rostro())
    with SessionLocal() as db:
        assert campo_persona(db, _persona(db, "52000017"), "apellidos") == "Riveros Acevedo"
    auditoria = str(cliente.get("/api/admin/auditoria", headers=admin).json())
    assert "RECTIFICAR_DATOS" in auditoria and "actualizados según la cédula: apellidos" in auditoria
    assert "Marcelo" not in auditoria


def test_la_cedula_debe_confirmar_todos_los_datos(cliente):
    def presentar(**cedula):
        r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000018"))
        return presentar_cedula(cliente, r.json()["token"], "52000018", rostro(), **cedula)

    antes = _conteos()
    r = presentar(apellidos="RIVEROS ACEVEDO GOMEZ")  # escribió un apellido de menos
    assert r.status_code == 422 and "apellidos" in r.json()["detail"] and "nombres" not in r.json()["detail"]
    r = presentar(nacimiento="16-JUL-2001")
    assert r.status_code == 422 and "fecha de nacimiento" in r.json()["detail"]
    # La fecha de expedición del reverso no sirve como fecha de nacimiento.
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000018", fecha_nacimiento="2007-08-20"))
    r = presentar_cedula(cliente, r.json()["token"], "52000018", rostro(), expedicion="20-AGO-2007")
    assert r.status_code == 422 and "fecha de nacimiento" in r.json()["detail"]
    r = presentar(nombres="JULIETH", apellidos="RIVERA ACEVEDO")
    assert r.status_code == 422 and "nombres" in r.json()["detail"] and "apellidos" in r.json()["detail"]
    assert _conteos() == antes
    # Una letra mal leída por el OCR se tolera; tildes y mayúsculas no importan.
    assert presentar(apellidos="RIVER0S ACEVEDO").status_code == 200
    r = cliente.post("/api/registraduria/inscripcion",
                     json=datos_persona("52000018", nombres="Julieth Cámila", apellidos="riveros  acevedo"))
    assert presentar_cedula(cliente, r.json()["token"], "52000018", rostro()).status_code == 200


def test_lectura_de_los_dos_tipos_de_cedula():
    from app.servicios.documento import verificar

    datos = {"documento": "1019985582", "nombres": "Nicolás", "apellidos": "Marcelo Ortiz",
             "fecha_nacimiento": "2005-05-15"}
    # Cédula amarilla: valor encima de la etiqueta; fecha en el reverso.
    amarilla = ("REPUBLICA DE COLOMBIA\nIDENTIFICACION PERSONAL\nCEDULA DE CIUDADANIA\nNUMERO 1.019.985.582\n"
                "MARCELO ORTIZ\nAPELLIDOS\nNICOLAS\nNOMBRES\nFIRMA\n"
                "FECHA DE NACIMIENTO\n15-MAY-2005\nBOGOTA D.C.\nESTATURA 1.75 G.S. RH O+ SEXO M")
    assert all(verificar(amarilla, datos).values())
    # Cédula digital: etiqueta y valor en líneas seguidas; reverso con MRZ.
    digital = ("REPUBLICA DE COLOMBIA\nCEDULA DE CIUDADANIA\nNUIP 1.019.985.582\nApellidos / Surname\n"
               "MARCELO ORTIZ\nNombres / Given names\nNICOLÁS\nFecha de nacimiento 15 MAY 2005\n"
               "ICCOL1019985582<<<<<<<<<<<<<<<\n0505153M3512301COL<<<<<<<<<<<0\nMARCELO<ORTIZ<<NICOLAS<<<<<<<<<<<<")
    assert all(verificar(digital, datos).values())
    # Solo con la MRZ también se confirman nombres, apellidos y fecha.
    solo_mrz = "1019985582\n0505153M3512301COL<<<<<<<<<<<0\nMARCELO<ORTIZ<<NICOLAS<<<<<<<<"
    assert all(verificar(solo_mrz, datos).values())
    # Lo que no está en la cédula no se confirma.
    assert verificar(amarilla, {**datos, "apellidos": "Marcelo"})["apellidos"] is False
    assert verificar(amarilla, {**datos, "nombres": "Nicolás Andrés"})["nombres"] is False
    assert verificar(amarilla, {**datos, "fecha_nacimiento": "2005-05-16"})["fecha_nacimiento"] is False


def test_errores_reales_del_ocr_en_la_fecha_de_la_cedula_amarilla():
    """Lecturas reales de Tesseract con una cédula amarilla: J leída como Y, espacio dentro del día y una letra de
    más en el mes. La fecha de expedición no debe colarse."""
    from app.servicios.documento import fechas_de_nacimiento
    for leida in ("21-YUL-2004", "2 1-YUL-2004", "21-YJUL-2004"):
        texto = (f"FECHA DE NACIMIENTO {leida}\nLUGAR DE NACIMIENTO\n26-JUL-2022 BOGOTA D.C.\n"
                 "FECHA Y LUGAR DE EXPEDICION")
        assert fechas_de_nacimiento(texto) == {"2004-07-21"}, leida


def test_fecha_de_nacimiento_no_se_confunde_con_la_de_expedicion():
    from app.servicios.documento import fechas_de_nacimiento

    reverso = ("FECHA DE NACIMIENTO 16-NOV-1990\nBOGOTA D.C.\nLUGAR DE NACIMIENTO\n1.75 O+ M\n"
               "20-DIC-2008 BOGOTA D.C.\nFECHA Y LUGAR DE EXPEDICION")
    assert fechas_de_nacimiento(reverso) == {"1990-11-16"}
    # Errores típicos del OCR: I por 1, O por 0, mes con un cero.
    assert fechas_de_nacimiento("FECHA DE NACIMIENTO I6-N0V-l99O\n20-DIC-2008\nFECHA Y LUGAR DE EXPEDICION") == {"1990-11-16"}
    # El OCR pasó la fecha a la línea siguiente.
    assert fechas_de_nacimiento("FECHA DE NACIMIENTO\n16 NOV 1990\nLUGAR DE NACIMIENTO") == {"1990-11-16"}
    # Sin la etiqueta legible, la fecha de expedición tampoco cuenta.
    assert fechas_de_nacimiento("16-NOV-1990\nBOGOTA\n20-DIC-2008 BOGOTA\nFECHA Y LUGAR DE EXPEDICION") == {"1990-11-16"}

def test_rostro_duplicado_con_otro_documento(cliente, votante):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000002"))
    r = presentar_cedula(cliente, r.json()["token"], "52000002", con_ruido(votante["cara"]))
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": con_ruido(votante["cara"]), "vida": vida_de(bearer(r.json()["token"]))},
                     headers=bearer(r.json()["token"]))
    assert r.status_code == 409


def test_inscripcion_exige_la_cedula_antes_del_rostro(cliente):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000010"))
    token = bearer(r.json()["token"])
    assert cliente.post("/api/registraduria/rostro", json={"descriptor": rostro(), "vida": vida_de(token)}, headers=token).status_code == 403
    # Los tokens de la inscripción no sirven en el flujo de votación.
    assert cliente.post("/api/votante/biometria", json={"descriptor": rostro(), "vida": vida_de(token)}, headers=token).status_code == 403


def test_cedula_con_otro_numero_se_rechaza(cliente):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000007"))
    r = presentar_cedula(cliente, r.json()["token"], "1.020.304.050", rostro())
    assert r.status_code == 422 and "número" in r.json()["detail"]


def test_cedula_acepta_el_numero_con_puntos(cliente):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("1020304050"))
    assert presentar_cedula(cliente, r.json()["token"], "1.020.304.050", rostro()).status_code == 200


def test_numero_de_cedula_completo():
    from app.servicios.documento import coincide
    assert coincide("1020304050", {"NUMERO1020304050"})
    assert not coincide("1020304", {"NUMERO1020304050"})
    assert not coincide("20304050", {"NUMERO1020304050"})
    assert coincide("AB123456", {"PASAPORTEAB123456"})


def test_rostro_distinto_al_de_la_cedula(cliente):
    antes = _conteos()
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000008"))
    r = presentar_cedula(cliente, r.json()["token"], "52000008", rostro())
    token = bearer(r.json()["token"])
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": rostro(), "vida": vida_de(token)}, headers=token)
    assert r.status_code == 422 and "cédula" in r.json()["detail"] and "Intentos restantes: 4" in r.json()["detail"]
    for _ in range(3):
        assert cliente.post("/api/registraduria/rostro", json={"descriptor": rostro(), "vida": vida_de(token)}, headers=token).status_code == 422
    # Al quinto fallo la inscripción se cancela: no se guarda nada y el token deja de servir.
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": rostro(), "vida": vida_de(token)}, headers=token)
    assert r.status_code == 423 and "no se guardó ningún dato" in r.json()["detail"]
    assert cliente.post("/api/registraduria/rostro", json={"descriptor": rostro(), "vida": vida_de(token)}, headers=token).status_code == 423
    assert _conteos() == antes

def _persona(db, numero):
    from sqlalchemy import select

    from app.crypto import llavero
    from app.models import Persona
    return db.scalar(select(Persona).where(Persona.documento_indice == llavero.indice_documento("CC", numero)))


def test_imagen_de_cedula_no_se_guarda(cliente, admin, votante):
    import hashlib

    from sqlalchemy import inspect, select

    from app.db import Base, SessionLocal, engine
    from app.models import VerificacionDocumento, Votante
    from app.servicios import respaldos

    firma_png, firma_png_b64 = bytes.fromhex("89504e47"), "iVBORw0KGgo"  # firma de los archivos PNG
    assert {"documento_identidad", "cotejo_pendiente"}.isdisjoint(inspect(engine).get_table_names())
    with SessionLocal() as db:
        # Ninguna columna de ninguna tabla contiene una imagen PNG (ni en binario ni en base64).
        for tabla in Base.metadata.sorted_tables:
            for fila in db.execute(select(tabla)).all():
                for valor in fila:
                    assert not (isinstance(valor, bytes) and firma_png in valor), tabla.name
                    assert not (isinstance(valor, str) and firma_png_b64 in valor), tabla.name
        # Tampoco en los respaldos.
        respaldo = respaldos.crear(db, creado_por="prueba")
        ok, datos = respaldos.verificar(db, respaldo)
        import json as _json
        import zlib

        from app.crypto import ecc, llavero
        volcado = zlib.decompress(ecc.descifrar(llavero.privada(db, "respaldo"), datos, b"respaldo-v1")).decode()
        assert ok and firma_png_b64 not in volcado and "documento_identidad" not in _json.loads(volcado)["tablas"]

        # Queda solo la evidencia: huella de la imagen y resultado del cotejo.
        persona = _persona(db, "52000001")
        evidencia = db.scalar(select(VerificacionDocumento).where(VerificacionDocumento.id_persona == persona.id_persona))
        assert evidencia.resultado == "verificado" and evidencia.numero_coincide is True
        assert evidencia.hash_imagen == hashlib.sha256(foto_cedula("52000001")).hexdigest()
        assert evidencia.hash_reverso == hashlib.sha256(reverso_cedula()).hexdigest()
        assert evidencia.datos_coinciden is True
        assert evidencia.distancia_cotejo is not None and evidencia.distancia_cotejo < 0.6
        id_votante = db.scalar(select(Votante.id_votante).where(Votante.id_persona == persona.id_persona))

    r = cliente.get(f"/api/admin/votantes/{id_votante}/verificacion", headers=admin)
    assert r.status_code == 200 and r.json()["resultado"] == "verificado"
    assert "imagen" not in r.json() and "descriptor" not in r.json()
    assert cliente.get(f"/api/admin/votantes/{id_votante}/cedula", headers=admin).status_code in (404, 405)
    assert any(v["cedula"] for v in cliente.get("/api/admin/votantes", headers=admin).json())


def test_inscripcion_vence_y_se_puede_repetir_la_foto(cliente, monkeypatch):
    from app.config import get_settings

    # Si vence el plazo, el token deja de servir y no queda nada guardado.
    antes = _conteos()
    monkeypatch.setattr(get_settings(), "minutos_inscripcion", 0)
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000011"))
    monkeypatch.undo()
    r = presentar_cedula(cliente, r.json()["token"], "52000011", rostro())
    assert r.status_code == 401
    assert _conteos() == antes

    # La foto se puede repetir dentro del plazo; la inscripción solo se guarda al confirmar el rostro.
    cara = rostro()
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000011"))
    r = presentar_cedula(cliente, r.json()["token"], "52000011", rostro())
    r = presentar_cedula(cliente, r.json()["token"], "52000011", con_ruido(cara))
    token = bearer(r.json()["token"])
    assert _conteos() == antes
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": cara, "vida": vida_de(token)}, headers=token)
    assert r.status_code == 200, r.text
    despues = _conteos()
    assert all(despues[m] == antes[m] + 1 for m in antes)
    # El mismo token no sirve para inscribirse otra vez.
    assert cliente.post("/api/registraduria/rostro", json={"descriptor": cara, "vida": vida_de(token)}, headers=token).status_code == 409

def test_titular_consulta_y_revoca_su_plantilla(cliente, admin):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Biometria, VerificacionDocumento

    cara = rostro()
    inscribir(cliente, "52000013", cara)
    r = cliente.post("/api/votante/identificacion", json=documento("52000013"))
    r = cliente.post("/api/votante/biometria", json={"descriptor": con_ruido(cara), "vida": vida_de(bearer(r.json()["token"]))}, headers=bearer(r.json()["token"]))
    verificado = bearer(r.json()["token"])

    datos = cliente.get("/api/votante/mis-datos", headers=verificado).json()
    assert datos["plantilla"]["se_borra_el"] == "2027-12-30" and datos["cedula_verificada_el"]
    assert datos["documento"] == "52000013" and datos["tipo_documento"] == "CC" and "@" in datos["correo"]
    # Sin verificar el rostro no se puede revocar.
    r = cliente.post("/api/votante/identificacion", json=documento("52000013"))
    assert cliente.post("/api/votante/revocar-biometria", headers=bearer(r.json()["token"])).status_code == 403

    assert cliente.post("/api/votante/revocar-biometria", headers=verificado).json() == {"revocada": True}
    with SessionLocal() as db:
        id_persona = _persona(db, "52000013").id_persona
        assert db.scalar(select(Biometria).where(Biometria.id_persona == id_persona)) is None
        assert db.scalar(select(VerificacionDocumento).where(VerificacionDocumento.id_persona == id_persona)) is None
    assert cliente.get("/api/votante/mis-datos", headers=verificado).json()["plantilla"] is None
    assert cliente.post("/api/votante/revocar-biometria", headers=verificado).status_code == 404
    autorizacion = cliente.get("/api/votante/mis-datos", headers=verificado).json()["autorizacion"]
    assert autorizacion["acepto_biometria"] and autorizacion["revocada_en"]
    # Ya no puede votar, pero puede volver a inscribirse con los mismos datos, aunque los escriba con tildes,
    # mayúsculas o espacios distintos.
    assert verificar_rostro(cliente, "52000013", con_ruido(cara)).status_code == 401
    r = cliente.post("/api/registraduria/inscripcion",
                     json=datos_persona("52000013", nombres=" JULIETH  CÁMILA", apellidos="riveros acevedo"))
    assert r.status_code == 200, r.text
    inscribir(cliente, "52000013", cara)
    assert "REVOCAR_BIOMETRIA" in str(cliente.get("/api/admin/auditoria", headers=admin).json())


def test_fin_del_piloto_cierra_inscripciones(cliente, monkeypatch):
    from datetime import date

    from app.config import get_settings
    from app.db import SessionLocal
    from app.servicios import retencion

    with SessionLocal() as db:
        assert retencion.aplicar(db)["titulares"] == 0  # el piloto sigue abierto: no se suprime a nadie
    monkeypatch.setattr(get_settings(), "fin_piloto", date(2020, 1, 1))
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000014"))
    assert r.status_code == 410 and "piloto" in r.json()["detail"]


def test_autorizacion_es_obligatoria_y_queda_probada(cliente):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Autorizacion

    texto = cliente.get("/api/publico/autorizacion").json()
    assert texto["version"] == "1.4" and len(texto["hash"]) == 64
    assert "dos caras de su cédula" in str(texto) and "huella dactilar" in str(texto)
    assert "si no la completa en 30 minutos, se descarta" in str(texto)
    assert "30 de diciembre de 2027" in str(texto) and "no estoy obligado(a)" in texto["casillas"]["biometria"]

    sin = {k: v for k, v in datos_persona("52000015").items() if k != "autorizacion"}
    assert cliente.post("/api/registraduria/inscripcion", json=sin).status_code == 422
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000015", autorizacion=aceptar(datos=False)))
    assert r.status_code == 422 and "Debe autorizar" in r.json()["detail"]
    otra = {**aceptar(), "hash": "0" * 64}
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000015", autorizacion=otra))
    assert r.status_code == 422 and "cambió" in r.json()["detail"]

    inscribir(cliente, "52000015", rostro())
    with SessionLocal() as db:
        persona = _persona(db, "52000015")
        filas = db.scalars(select(Autorizacion).where(Autorizacion.id_persona == persona.id_persona)).all()
        assert len(filas) == 1 and filas[0].hash_texto == texto["hash"] and filas[0].acepto_biometria
        assert filas[0].documento_indice == persona.documento_indice


def test_las_dos_casillas_son_necesarias(cliente):
    antes = _conteos()
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000016", biometria=False))
    assert r.status_code == 422 and "datos biométricos" in r.json()["detail"]
    assert _conteos() == antes


def test_pausa_tras_intentos_fallidos(cliente):
    """5 rostros que no coinciden pausan el documento 30 minutos, exista o no: no se bloquea a nadie para siempre
    (nadie puede bloquear la cuenta de otra persona) y la respuesta no revela si el documento está inscrito."""
    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import Limite
    cara = rostro()
    ingresar(cliente, "52000003", cara)
    for numero in ("52000003", "59000003"):  # inscrito / no inscrito
        for _ in range(5):
            assert verificar_rostro(cliente, numero, rostro()).status_code == 401
        r = verificar_rostro(cliente, numero, cara)  # incluso con el rostro correcto
        assert r.status_code == 429 and "espere 30 minutos" in r.json()["detail"]
    # Pasada la pausa, el titular entra normalmente.
    with SessionLocal() as db:
        db.execute(update(Limite).values(vence=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    assert verificar_rostro(cliente, "52000003", con_ruido(cara)).status_code == 200


def test_limite_de_peticiones_por_ip(cliente, monkeypatch):
    from sqlalchemy import delete

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Limite
    with SessionLocal() as db:
        db.execute(delete(Limite))
        db.commit()
    monkeypatch.setattr(get_settings(), "limite_identificacion_ip", 3)
    for _ in range(3):
        assert cliente.post("/api/votante/identificacion", json=documento("52000001")).status_code == 200
    r = cliente.post("/api/votante/identificacion", json=documento("52000001"))
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    monkeypatch.setattr(get_settings(), "limite_login_ip", 2)
    for _ in range(2):
        cliente.post("/api/admin/login", json={"correo": "x@y.co", "password": "no"})
    assert cliente.post("/api/admin/login", json={"correo": "x@y.co", "password": "no"}).status_code == 429
    # La tabla de límites no guarda la IP ni el documento en claro.
    with SessionLocal() as db:
        claves = [l.clave for l in db.query(Limite).all()]
        assert claves and all(len(c) == 64 and "testclient" not in c for c in claves)
        db.execute(delete(Limite))
        db.commit()


def test_menor_de_edad_no_se_puede_inscribir(cliente, admin):
    hoy = date.today()
    hace_18 = hoy.replace(year=hoy.year - 18) if (hoy.month, hoy.day) != (2, 29) else date(hoy.year - 18, 2, 28)
    antes = _conteos()
    # 16 años, y 17 años que cumple 18 mañana: rechazados antes de pedir la cédula, sin guardar nada.
    for nacimiento in ((hoy - timedelta(days=365 * 16)).isoformat(), (hace_18 + timedelta(days=1)).isoformat()):
        r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000004", fecha_nacimiento=nacimiento))
        assert r.status_code == 422 and "18 años" in r.json()["detail"], r.text
    assert _conteos() == antes
    # Quien cumple 18 hoy sí puede inscribirse.
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000004", fecha_nacimiento=hace_18.isoformat()))
    assert r.status_code == 200, r.text
    # El rechazo queda en la auditoría sin el documento ni la fecha.
    auditoria = str(cliente.get("/api/admin/auditoria", headers=admin).json())
    assert "Menor de edad" in auditoria and "52000004" not in auditoria


def test_edad_por_anio_de_nacimiento():
    from app.servicios.consultas import edad, es_menor
    hoy = date(2026, 11, 10)
    assert edad(date(2008, 11, 10), hoy) == 18 and not es_menor("2008-11-10", hoy)
    assert edad(date(2008, 11, 11), hoy) == 17 and es_menor("2008-11-11", hoy)
    assert edad(date(2008, 2, 29), date(2026, 2, 28)) == 17 and edad(date(2008, 2, 29), date(2026, 3, 1)) == 18


def test_pasos_no_se_pueden_saltar(cliente):
    inscribir(cliente, "52000005", rostro())
    r = cliente.post("/api/votante/identificacion", json=documento("52000005"))
    assert cliente.get("/api/votante/elegibilidad", headers=bearer(r.json()["token"])).status_code == 403
    assert cliente.get("/api/votante/elecciones", headers=bearer(r.json()["token"])).status_code == 403
    assert cliente.get("/api/votante/elecciones").status_code == 401


def test_datos_personales_cifrados_en_bd(votante):
    from sqlalchemy import select

    from app.crypto import llavero
    from app.db import SessionLocal
    from app.models import Persona, Voto
    with SessionLocal() as db:
        indice = llavero.indice_documento("CC", "52000001")
        persona = db.scalar(select(Persona).where(Persona.documento_indice == indice))
        assert b"j@correo.co" not in persona.correo and b"52000001" not in persona.documento
        assert b"Julieth" not in persona.nombres
        # Los votos de la elección cerrada llevan todos la hora del cierre, no la de cada voto.
        fechas = {}
        for v in db.scalars(select(Voto)):
            fechas.setdefault(v.id_eleccion, set()).add(v.fecha_hora)
        assert all(len(f) == 1 for f in fechas.values())


def test_resultados_sellados_hasta_el_cierre(cliente, admin, votante):
    eleccion = eleccion_activa(cliente, votante["token"])
    ruta = f"/api/admin/elecciones/{eleccion['id_eleccion']}/resultados"
    assert cliente.get(ruta, headers=admin).status_code == 409
    assert cliente.get(f"/api/publico/elecciones/{eleccion['id_eleccion']}/resultados").status_code == 409


def test_crear_eleccion_candidatos_y_escrutinio(cliente, admin):
    ahora = datetime.now(UTC)
    r = cliente.post("/api/admin/elecciones", headers=admin, json={
        "nombre": "Elección de prueba", "tipo": "Institucional",
        "fecha_inicio": (ahora + timedelta(hours=1)).isoformat(), "fecha_fin": (ahora + timedelta(hours=5)).isoformat()})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["estado"] == "programada"
    for nombre in ("Ana Uno", "Beto Dos"):
        r = cliente.post(f"/api/admin/elecciones/{e['id_eleccion']}/candidatos", headers=admin,
                         data={"nombre": nombre, "partido": "Partido de prueba", "color": "#123456"})
        assert r.status_code == 201, r.text

    # Se abre adelantando la fecha de inicio (solo posible antes de iniciar) y se vota.
    r = cliente.put(f"/api/admin/elecciones/{e['id_eleccion']}", headers=admin, json={
        "nombre": "Elección de prueba", "tipo": "Institucional",
        "fecha_inicio": (ahora - timedelta(minutes=1)).isoformat(), "fecha_fin": (ahora + timedelta(hours=5)).isoformat()})
    assert r.status_code == 200 and r.json()["estado"] == "activa"
    # Con la votación en curso ya no se puede editar ni agregar candidatos.
    assert cliente.post(f"/api/admin/elecciones/{e['id_eleccion']}/candidatos", headers=admin,
                        data={"nombre": "Tarde", "partido": "Partido tardío"}).status_code == 409

    candidatos = cliente.get(f"/api/admin/elecciones/{e['id_eleccion']}/candidatos", headers=admin).json()
    eleccion_votos = {candidatos[0]["id_candidato"]: 2, candidatos[1]["id_candidato"]: 1}
    doc, codigos = 53000000, []
    for id_candidato, n in eleccion_votos.items():
        for _ in range(n):
            doc += 1
            token = ingresar(cliente, str(doc), rostro())["token"]
            r = cliente.post("/api/votante/votos", headers=bearer(token),
                             json={"id_eleccion": e["id_eleccion"], "id_candidato": id_candidato})
            assert r.status_code == 201, r.text
            codigos.append(r.json()["codigo"])

    # Anonimato: con la elección abierta los votos están en la urna (una sola fila barajada), no en VOTO, y la
    # participación no guarda la hora. El comprobante ya se puede verificar.
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Participacion, Urna, Voto
    with SessionLocal() as db:
        assert not db.scalars(select(Voto).where(Voto.id_eleccion == e["id_eleccion"])).all()
        assert len(json.loads(db.get(Urna, e["id_eleccion"]).votos)) == 3
        for p in db.scalars(select(Participacion).where(Participacion.id_eleccion == e["id_eleccion"])):
            assert (p.fecha_hora.hour, p.fecha_hora.minute, p.fecha_hora.second) == (0, 0, 0)
    v = cliente.post("/api/publico/verificar", json={"codigo": codigos[0]}).json()
    assert v["encontrado"] and v["integro"] and v["firma_valida"] and not v["escrutado"]

    r = cliente.post(f"/api/admin/elecciones/{e['id_eleccion']}/cerrar", headers=admin)
    assert r.status_code == 200 and r.json()["integridad_ok"] is True
    # Al cerrar, los votos pasan a VOTO en orden aleatorio, todos con la hora del cierre, y la urna se borra.
    with SessionLocal() as db:
        votos = db.scalars(select(Voto).where(Voto.id_eleccion == e["id_eleccion"])).all()
        assert len(votos) == 3 and len({v.fecha_hora for v in votos}) == 1
        assert db.get(Urna, e["id_eleccion"]) is None
    v = cliente.post("/api/publico/verificar", json={"codigo": codigos[0]}).json()
    assert v["encontrado"] and v["integro"] and v["escrutado"] and "hora" not in str(v)
    res = cliente.get(f"/api/admin/elecciones/{e['id_eleccion']}/resultados", headers=admin).json()
    assert [(c["nombre"], c["votos"]) for c in res["candidatos"]] == [("Ana Uno", 2), ("Beto Dos", 1)]
    assert res["total_votos"] == res["votaron"] == 3

    pdf = cliente.get(f"/api/admin/elecciones/{e['id_eleccion']}/reporte.pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    csv = cliente.get(f"/api/admin/elecciones/{e['id_eleccion']}/reporte.csv", headers=admin)
    assert "Ana Uno" in csv.text
    # Tras el cierre no se reciben más votos.
    token = ingresar(cliente, "53999999", rostro())["token"]
    r = cliente.post("/api/votante/votos", headers=bearer(token),
                     json={"id_eleccion": e["id_eleccion"], "id_candidato": candidatos[0]["id_candidato"]})
    assert r.status_code == 409


def test_login_admin_y_roles(cliente, admin):
    assert cliente.post("/api/admin/login", json={"correo": "admin@votoseguro.local", "password": "mal"}).status_code == 401
    r = cliente.post("/api/admin/usuarios", headers=admin, json={
        "correo": "supervisor@votoseguro.local", "nombre": "Supervisor", "rol": "Supervisor", "password": "Supervisor2026*"})
    assert r.status_code == 201, r.text
    token = cliente.post("/api/admin/login", json={"correo": "supervisor@votoseguro.local",
                                                    "password": "Supervisor2026*"}).json()["token"]
    sup = bearer(token)
    assert cliente.get("/api/admin/dashboard", headers=sup).status_code == 200
    assert cliente.post("/api/admin/respaldos", headers=sup).status_code == 403
    assert cliente.get("/api/admin/usuarios", headers=sup).status_code == 403
    assert cliente.get("/api/admin/dashboard").status_code == 401


def test_auditoria_encadenada(cliente, admin):
    r = cliente.get("/api/admin/auditoria/verificar", headers=admin).json()
    assert r["integra"] and r["registros"] > 10

    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import Auditoria
    with SessionLocal() as db:
        db.execute(update(Auditoria).where(Auditoria.id_auditoria == 2).values(descripcion="alterado"))
        db.commit()
    r = cliente.get("/api/admin/auditoria/verificar", headers=admin).json()
    assert not r["integra"] and r["roto_en"] == 2


def test_respaldo_y_restauracion(cliente, admin):
    respaldo = cliente.post("/api/admin/respaldos", headers=admin).json()
    assert respaldo["valido"]
    antes = {e["codigo"] for e in cliente.get("/api/admin/elecciones", headers=admin).json()}
    ahora = datetime.now(UTC)
    cliente.post("/api/admin/elecciones", headers=admin, json={
        "nombre": "Elección posterior al respaldo", "tipo": "Municipal",
        "fecha_inicio": (ahora + timedelta(days=1)).isoformat(), "fecha_fin": (ahora + timedelta(days=2)).isoformat()})
    r = cliente.post(f"/api/admin/respaldos/{respaldo['id_respaldo']}/restaurar", headers=admin)
    assert r.status_code == 200, r.text
    despues = {e["codigo"] for e in cliente.get("/api/admin/elecciones", headers=admin).json()}
    assert despues == antes


def test_voto_inmutable_en_postgres(votante):
    """RQF14: el trigger de PostgreSQL impide modificar o borrar votos incluso con acceso directo a la BD."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.db import engine
    if engine.dialect.name != "postgresql":
        pytest.skip("El trigger de inmutabilidad solo existe en PostgreSQL")
    for sql in ("UPDATE voto SET hash_voto = 'x'", "DELETE FROM voto"):
        with pytest.raises(DBAPIError, match="inmutables"), engine.begin() as conn:
            conn.execute(text(sql))


def test_politica_de_tratamiento_publicada(cliente):
    r = cliente.get("/api/publico/politica")
    assert r.status_code == 200
    p = r.json()
    texto = json.dumps(p, ensure_ascii=False)
    # Contenido mínimo del Decreto 1377 art. 13: responsables y contacto, finalidades, derechos, procedimiento,
    # vigencia de la política y de la base de datos.
    for requerido in ("Mario Mendoza Huertas", "Carrera 104", "Ingeniería de Software", "nicololmomo123@gmail.com", "Para qué se usa", "Sus derechos",
                      "10 días hábiles", "15 días hábiles", "Vigencia", "30 de diciembre de 2027", "18 años"):
        assert requerido in texto, requerido
    assert "{fin}" not in texto and "{correo}" not in texto
    assert len(p["hash"]) == 64
    from app.servicios.politica import markdown
    assert markdown().startswith("# Política de Tratamiento de Datos Personales")


def test_migracion_de_votos_al_formato_anonimo(votante):
    """Votos guardados por la versión anterior (en VOTO, con su hora) pasan a la urna o se reescriben al azar."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Participacion, Urna, Votante, Voto
    from app.servicios import elecciones
    ahora = datetime.now(UTC).replace(microsecond=0)
    with SessionLocal() as db:
        abierta = elecciones.crear(db, nombre="Migración abierta", descripcion=None, tipo="Prueba",
                                   fecha_inicio=ahora - timedelta(hours=1), fecha_fin=ahora + timedelta(hours=1))
        cerrada = elecciones.crear(db, nombre="Migración cerrada", descripcion=None, tipo="Prueba",
                                   fecha_inicio=ahora - timedelta(hours=3), fecha_fin=ahora - timedelta(hours=2))
        cerrada.estado, cerrada.fecha_cierre = "finalizada", ahora - timedelta(hours=2)
        db.delete(db.get(Urna, cerrada.id_eleccion))
        id_votante = db.scalars(select(Votante.id_votante)).first()
        for i, e in enumerate((abierta, abierta, cerrada, cerrada)):
            db.add(Voto(id_voto=f"00000000-0000-0000-0000-00000000000{i}", id_eleccion=e.id_eleccion,
                        voto_cifrado=b"x", fecha_hora=ahora.replace(minute=0, second=0), hash_voto="h" * 64,
                        codigo_hash=f"{i}" * 64, firma=b"f"))
        db.add(Participacion(id_votante=id_votante, id_eleccion=abierta.id_eleccion, fecha_hora=ahora))
        db.commit()
        ids = (abierta.id_eleccion, cerrada.id_eleccion)

    with SessionLocal() as db:
        assert elecciones.migrar_anonimato(db) > 0
        assert not db.scalars(select(Voto).where(Voto.id_eleccion == ids[0])).all()
        assert len(json.loads(db.get(Urna, ids[0]).votos)) == 2
        cierre = db.get(elecciones.Eleccion, ids[1]).fecha_cierre
        assert {v.fecha_hora for v in db.scalars(select(Voto).where(Voto.id_eleccion == ids[1]))} == {cierre}
        p = db.scalar(select(Participacion).where(Participacion.id_eleccion == ids[0]))
        assert (p.fecha_hora.hour, p.fecha_hora.minute) == (0, 0)
        assert elecciones.migrar_anonimato(db) == 0  # idempotente


def _id_votante(numero):
    from sqlalchemy import select

    from app.crypto import llavero
    from app.db import SessionLocal
    from app.models import Persona, Votante
    with SessionLocal() as db:
        persona = db.scalar(select(Persona).where(Persona.documento_indice == llavero.indice_documento("CC", numero)))
        return None if persona is None else db.scalar(
            select(Votante.id_votante).where(Votante.id_persona == persona.id_persona))


def test_supresion_a_solicitud_del_titular(cliente, admin, votante):
    from sqlalchemy import select

    from app.crypto import llavero
    from app.db import SessionLocal
    from app.models import Autorizacion, Biometria, Supresion

    # Quien ya votó en una elección abierta no se puede borrar todavía: su participación garantiza el voto único.
    r = cliente.delete(f"/api/admin/votantes/{_id_votante('52000001')}", headers=admin)
    assert r.status_code == 409 and "abierta" in r.json()["detail"]
    assert _id_votante("52000001") is not None

    inscribir(cliente, "55000001", rostro())
    id_votante = _id_votante("55000001")
    indice = llavero.indice_documento("CC", "55000001")
    r = cliente.delete(f"/api/admin/votantes/{id_votante}", headers=admin)
    assert r.status_code == 200, r.text
    assert _id_votante("55000001") is None
    with SessionLocal() as db:
        aut = db.scalars(select(Autorizacion).where(Autorizacion.documento_indice == indice)).all()
        assert aut and all(a.id_persona is None and a.suprimida_en for a in aut)  # prueba seudonimizada
        assert db.scalar(select(Supresion).where(Supresion.documento_indice == indice))
        assert not db.scalars(select(Biometria).where(Biometria.id_persona.is_(None))).all()
    assert verificar_rostro(cliente, "55000001", rostro()).status_code == 401
    auditoria = str(cliente.get("/api/admin/auditoria", headers=admin).json())
    assert "SUPRIMIR_TITULAR" in auditoria and "55000001" not in auditoria
    # Puede volver a inscribirse si quiere.
    inscribir(cliente, "55000001", rostro())
    assert _id_votante("55000001") is not None


def test_restaurar_un_respaldo_no_revive_a_quien_pidio_borrar(cliente, admin):
    from app.db import SessionLocal
    from app.models import Respaldo
    from app.servicios import respaldos

    inscribir(cliente, "55000002", rostro())
    with SessionLocal() as db:
        id_respaldo = respaldos.crear(db, creado_por="prueba").id_respaldo
    assert cliente.delete(f"/api/admin/votantes/{_id_votante('55000002')}", headers=admin).status_code == 200
    with SessionLocal() as db:
        respaldos.restaurar(db, db.get(Respaldo, id_respaldo), actor="prueba", ip=None)
    assert _id_votante("55000002") is None
    assert _id_votante("52000001") is not None  # lo demás sí se restauró


def test_plazos_de_conservacion(votante):
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Autorizacion, Participacion, Respaldo, Votante
    from app.servicios import elecciones, retencion
    ahora = datetime.now(UTC)
    s = get_settings()
    with SessionLocal() as db:
        # Respaldo de hace 8 días (se borra con su archivo) y de hace 1 día (se conserva).
        s.directorio_respaldos.mkdir(parents=True, exist_ok=True)
        for nombre, dias in (("viejo.vsbak", 8), ("nuevo.vsbak", 1)):
            (s.directorio_respaldos / nombre).write_bytes(b"x")
            db.add(Respaldo(archivo=nombre, fecha=ahora - timedelta(days=dias), tamano=1, hash="0" * 64,
                            firma=b"f", automatico=True, creado_por="prueba"))
        # Elección cerrada hace 31 días: su participación se desvincula. Cerrada hace 5 días: todavía no.
        id_votante = db.scalars(select(Votante.id_votante)).first()
        ids = []
        for dias in (31, 5):
            e = elecciones.crear(db, nombre=f"Cerrada hace {dias}", descripcion=None, tipo="Prueba",
                                 fecha_inicio=ahora - timedelta(days=dias + 1), fecha_fin=ahora - timedelta(days=dias))
            e.estado, e.fecha_cierre = "finalizada", ahora - timedelta(days=dias)
            db.add(Participacion(id_votante=id_votante, id_eleccion=e.id_eleccion, fecha_hora=ahora))
            ids.append(e.id_eleccion)
        # Prueba de autorización seudonimizada hace 4 años (se borra) y hace 1 año (se conserva).
        for anios in (4, 1):
            db.add(Autorizacion(id_persona=None, documento_indice=f"{anios}" * 64, version_texto="1.0",
                                hash_texto="0" * 64, acepto_datos=True, acepto_biometria=False,
                                fecha=ahora - timedelta(days=365 * anios + 30),
                                suprimida_en=ahora - timedelta(days=365 * anios)))
        db.commit()

        hecho = retencion.aplicar(db)
        assert hecho["respaldos"] >= 1 and hecho["participaciones"] >= 1 and hecho["autorizaciones"] >= 1
        assert not (s.directorio_respaldos / "viejo.vsbak").exists() and (s.directorio_respaldos / "nuevo.vsbak").exists()
        # Un archivo huérfano (sin registro) de hace 8 días también se borra.
        import os
        huerfano = s.directorio_respaldos / "huerfano.vsbak"
        huerfano.write_bytes(b"x")
        viejo = (ahora - timedelta(days=8)).timestamp()
        os.utime(huerfano, (viejo, viejo))
        retencion.aplicar(db)
        assert not huerfano.exists()
        assert db.scalar(select(Respaldo).where(Respaldo.archivo == "nuevo.vsbak"))
        vieja, reciente = (db.scalar(select(Participacion).where(Participacion.id_eleccion == i)) for i in ids)
        assert vieja.id_votante is None and reciente.id_votante == id_votante
        indices = set(db.scalars(select(Autorizacion.documento_indice)))
        assert "4" * 64 not in indices and "1" * 64 in indices
        # El conteo de participación de la elección vieja se conserva.
        assert db.scalar(select(Participacion.id_participacion).where(Participacion.id_eleccion == ids[0]))



def test_prueba_de_vida_la_comprueba_el_servidor(cliente, votante):
    """Una foto (los puntos no cambian), los retos en otro orden o sin prueba: rechazados aunque el rostro coincida."""
    import jwt
    cara = con_ruido(votante["cara"])
    for intento in ("sin", "foto", "orden"):
        r = cliente.post("/api/votante/identificacion", json=documento("52000001"))
        flujo = bearer(r.json()["token"])
        retos = jwt.decode(r.json()["token"], options={"verify_signature": False})["retos"]
        assert len(retos) == 3 and len(set(retos)) == 3
        if intento == "sin":
            cuerpo = {"descriptor": cara}
        elif intento == "foto":
            cuerpo = {"descriptor": cara, "vida": {"frente": puntos_cara(), "retos": [puntos_cara()] * 3}}
        else:
            cuerpo = {"descriptor": cara, "vida": vida_de(flujo, list(reversed(retos)))}
        r = cliente.post("/api/votante/biometria", json=cuerpo, headers=flujo)
        assert r.status_code == 422 and "prueba de vida" in r.json()["detail"], (intento, r.text)
    # Con la prueba completa, entra.
    r = cliente.post("/api/votante/identificacion", json=documento("52000001"))
    flujo = bearer(r.json()["token"])
    assert cliente.post("/api/votante/biometria", json={"descriptor": cara, "vida": vida_de(flujo)},
                        headers=flujo).status_code == 200


def test_reglas_de_la_prueba_de_vida():
    import pytest as _pytest

    from app.servicios import vida
    frente = puntos_cara()
    for reto in vida.RETOS:
        vida.verificar([reto], {"frente": frente, "retos": [puntos_cara(reto)]})
        with _pytest.raises(vida.PruebaFallida):
            vida.verificar([reto], {"frente": frente, "retos": [frente]})
    # Una foto inclinada: todos los puntos se comprimen igual en x, las proporciones no cambian.
    inclinada = [[x * 0.8 + 10, y] for x, y in puntos_cara()]
    with _pytest.raises(vida.PruebaFallida):
        vida.verificar(["izquierda"], {"frente": frente, "retos": [inclinada]})
    # Otra cara, de tamaño muy distinto, en medio de la prueba.
    with _pytest.raises(vida.PruebaFallida):
        vida.verificar(["boca"], {"frente": frente, "retos": [[[x * 3, y * 3] for x, y in puntos_cara("boca")]]})
    with _pytest.raises(vida.PruebaFallida):
        vida.verificar(["boca"], {"frente": frente[:10], "retos": [puntos_cara("boca")]})


# Debe ser la última prueba del archivo: suprime a todos los votantes.
def test_fin_del_piloto_suprime_todos_los_datos(cliente, admin, monkeypatch):
    from datetime import date

    from sqlalchemy import func, select

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Autorizacion, Biometria, Participacion, Persona, VerificacionDocumento, Votante
    from app.servicios import retencion

    monkeypatch.setattr(get_settings(), "fin_piloto", date(2020, 1, 1))
    with SessionLocal() as db:
        antes = db.scalar(select(func.count()).select_from(Votante))
        assert retencion.aplicar(db)["titulares"] == antes > 0
        for modelo in (Votante, Persona, Biometria, VerificacionDocumento):
            assert db.scalar(select(func.count()).select_from(modelo)) == 0, modelo
        assert db.scalar(select(func.count()).select_from(Participacion).where(Participacion.id_votante.is_not(None))) == 0
        assert db.scalar(select(func.count()).select_from(Participacion)) > 0  # el conteo se conserva
        assert all(a.id_persona is None and a.suprimida_en for a in db.scalars(select(Autorizacion)))
        assert retencion.aplicar(db)["titulares"] == 0  # idempotente
    assert "SUPRIMIR_DATOS_FIN_PILOTO" in str(cliente.get("/api/admin/auditoria", headers=admin).json())
