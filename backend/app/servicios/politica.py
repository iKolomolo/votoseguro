"""Política de Tratamiento de Datos Personales de VotoSeguro (Ley 1581 de 2012; Decreto 1377 de 2013, art. 13,
compilado en el Decreto 1074 de 2015).

Es la única fuente del texto: la página /privacidad lo pide a /api/publico/politica y docs/politica-tratamiento-
datos.md se genera desde aquí (`python -m app.servicios.politica`). Los datos de contacto, el fin del piloto y los
plazos salen de la configuración, así que el texto siempre coincide con lo que hace el sistema. El marcado
**así** indica negrilla. Cada versión lleva una huella SHA-256 para poder probar qué texto estaba publicado.

IMPORTANTE: si cambia lo que el sistema hace con los datos, hay que cambiar este texto y subir VERSION. Una
política que promete algo que el sistema no cumple es un incumplimiento, no una protección.
"""
import hashlib
import json
from datetime import date
from functools import lru_cache

from ..config import get_settings
from .consultas import EDAD_MINIMA

VERSION = "1.4"
VIGENTE_DESDE = date(2026, 11, 11)
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]


def _fecha(d: date) -> str:
    return f"{d.day} de {_MESES[d.month - 1]} de {d.year}"


@lru_cache
def texto() -> dict:
    s = get_settings()
    fin = _fecha(s.fin_piloto)
    correo = s.correo_privacidad
    contenido = {
        "version": VERSION,
        "vigente_desde": VIGENTE_DESDE.isoformat(),
        "titulo": "Política de Tratamiento de Datos Personales",
        "subtitulo": "VotoSeguro — prototipo académico de votación electrónica",
        "resumen": [
            "VotoSeguro es una **simulación académica**: no es de la Registraduría y no tiene efectos electorales.",
            "Solo pedimos los datos necesarios para inscribirle, comprobar que es usted y que vote una sola vez.",
            "Las fotos de su cédula **no se guardan**. Su voto **no queda unido a su identidad**.",
            "El piloto usa su rostro para verificar que es usted. Participar es **voluntario**: si no quiere, no "
            "participa, sin ninguna consecuencia.",
            f"Todo se guarda cifrado y se borra a más tardar el **{fin}**.",
            f"No vendemos ni compartimos sus datos. Puede consultarlos, corregirlos o pedir que se borren: {correo}.",
        ],
        "secciones": [
            {"id": "responsables", "titulo": "1. Quiénes son los Responsables del Tratamiento", "texto": (
                f"Los Responsables del Tratamiento son **{s.responsables}**, personas naturales, estudiantes de la "
                "programa de Ingeniería de Software de la Universidad Manuela Beltrán y autores del trabajo de grado "
                "\"Prototipo de un sistema web de "
                "votación electrónica basado en criptografía de curva elíptica y plantilla biométrica\". Actúan "
                "como **Responsables conjuntos**: deciden juntos qué datos se recogen, para qué y cómo se "
                "protegen, y responden solidariamente por los deberes de esta política.\n\n"
                f"**Domicilio:** Bogotá D.C., Colombia. **Dirección:** {s.direccion_responsables}. "
                f"**Teléfono:** {s.telefono_responsables}. **Correo para asuntos de datos personales:** {correo}.\n\n"
                "La Universidad Manuela Beltrán no es Responsable ni Encargada de estos datos: no los recibe, no "
                "los administra y no decide sobre ellos. Ninguna otra persona (incluidos el director del trabajo "
                "de grado y los jurados) tiene acceso al panel de administración ni a los datos de los "
                "participantes: **solo los tres Responsables**.")},
            {"id": "alcance", "titulo": "2. Qué es VotoSeguro y a quién aplica esta política", "texto": (
                "VotoSeguro es un **prototipo académico** que simula un proceso de votación para evaluar técnicas "
                "de seguridad. **No pertenece a la Registraduría Nacional del Estado Civil, no está conectado con "
                "ella ni con ninguna autoridad electoral, y ningún voto emitido aquí tiene efectos electorales, "
                "políticos ni jurídicos.** La \"Registraduría\" que aparece en el sistema es una simulación.\n\n"
                "Esta política aplica a todos los datos personales que el sistema trata durante la prueba piloto: "
                "los de las personas que se inscriben y votan, los de los administradores y los de los candidatos "
                "de las elecciones simuladas. Aplica en el sitio web, en la API y en las copias de seguridad.\n\n"
                "**Participación voluntaria.** Las personas que se inscriben en el piloto lo hacen de forma "
                "**libre y voluntaria** para colaborar con un proyecto académico, aunque tengan una relación "
                "familiar o personal con los Responsables. Participar no da ningún beneficio, y no participar "
                "o retirarse en cualquier momento no tiene ninguna consecuencia. Para retirarse basta con "
                "pedirlo (numeral 14).")},
            {"id": "marco", "titulo": "3. Marco legal", "lista": [
                "Constitución Política de Colombia, arts. 15 (intimidad y hábeas data) y 20.",
                "Ley Estatutaria 1581 de 2012, de protección de datos personales.",
                "Decreto 1377 de 2013, compilado en el Decreto Único Reglamentario 1074 de 2015 (Libro 2, Parte 2, "
                "Título 2, Capítulo 25).",
                "Decreto 090 de 2018 (Registro Nacional de Bases de Datos).",
                "Circular Única de la Superintendencia de Industria y Comercio (SIC), Título V, incluidas las "
                "Circulares Externas 005 de 2017 (países con nivel adecuado de protección) y 003 de 2018.",
                "Ley 1273 de 2009 (delitos informáticos) y Código Penal.",
                "Sentencia C-748 de 2011 de la Corte Constitucional y las demás normas y decisiones que las "
                "modifiquen, complementen o interpreten.",
            ]},
            {"id": "definiciones", "titulo": "4. Definiciones", "lista": [
                "**Dato personal:** cualquier información que identifica o puede identificar a una persona.",
                "**Dato sensible:** el que afecta la intimidad o puede causar discriminación, como los **datos "
                "biométricos** (por ejemplo, su rostro) y la **opinión u orientación política** (Ley 1581, art. 5).",
                "**Titular:** la persona a quien se refieren los datos; en este caso, usted.",
                "**Tratamiento:** cualquier operación con los datos: recogerlos, guardarlos, usarlos, circularlos "
                "o borrarlos.",
                "**Responsable:** quien decide sobre la base de datos y el Tratamiento.",
                "**Encargado:** quien trata los datos por cuenta del Responsable (aquí, los proveedores de "
                "alojamiento).",
                "**Autorización:** su consentimiento previo, expreso e informado para el Tratamiento.",
                "**Transmisión:** comunicar datos a un Encargado para que los trate por cuenta del Responsable.",
                "**Transferencia:** enviar datos a otro Responsable. VotoSeguro **no hace transferencias**.",
                "**Plantilla biométrica cancelable:** representación numérica y transformada de su rostro que "
                "sirve para compararlo, que no permite reconstruir su imagen y que se puede anular.",
            ]},
            {"id": "principios", "titulo": "5. Principios que seguimos", "texto": (
                "Tratamos los datos según los principios de la Ley 1581 (art. 4) y de la sentencia C-748 de 2011:"),
             "lista": [
                "**Legalidad:** solo hacemos lo que la ley permite.",
                "**Finalidad:** los datos se usan solo para lo que se dice en esta política.",
                "**Libertad:** nada se trata sin su autorización, salvo los casos que la ley exceptúa.",
                "**Necesidad:** no pedimos más datos de los indispensables. Por eso las fotos de su cédula no se "
                "guardan.",
                "**Veracidad:** los datos se confirman contra su cédula y usted puede corregirlos.",
                "**Transparencia:** usted puede saber en todo momento qué datos suyos tenemos.",
                "**Acceso y circulación restringida:** solo los Responsables acceden, y los datos no se publican.",
                "**Seguridad y confidencialidad:** los datos se cifran y quien los trata guarda reserva, incluso "
                "después de terminar el proyecto.",
                "**Temporalidad:** los datos se borran cuando dejan de ser necesarios.",
            ]},
            {"id": "datos", "titulo": "6. Qué datos tratamos, para qué y por cuánto tiempo",
             "texto": "Estos son **todos** los datos que el sistema trata. No se usan para ninguna otra finalidad.",
             "tabla": {
                "columnas": ["Dato", "Para qué se usa", "Cuánto tiempo se conserva"],
                "filas": [
                    ["Tipo y número de documento",
                     "Identificarle, confirmar que coincide con su cédula y evitar que alguien se inscriba dos veces.",
                     f"Hasta el {fin} o hasta que pida borrarlo. Se guarda cifrado; para buscarlo se usa un código "
                     "derivado que no revela el número."],
                    ["Nombres y apellidos",
                     "Identificarle, confirmar que coinciden con su cédula y dirigirnos a usted.",
                     f"Hasta el {fin} o hasta que pida borrarlos. Cifrados."],
                    ["Fecha de nacimiento",
                     f"Comprobar que tiene {EDAD_MINIMA} años cumplidos, y confirmar que coincide con su cédula.",
                     f"Hasta el {fin} o hasta que pida borrarla. Cifrada."],
                    ["Correo electrónico (y teléfono, si lo da)",
                     "Contactarle, responder sus solicitudes y avisarle de cambios en esta política.",
                     f"Hasta el {fin} o hasta que pida borrarlo. Cifrado."],
                    ["Fotos de las dos caras de la cédula",
                     "Leer automáticamente el número, los nombres, los apellidos y la fecha de nacimiento. No se "
                     "analizan la huella dactilar, la firma ni los demás datos impresos.",
                     "**No se guardan.** Se procesan en la memoria RAM del servidor (el lector de texto usa un archivo "
                     "temporal que también está en memoria, nunca en el disco) y se descartan en la misma operación. "
                     "Solo queda una "
                     "huella SHA-256 de cada foto (un código que no permite reconstruirla) y el resultado de la "
                     "verificación."],
                    ["Rostro impreso en la cédula (dato sensible)",
                     "Compararlo con su rostro en vivo para comprobar que la cédula es suya.",
                     f"Solo mientras termina la inscripción, cifrado (máximo {s.minutos_inscripcion} minutos). "
                     "**No se guarda.**"],
                    ["Rostro capturado con la cámara (dato sensible)",
                     "Inscribirle y comprobar que es usted cada vez que vota o consulta sus datos.",
                     "El video **no sale de su dispositivo**: su navegador calcula 128 valores numéricos y, para la "
                     "prueba de vida, la posición de 68 puntos del rostro (ojos, nariz, boca, contorno) en 4 momentos. "
                     "Solo eso se envía. Los puntos se usan en el momento y **no se guardan**. Se guarda una plantilla "
                     f"cancelable cifrada hasta el {fin} o hasta que la revoque."],
                    ["Estado de habilitación y mesa",
                     "Saber si puede votar.",
                     f"Hasta el {fin} o hasta que pida borrarlo."],
                    ["Contadores de intentos (de su conexión y de su documento, guardados como un código que no "
                     "revela ni la IP ni el número)",
                     "Frenar ataques: tras 5 rostros que no coinciden con un documento, ese documento se pausa 30 "
                     "minutos, y cada conexión tiene un máximo de intentos.",
                     "Solo mientras dura la pausa o la ventana de conteo (minutos); luego se borran."],
                    ["Participación (que usted votó en una elección, sin decir por quién)",
                     "Garantizar que cada persona vote una sola vez.",
                     "Solo se guarda el día, no la hora. Hasta 30 días después del cierre de cada elección, plazo "
                     "para reclamaciones; después se desvincula de su identidad."],
                    ["Voto",
                     "Contar los votos y permitirle verificar que el suyo fue contado.",
                     "Se guarda cifrado, **sin ningún vínculo con su identidad**, mezclado con los demás y con la "
                     "hora del cierre de la votación, así que no es un dato personal. Se conserva con los resultados "
                     "de la simulación."],
                    ["Prueba de su autorización (versión del texto, casillas marcadas y fecha)",
                     "Demostrar que usted autorizó el Tratamiento, como exige la ley.",
                     "Mientras se traten sus datos y hasta 3 años después de borrarlos, sin su nombre ni su número de "
                     "documento legible."],
                    ["Dirección IP, fecha, hora y resultado de las acciones (bitácora de auditoría)",
                     "Seguridad del sistema, detección de fraudes y atención de incidentes.",
                     f"Hasta un año después del {fin}. La bitácora no guarda nombres ni números de documento de los "
                     "participantes; sí guarda el correo del administrador que hizo cada acción, para saber quién "
                     "fue."],
                    ["Copias de seguridad",
                     "Recuperar el sistema si falla.",
                     "Máximo 7 días, cifradas y firmadas. Así, un dato que usted pida borrar desaparece también de "
                     "todas las copias en ese plazo."],
                    ["Administradores: nombre, correo, contraseña y accesos",
                     "Operar el sistema y saber quién hizo cada acción.",
                     "Mientras la cuenta esté activa; las acciones que hicieron quedan en la bitácora con su correo "
                     "durante el plazo de la bitácora. La contraseña nunca se guarda: solo un resumen Argon2 que no "
                     "permite recuperarla."],
                    ["Candidatos de las elecciones simuladas: nombre, partido, foto y descripción",
                     "Mostrar el tarjetón de la simulación.",
                     f"Hasta el {fin}. **Son ficticios**: no corresponden a personas reales ni a partidos reales."],
                ],
            }},
            {"id": "sensibles", "titulo": "7. Datos sensibles", "texto": (
                "**Datos biométricos.** Su rostro (el de la cédula y el de la cámara) es un dato sensible. Solo se "
                "trata si usted lo autoriza de forma **expresa y separada**, en una casilla distinta a la de los "
                "demás datos. **Usted no está obligado(a) a entregar datos sensibles** (Ley 1581, arts. 6 y 8). "
                "El objeto de este piloto académico es precisamente evaluar la verificación de identidad con el "
                "rostro, por lo que esta autorización es necesaria para participar. La participación es "
                "**totalmente voluntaria** y no es un servicio ni un trámite: quien no quiera entregar su rostro "
                "simplemente no participa, sin ninguna consecuencia, y no pierde ningún derecho ni beneficio. Puede "
                "revocar esta autorización en cualquier momento desde \"Mis datos personales\": su plantilla se "
                "borra de inmediato y, desde ese momento, ya no podrá votar en el piloto salvo que vuelva a "
                "inscribirse.\n\n"
                "**Opinión política.** Su voto revela una preferencia política, que también es un dato sensible. "
                "Por eso el sistema **separa el voto de su identidad**:\n\n"
                "- El voto se cifra con la llave de la elección y se guarda **sin ningún enlace con usted**.\n"
                "- Mientras la votación está abierta, todos los votos están juntos en una **urna digital que se "
                "mezcla** cada vez que alguien vota, así que su posición no indica quién lo emitió.\n"
                "- Al cerrar la votación, los votos pasan a su registro definitivo **en orden aleatorio y todos con "
                "la misma hora** (la del cierre).\n"
                "- El registro de que usted votó guarda **solo el día**, no la hora.\n"
                "- Los votos se descifran **solo al cerrar la votación**, todos juntos, para contarlos.\n\n"
                "Así, con lo que queda guardado no es posible saber por quién votó una persona. **Límite que debe "
                "conocer:** los Responsables administran el servidor y sus llaves. Alguien con ese acceso que vigilara "
                "el servidor en el momento exacto en que usted vota, o que comparara copias de seguridad hechas "
                "durante la votación, podría intentar relacionar su voto con usted. Los Responsables **se "
                "comprometen expresamente a no hacerlo**, y las copias de seguridad se borran a los 7 días: pasado "
                "ese plazo después del cierre, no queda ninguna forma de relacionar un voto con una persona.")},
            {"id": "menores", "titulo": "8. Menores de edad", "texto": (
                f"VotoSeguro **no trata datos de menores de {EDAD_MINIMA} años**. El sistema calcula su edad con la "
                f"fecha de nacimiento confirmada en su cédula y rechaza la inscripción si no tiene {EDAD_MINIMA} años "
                "cumplidos, antes de pedir cualquier foto. Del rechazo solo queda en la bitácora la anotación "
                "\"Menor de edad\", sin el documento ni la fecha. Si llegamos a saber que se inscribió un menor, "
                "borraremos sus datos.")},
            {"id": "autorizacion", "titulo": "9. Cómo obtenemos su autorización", "texto": (
                "Antes de pedirle cualquier dato, el sistema le muestra el texto de la autorización y le pide marcar "
                "dos casillas que aparecen **desmarcadas**: una para los datos personales (necesaria para "
                "inscribirse) y otra, separada y expresa, para los datos biométricos, que también es necesaria "
                "para participar (numeral 7). Se guarda la prueba de lo que aceptó: "
                "la versión del texto, su huella SHA-256, las casillas y la fecha (Decreto 1377, arts. 7 y 8). "
                "Puede ver esa prueba en \"Mis datos personales\" o pedir una copia por correo.\n\n"
                "La inscripción es **todo o nada**: nada se guarda hasta que la termine. Si la abandona o pasan "
                f"{s.minutos_inscripcion} minutos, se descarta y no queda ningún dato suyo.\n\n"
                "La ley permite tratar datos sin autorización en casos excepcionales (Ley 1581, art. 10), como el "
                "requerimiento de una autoridad pública o judicial en ejercicio de sus funciones. Si eso ocurre, "
                "solo entregaremos lo estrictamente pedido y, si la ley lo permite, se lo informaremos.")},
            {"id": "automatizadas", "titulo": "10. Verificaciones automáticas", "texto": (
                "Para confirmar su identidad, el sistema hace tres comprobaciones automáticas: lee su cédula con "
                "reconocimiento óptico de caracteres (OCR), compara su rostro con el de la cédula y con su plantilla, "
                "y hace una **prueba de vida**: le pide tres movimientos elegidos al azar (girar la cabeza, sonreír "
                "o abrir la boca) para comprobar que frente a la cámara hay una persona y no una foto."
                " Estas comprobaciones **pueden equivocarse**, por ejemplo con una foto borrosa "
                "o con poca luz. Si el sistema le rechaza, puede repetir la foto o "
                "presentar un reclamo para que una persona del equipo revise su caso. Ninguna decisión automática "
                "tiene efectos jurídicos sobre usted, porque la votación es simulada.")},
            {"id": "derechos", "titulo": "11. Sus derechos", "texto": (
                "Como titular, usted tiene derecho a (Ley 1581, art. 8):"), "lista": [
                "**Conocer, actualizar y rectificar** sus datos, incluidos los parciales, inexactos, incompletos o "
                "que induzcan a error.",
                "**Pedir prueba de la autorización** que nos dio.",
                "**Ser informado(a)**, si lo pide, de cómo se han usado sus datos.",
                "**Presentar quejas ante la Superintendencia de Industria y Comercio** por infracciones a la ley, "
                "después de haber hecho su consulta o reclamo ante nosotros.",
                "**Revocar la autorización y pedir que se borren sus datos** cuando no se respeten sus derechos o "
                "cuando ya no quiera que los tratemos, salvo un deber legal que obligue a conservarlos (ver "
                "numeral 14).",
                "**Acceder gratis** a sus datos, al menos una vez al mes y cada vez que esta política cambie de "
                "forma sustancial (Decreto 1377, art. 21).",
            ]},
            {"id": "legitimados", "titulo": "12. Quién puede ejercer los derechos", "lista": [
                "Usted, demostrando su identidad.",
                "Sus causahabientes (herederos), demostrando esa calidad.",
                "Su representante o apoderado(a), con el poder correspondiente.",
                "Quien usted haya autorizado por estipulación a favor de otro.",
            ], "texto": "Así lo dispone el art. 20 del Decreto 1377. No entregamos datos a nadie más."},
            {"id": "procedimiento", "titulo": "13. Cómo hacer una consulta o un reclamo", "texto": (
                "**Quién atiende:** los tres Responsables atienden conjuntamente todas las solicitudes, sin costo, "
                f"por el correo **{correo}**, en la dirección o en el teléfono del numeral 1. Muchas cosas las puede hacer usted mismo(a) en la sección **\"Mis datos "
                "personales\"**, identificándose con su documento y su rostro: ver qué datos tenemos, ver la prueba "
                "de su autorización y revocar el uso de su rostro (el borrado es inmediato).\n\n"
                "Para proteger sus datos, antes de responder comprobaremos que quien pide es el titular o alguien "
                "legitimado. Puede que le pidamos información adicional para ello; nunca le pediremos su contraseña "
                "ni fotos de su cédula por correo.\n\n"
                "**Consultas** (saber qué datos tenemos o cómo se usaron, Ley 1581, art. 14): se responden en máximo "
                "**10 días hábiles** desde que las recibimos. Si no es posible, le diremos el motivo antes de que "
                "venza el plazo y responderemos en máximo 5 días hábiles más.\n\n"
                "**Reclamos** (corregir, actualizar o borrar datos, revocar la autorización o denunciar un "
                "incumplimiento, Ley 1581, art. 15): deben incluir su identificación, la descripción de los hechos, "
                "una dirección o correo para responderle y los documentos que quiera aportar. Si el reclamo está "
                "incompleto, le pediremos completarlo dentro de los 5 días siguientes; si pasan 2 meses sin que lo "
                "haga, se entenderá que desistió. Dentro de los 2 días hábiles siguientes a recibir un reclamo "
                "completo, marcaremos sus datos con la leyenda \"reclamo en trámite\". Se responde en máximo **15 "
                "días hábiles**; si no es posible, le diremos el motivo y responderemos en máximo 8 días hábiles "
                "más.\n\n"
                "**Queja ante la SIC:** solo puede presentarse después de hacer la consulta o el reclamo ante "
                "nosotros (Ley 1581, art. 16). La autoridad es la Delegatura para la Protección de Datos Personales "
                "de la Superintendencia de Industria y Comercio, www.sic.gov.co.")},
            {"id": "supresion", "titulo": "14. Revocatoria y borrado de los datos", "texto": (
                "Puede revocar su autorización o pedir que borremos sus datos en cualquier momento. Revocar solo la "
                "autorización biométrica borra su plantilla al instante y ya no podrá votar en el piloto salvo que se "
                "inscriba de nuevo. "
                "Pedir el borrado total elimina su inscripción.\n\n"
                "La ley permite negar el borrado solo cuando un deber legal o contractual obliga a conservar los "
                "datos (Decreto 1377, art. 9). En VotoSeguro hay dos casos, y solo por el tiempo indicado en el "
                "numeral 6: la **prueba de su autorización**, sin su nombre ni su número legible, para poder "
                "demostrar ante la SIC que actuamos con su consentimiento; y la **participación** en una elección "
                "que esté en curso o cerrada hace menos de 30 días, para garantizar el voto único. Si su solicitud "
                "queda en alguno de estos casos, se lo explicaremos por escrito.\n\n"
                "Los datos borrados desaparecen de las copias de seguridad en máximo 7 días. Si hubiera que "
                "restaurar una copia, se vuelven a aplicar los borrados hechos después de esa copia.")},
            {"id": "deberes", "titulo": "15. Nuestros deberes", "texto": (
                "Como Responsables nos comprometemos a cumplir los deberes del art. 17 de la Ley 1581, en especial:"),
             "lista": [
                "Garantizarle en todo momento el ejercicio de sus derechos.",
                "Pedir y conservar la prueba de su autorización, e informarle para qué se recogen sus datos.",
                "Proteger los datos para impedir su adulteración, pérdida, consulta, uso o acceso no autorizado.",
                "Mantener los datos veraces y actualizados, y corregirlos cuando no lo estén.",
                "Exigir a los Encargados que respeten la seguridad y la privacidad de los datos.",
                "Tramitar consultas y reclamos en los plazos de la ley.",
                "Informar a la SIC cuando haya violaciones a los códigos de seguridad y riesgos para los datos.",
                "Cumplir las instrucciones de la Superintendencia de Industria y Comercio.",
            ]},
            {"id": "encargados", "titulo": "16. Dónde se alojan los datos y quién más los trata", "texto": (
                "El sistema se aloja en servicios de **Render** (aplicación y base de datos) y **Vercel** (sitio "
                "web), con servidores en los **Estados Unidos de América**, país que la SIC reconoce con un nivel "
                "adecuado de protección de datos (Circular Externa 005 de 2017). Esas empresas actúan como "
                "**Encargadas**: solo almacenan y procesan los datos por cuenta de los Responsables, bajo sus "
                "términos de tratamiento de datos, y no pueden usarlos para fines propios. Esto es una "
                "**transmisión internacional** (Ley 1581, art. 26; Decreto 1377, arts. 24 y 25), que usted autoriza "
                "al aceptar el Tratamiento. Los datos viajan siempre cifrados (HTTPS) y se guardan cifrados.\n\n"
                "**No vendemos, alquilamos, cedemos ni compartimos sus datos con nadie más**, y no los usamos para "
                "publicidad, perfiles ni fines políticos. En el documento de grado, sus presentaciones y cualquier "
                "publicación académica solo se usan **estadísticas anónimas** o datos de prueba, que no permiten "
                "identificar a nadie.")},
            {"id": "seguridad", "titulo": "17. Cómo protegemos los datos", "lista": [
                "Los datos personales se guardan **cifrados** con criptografía de curva elíptica (ECIES con curva "
                "P-256 y AES-256-GCM), con llaves separadas para los datos personales, la biometría, la cédula, las "
                "firmas y los respaldos, y una llave propia para cada elección.",
                "El número de documento se busca con un índice ciego (HMAC), sin descifrarlo.",
                "La plantilla del rostro es **cancelable**: se transforma con una semilla secreta, no permite "
                "reconstruir su imagen y se puede anular.",
                "Las fotos de la cédula **no se guardan** en ningún momento.",
                "Las contraseñas de los administradores se guardan con Argon2; el acceso se controla por roles y se "
                "bloquea tras varios intentos fallidos.",
                "La **prueba de vida** la comprueba también el servidor, con retos que él mismo elige al azar.",
                "Hay **límites de intentos** por conexión y por documento, y el sistema responde igual esté o no "
                "inscrito un documento: con solo un número de cédula nadie puede averiguar si una persona participa.",
                "Cada acción queda en una **bitácora de auditoría encadenada** con SHA-256: si alguien la altera, "
                "se detecta.",
                "Las copias de seguridad están cifradas y firmadas.",
                "En su navegador no usamos cookies de rastreo, publicidad ni analítica. La sesión se guarda en el "
                "almacenamiento temporal de la pestaña y se borra al cerrarla. La cámara solo se activa con su "
                "permiso y durante la captura.",
                "Los Responsables guardan reserva sobre los datos, incluso después de terminar el proyecto.",
            ], "texto": (
                "Estas medidas son razonables para el riesgo del piloto, pero ningún sistema conectado a internet es "
                "invulnerable. Por eso también tenemos un procedimiento para los incidentes (numeral 18).")},
            {"id": "incidentes", "titulo": "18. Si ocurre un incidente de seguridad", "texto": (
                "Si detectamos un acceso no autorizado, una pérdida o una filtración de datos: lo contendremos de "
                "inmediato (por ejemplo, cambiando llaves y cerrando sesiones), evaluaremos qué datos y qué personas "
                "se vieron afectadas, lo reportaremos a la Superintendencia de Industria y Comercio en máximo 15 días "
                "hábiles desde que lo detectemos, **le avisaremos** escribiéndole desde el correo de contacto "
                "a la dirección que nos dio, si sus datos estuvieron "
                "comprometidos, con recomendaciones para protegerse, y dejaremos registro de lo ocurrido.")},
            {"id": "usuario", "titulo": "19. Sus compromisos como usuario", "texto": (
                "Al usar VotoSeguro usted se compromete a:"), "lista": [
                "Dar información **verdadera** y usar solo **su propia** cédula y **su propio** rostro.",
                "No inscribir a otra persona ni hacerse pasar por ella. Suplantar a alguien puede ser el delito de "
                "**falsedad personal** (Código Penal, art. 296), y usar datos ajenos sin permiso, el de **violación "
                "de datos personales** (Código Penal, art. 269F, Ley 1273 de 2009).",
                "No intentar acceder sin permiso, alterar ni bloquear el sistema, lo que puede constituir los "
                "delitos de los arts. 269A a 269G del Código Penal.",
                "Si detectamos un uso fraudulento, podremos bloquear la inscripción y conservar la evidencia "
                "necesaria (bitácora) para informar a las autoridades.",
            ]},
            {"id": "alcance-responsabilidad", "titulo": "20. Carácter académico del sistema", "texto": (
                "VotoSeguro es un prototipo en evaluación y puede tener fallas o interrupciones. Como la votación es "
                "simulada, sus resultados no sirven como prueba de ninguna elección real ni deben usarse para "
                "tomar decisiones. Nada de lo dicho en este numeral limita sus derechos como titular ni nuestros "
                "deberes como Responsables, que se mantienen completos según la ley.")},
            {"id": "rnbd", "titulo": "21. Registro Nacional de Bases de Datos", "texto": (
                "Según el Decreto 090 de 2018, deben inscribir sus bases de datos ante la SIC las sociedades y "
                "entidades sin ánimo de lucro con activos superiores a 100.000 UVT y las entidades públicas. Los "
                "Responsables son personas naturales y el proyecto es académico, por lo que no están obligados a "
                "ese registro. Aun así, cumplen todos los demás deberes de la Ley 1581.")},
            {"id": "cambios", "titulo": "22. Cambios a esta política", "texto": (
                "Si cambiamos esta política de forma sustancial, en especial sobre quiénes son los Responsables o "
                "para qué se usan sus datos, se lo informaremos en el sitio y escribiéndole desde el correo de "
                "contacto, **antes** de aplicar el "
                "cambio. Si cambian las finalidades, le pediremos una **nueva autorización**. Cada versión tiene un "
                "número, una fecha y una huella SHA-256, y conservamos las anteriores.")},
            {"id": "vigencia", "titulo": "23. Vigencia", "texto": (
                f"Esta política (versión {VERSION}) rige desde el **{_fecha(VIGENTE_DESDE)}**. La base de datos del "
                f"piloto estará vigente hasta el **{fin}**. Llegada esa fecha, el sistema cierra las inscripciones "
                "y borra las plantillas biométricas y los datos personales, y solo se conservan las estadísticas "
                "anónimas y lo indicado en el numeral 6. Esta política se rige por las leyes de la República de "
                "Colombia.")},
        ],
    }
    contenido["hash"] = hashlib.sha256(json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return contenido


def markdown() -> str:
    """El mismo texto en Markdown, para docs/politica-tratamiento-datos.md."""
    t = texto()
    partes = [f"# {t['titulo']}", "", f"**{t['subtitulo']}**", "",
              f"Versión {t['version']} · Vigente desde el {_fecha(date.fromisoformat(t['vigente_desde']))} · "
              f"Huella SHA-256: `{t['hash']}`", "", "> Generado desde `backend/app/servicios/politica.py`. No lo "
              "edite a mano: cambie ese archivo y vuelva a generarlo.", "", "## En resumen", ""]
    partes += [f"- {linea}" for linea in t["resumen"]]
    for s in t["secciones"]:
        partes += ["", f"## {s['titulo']}", ""]
        if s.get("texto") and not s.get("lista"):
            partes.append(s["texto"])
        elif s.get("texto") and s.get("lista") and s["texto"].endswith(":"):
            partes += [s["texto"], ""]
        if s.get("lista"):
            partes += [f"- {item}" for item in s["lista"]]
            if s.get("texto") and not s["texto"].endswith(":"):
                partes += ["", s["texto"]]
        if s.get("tabla"):
            cols = s["tabla"]["columnas"]
            partes += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            partes += ["| " + " | ".join(celda.replace("|", "\\|") for celda in fila) + " |"
                       for fila in s["tabla"]["filas"]]
    return "\n".join(partes).replace("\n\n\n", "\n\n") + "\n"


if __name__ == "__main__":
    print(markdown(), end="")
