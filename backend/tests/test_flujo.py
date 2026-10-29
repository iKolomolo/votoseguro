"""Pruebas de extremo a extremo de la API: flujo del votante, principios del voto y administración."""
import io
import json
import random
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

_rng = random.Random(2026)


def rostro():
    return [_rng.gauss(0, 0.09) for _ in range(128)]


def con_ruido(descriptor, sigma=0.008):
    return [v + _rng.gauss(0, sigma) for v in descriptor]


def datos_persona(documento, **extra):
    return {"tipo_documento": "CC", "documento": documento, "nombres": "Julieth Camila",
            "apellidos": "Riveros Acevedo", "fecha_nacimiento": "2001-07-15", "correo": "j@correo.co", **extra}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def foto_cedula(numero):
    """PNG de prueba; el OCR simulado (conftest) lee el número del metadato "numero"."""
    info = PngInfo()
    info.add_text("numero", numero)
    salida = io.BytesIO()
    Image.new("RGB", (640, 400), "white").save(salida, "PNG", pnginfo=info)
    return salida.getvalue()


def documento(numero):
    return {"tipo_documento": "CC", "documento": numero}


def presentar_cedula(cliente, token, numero, cara):
    return cliente.post("/api/registraduria/cedula", headers=bearer(token),
                        files={"imagen": ("cedula.png", foto_cedula(numero), "image/png")},
                        data={"descriptor": json.dumps(cara)})


def inscribir(cliente, numero, cara, **extra):
    """Inscripción en la Registraduría: datos, cédula (con la misma cara, algo de ruido) y rostro."""
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona(numero, **extra))
    assert r.status_code == 200, r.text
    r = presentar_cedula(cliente, r.json()["token"], numero, con_ruido(cara))
    assert r.status_code == 200, r.text
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": cara}, headers=bearer(r.json()["token"]))
    assert r.status_code == 200, r.text
    return r.json()


def ingresar(cliente, numero, cara, **extra):
    """Inscribe al ciudadano y recorre el flujo de votación; devuelve la respuesta de elegibilidad."""
    inscribir(cliente, numero, cara, **extra)
    r = cliente.post("/api/votante/identificacion", json=documento(numero))
    assert r.status_code == 200, r.text
    r = cliente.post("/api/votante/biometria", json={"descriptor": cara}, headers=bearer(r.json()["token"]))
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
    v = cliente.get(f"/api/publico/verificar/{codigo}").json()
    assert v["encontrado"] and v["integro"] and v["firma_valida"]
    assert "candidato" not in str(v).lower()
    assert cliente.get("/api/publico/verificar/VS-2026-NOEXISTE").json() == {"encontrado": False}


def test_segundo_ingreso_verifica_el_rostro(cliente, votante):
    r = cliente.post("/api/votante/identificacion", json=documento("52000001"))
    flujo = bearer(r.json()["token"])
    r = cliente.post("/api/votante/biometria", json={"descriptor": rostro()}, headers=flujo)
    assert r.status_code == 401 and "Intentos restantes: 4" in r.json()["detail"]
    r = cliente.post("/api/votante/biometria", json={"descriptor": con_ruido(votante["cara"])}, headers=flujo)
    assert r.status_code == 200


def test_votar_exige_inscripcion_en_la_registraduria(cliente):
    r = cliente.post("/api/votante/identificacion", json=documento("52999999"))
    assert r.status_code == 404 and "Registraduría" in r.json()["detail"]
    # Una inscripción a medias (sin rostro) tampoco permite votar.
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000006"))
    presentar_cedula(cliente, r.json()["token"], "52000006", rostro())
    assert cliente.post("/api/votante/identificacion", json=documento("52000006")).status_code == 404


def test_no_se_puede_inscribir_dos_veces(cliente, votante):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000001"))
    assert r.status_code == 409


def test_inscripcion_a_medias_exige_los_mismos_datos(cliente):
    assert cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000009")).status_code == 200
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000009", fecha_nacimiento="1990-01-01"))
    assert r.status_code == 409
    r = cliente.post("/api/registraduria/inscripcion",
                     json=datos_persona("52000009", nombres="julieth camila", apellidos="RIVEROS  ACEVEDO"))
    assert r.status_code == 200


def test_rostro_duplicado_con_otro_documento(cliente, votante):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000002"))
    r = presentar_cedula(cliente, r.json()["token"], "52000002", con_ruido(votante["cara"]))
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": con_ruido(votante["cara"])},
                     headers=bearer(r.json()["token"]))
    assert r.status_code == 409


def test_inscripcion_exige_la_cedula_antes_del_rostro(cliente):
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000010"))
    token = bearer(r.json()["token"])
    assert cliente.post("/api/registraduria/rostro", json={"descriptor": rostro()}, headers=token).status_code == 403
    # Los tokens de la inscripción no sirven en el flujo de votación.
    assert cliente.post("/api/votante/biometria", json={"descriptor": rostro()}, headers=token).status_code == 403


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
    r = cliente.post("/api/registraduria/inscripcion", json=datos_persona("52000008"))
    r = presentar_cedula(cliente, r.json()["token"], "52000008", rostro())
    r = cliente.post("/api/registraduria/rostro", json={"descriptor": rostro()}, headers=bearer(r.json()["token"]))
    assert r.status_code == 401 and "cédula" in r.json()["detail"] and "Intentos restantes: 4" in r.json()["detail"]


def test_cedula_cifrada_y_visible_solo_para_superadmin(cliente, admin, votante):
    from sqlalchemy import select

    from app.crypto import llavero
    from app.db import SessionLocal
    from app.models import DocumentoIdentidad, Persona, Votante
    with SessionLocal() as db:
        persona = db.scalar(select(Persona).where(Persona.documento_indice == llavero.indice_documento("CC", "52000001")))
        fila = db.scalar(select(DocumentoIdentidad).where(DocumentoIdentidad.id_persona == persona.id_persona))
        assert fila.estado == "verificado" and b"PNG" not in fila.imagen
        id_votante = db.scalar(select(Votante.id_votante).where(Votante.id_persona == persona.id_persona))
    r = cliente.get(f"/api/admin/votantes/{id_votante}/cedula", headers=admin)
    assert r.status_code == 200 and r.content == foto_cedula("52000001")
    assert any(v["cedula"] for v in cliente.get("/api/admin/votantes", headers=admin).json())
    auditoria = cliente.get("/api/admin/auditoria", headers=admin).json()
    assert "VER_CEDULA" in str(auditoria)


def test_bloqueo_tras_intentos_fallidos(cliente):
    cara = rostro()
    ingresar(cliente, "52000003", cara)
    for intento in range(5):
        r = cliente.post("/api/votante/identificacion", json=documento("52000003"))
        r = cliente.post("/api/votante/biometria", json={"descriptor": rostro()}, headers=bearer(r.json()["token"]))
        assert r.status_code == (423 if intento == 4 else 401)
    assert cliente.post("/api/votante/identificacion", json=documento("52000003")).status_code == 423


def test_menor_de_edad_no_habilitado(cliente):
    menor = (datetime.now(UTC) - timedelta(days=365 * 16)).date().isoformat()
    r = ingresar(cliente, "52000004", rostro(), fecha_nacimiento=menor)
    assert not r["habilitado"] and "token" not in r
    assert next(x for x in r["requisitos"] if x["clave"] == "edad")["ok"] is False


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
        voto = db.scalars(select(Voto)).first()
        assert voto.fecha_hora.minute == 0 and voto.fecha_hora.second == 0


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
    doc = 53000000
    for id_candidato, n in eleccion_votos.items():
        for _ in range(n):
            doc += 1
            token = ingresar(cliente, str(doc), rostro())["token"]
            r = cliente.post("/api/votante/votos", headers=bearer(token),
                             json={"id_eleccion": e["id_eleccion"], "id_candidato": id_candidato})
            assert r.status_code == 201, r.text

    r = cliente.post(f"/api/admin/elecciones/{e['id_eleccion']}/cerrar", headers=admin)
    assert r.status_code == 200 and r.json()["integridad_ok"] is True
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
    assert cliente.post("/api/admin/login", json={"correo": "admin@votoseguro.gov.co", "password": "mal"}).status_code == 401
    r = cliente.post("/api/admin/usuarios", headers=admin, json={
        "correo": "supervisor@votoseguro.gov.co", "nombre": "Supervisor", "rol": "Supervisor", "password": "Supervisor2026*"})
    assert r.status_code == 201, r.text
    token = cliente.post("/api/admin/login", json={"correo": "supervisor@votoseguro.gov.co",
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
