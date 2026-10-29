# VotoSeguro — Prototipo de votación electrónica con ECC y plantilla biométrica

Implementación del trabajo de grado *"Prototipo de un sistema web de votación electrónica basado en criptografía de
curva elíptica y plantilla biométrica que garantice los principios del voto en Bogotá"* (Universidad Manuela Beltrán,
2026). La interfaz sigue el diseño de Figma (18 pantallas) y los tokens de `design-tokens/`.

| Carpeta | Contenido |
|---|---|
| `backend/` | API REST en **Python 3 + FastAPI + SQLAlchemy + PostgreSQL**, criptografía con `cryptography` |
| `frontend/` | **React 19 + Vite + Tailwind CSS 4**, reconocimiento facial con **face-api.js** en el navegador |
| `design-tokens/` | Tokens de diseño extraídos de Figma (JSON W3C y CSS) |
| `proyecto-Grado` | Documento del trabajo de grado (Markdown) |

## Cómo ejecutarlo

### Opción A — Docker (todo en uno)

```bash
cp .env.example .env          # y ponga una clave en VOTOSEGURO_MASTER_KEY (el archivo explica cómo generarla)
docker compose up --build
```

Abra <http://localhost:8000>.

### Opción B — Desarrollo local

Requisitos: Python 3.12+, Node 20+, PostgreSQL 14+.

```bash
# 1. Base de datos
createdb votoseguro      # o use: docker compose up db

# 2. Backend (http://localhost:8000, documentación interactiva en /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env     # ajuste VOTOSEGURO_DATABASE_URL
.venv/bin/uvicorn app.main:app --reload

# 3. Frontend (http://localhost:5173, redirige /api al backend)
cd ../frontend
npm install
npm run dev
```

La cámara del navegador solo funciona en `localhost` o con HTTPS.

### Datos iniciales

En el primer arranque se crean:

- La cuenta **admin@votoseguro.gov.co / Admin2026\*** (Superadministrador). Cámbiela desde *Más → Mi cuenta*.
- Si `VOTOSEGURO_SEMBRAR_DATOS_DEMO=true`: 60 votantes de ejemplo y 3 elecciones como en el diseño, una cerrada con
  47 votos, una activa y una próxima. Los candidatos son de demostración y los partidos son ficticios.

Primero inscríbase con el botón **Registraduría** de la pantalla de inicio (simula la oficina): datos personales,
foto de la cédula (cámara o archivo) y rostro, que se compara con la foto impresa. Luego entre por **Iniciar
Verificación** con su número de documento y su rostro.

### Pruebas

```bash
cd backend && .venv/bin/pytest            # SQLite temporal
VOTOSEGURO_TEST_DATABASE_URL=postgresql+psycopg://usuario@localhost/vs_test .venv/bin/pytest   # incluye el trigger
```

Cubren el cifrado ECIES y ECDSA, la plantilla cancelable, el flujo completo del votante, el voto único, la verificación
del comprobante, el bloqueo por intentos fallidos, los roles, el escrutinio con integridad, la cadena de auditoría, la
restauración de respaldos y la inmutabilidad del voto en PostgreSQL.

## Arquitectura

Sigue el diagrama de despliegue (Figura 7): navegador → servidor de aplicaciones (HTTPS) → base de datos, más un
sistema de respaldo.

```
Navegador (React)                     Servidor (FastAPI)                         PostgreSQL
─────────────────                     ──────────────────                         ──────────
Foto de la cédula ─ imagen + cara ──▶ OCR del número (Tesseract)                   ─▶ DOCUMENTO_IDENTIDAD (cifrada ECIES)
Cámara → face-api.js ─ descriptor ──▶ Servicio biométrico (plantilla cancelable) ─▶ BIOMETRIA (cifrada ECIES)
Formulario de voto ───────────────────▶ Servicio de cifrado (ECIES con la llave     ─▶ VOTO (cifrado, sin votante)
                                        pública de la elección)                        PARTICIPACION (quién votó)
Panel administrativo ─────────────────▶ Gestión electoral, reportes, auditoría,      ─▶ AUDITORIA (hash encadenado)
                                        monitoreo, respaldos (tarea cada 20 s)         respaldos/*.vsbak (cifrados)
```

## Diseño criptográfico (ECC P-256)

| Uso | Mecanismo |
|---|---|
| **Voto** | Cada elección tiene su propio par ECC. El voto se cifra con **ECIES** (ECDH efímero P-256 → HKDF-SHA256 → AES-256-GCM) usando la llave pública de la elección. El código de la elección va como dato autenticado, así que un voto no puede moverse a otra elección. Lleva relleno aleatorio: dos votos por el mismo candidato producen textos cifrados distintos. |
| **Escrutinio** | La llave privada de la elección está envuelta con la clave maestra (AES-256-GCM) y solo se usa al cerrar. Antes del cierre los resultados son inaccesibles, incluso para el administrador. |
| **Comprobante** | Código `VS-AAAA-XXXXXXXX`. Solo se guarda su SHA-256 junto con una firma **ECDSA P-256** sobre (elección, hash del voto, hash del código). Cualquiera puede verificarlo en `/verificar` sin conocer el candidato. |
| **Datos personales** | Documento, nombres, correo y fecha de nacimiento se cifran con ECIES. El documento se busca con un **índice ciego** (HMAC-SHA256), sin guardarlo en claro. |
| **Plantilla biométrica** | El descriptor facial de 128 valores se transforma con una permutación e inversión de signos secretas por usuario (**plantilla cancelable**, Abd El-Rahiem et al., 2022). La transformación conserva las distancias y puede revocarse. Tanto la plantilla como la semilla se guardan cifradas con ECIES. |
| **Cédula** | En la inscripción (Registraduría). El servidor lee el número con OCR (Tesseract) sobre la misma imagen que guarda, y el rostro en vivo debe quedar a menos de `umbral_cedula` (0,6) del descriptor de la cara impresa. Imagen y descriptor se cifran con ECIES (llave del sistema `documento`); solo el Superadministrador puede ver la imagen y cada consulta queda auditada. |
| **Auditoría** | Cada registro incluye el hash del anterior (cadena SHA-256). Alterar o borrar uno rompe la cadena, y el panel lo detecta. |
| **Respaldos** | Volcado comprimido, cifrado con ECIES y firmado con ECDSA. Se verifica la firma antes de restaurar. |
| **Sesiones** | JWT HS256 de corta duración por etapa (identificación → biometría → votación). Contraseñas con Argon2. |

## Trazabilidad de requerimientos

| Requerimiento | Implementación |
|---|---|
| RQF01–RQF03, RQF27 | `rutas/registraduria.py`: inscripción (datos, cédula con número por OCR y cara impresa en `servicios/documento.py`, enrolamiento facial). `rutas/votante.py`: identificación por documento y verificación facial, bloqueo tras 5 intentos |
| RQF04 | Paso de elegibilidad: mayor de 18, censo, sanciones, mesa |
| RQF05, RQF10, RQF11 | Restricción `UNIQUE(id_votante, id_eleccion)` + selección única + pantalla de confirmación |
| RQF06, RQF07, RQF08, RQF09, RQF18 | `rutas/admin_elecciones.py`: elecciones con fechas y candidatos con foto (solo antes del inicio) |
| RQF12, RQF13, RQF15, RQF16 | `servicios/elecciones.py`: ECIES, UUID aleatorio, hora truncada |
| RQF14 | Sin rutas de edición + **trigger** en PostgreSQL que rechaza UPDATE/DELETE sobre `voto` |
| RQF19, RQF24 | Archivar sin borrar; historial de elecciones cerradas |
| RQF20, RQF26 | Escrutinio automático al cumplirse la hora de cierre (tarea periódica) o con cierre manual |
| RQF21, RQF22, RQF23, RQF29 | Resultados, estadísticas, reporte PDF/CSV |
| RQF17, RQF25 | Cuentas con roles (Superadministrador, Administrador, Supervisor) y auditoría encadenada |
| RQF30, RQF31 | Respaldos manuales y automáticos (cada 60 min) con restauración |
| RQF32, RQNF03, RQNF21 | Tablero y página de supervisión: disponibilidad, latencia, errores, usuarios activos; log rotativo en `backend/logs/` |
| RQNF15 | `VOTO` no tiene llave hacia el votante; `PARTICIPACION` registra solo que votó |
| RQNF05, RQNF23 | Diseño móvil del Figma, botones de 58 px, etiquetas accesibles, foco visible, `prefers-reduced-motion` |

## Cambios respecto al MER del documento

- `PERSONA`: los campos personales pasan a `BYTEA` cifrado y se agrega `documento_indice` (HMAC, único) en lugar de
  `documento` en claro. Cumple la Ley 1581 de 2012.
- `VOTO`: la PK es un UUID aleatorio, `fecha_hora` se trunca a la hora y se agregan `hash_voto`, `codigo_hash` y
  `firma`. Así se corrige la posibilidad de relacionar VOTO y PARTICIPACION por la hora exacta.
- `ELECCION`: se agregan `codigo`, `tipo`, `clave_publica`, `clave_privada` (envuelta), `archivada`, `fecha_cierre` e
  `integridad_ok`.
- `CANDIDATO`: se agregan `nombre`, `partido` y `color` (datos públicos que no dependen de PERSONA).
- `AUDITORIA`: se agregan `actor`, `hash_anterior` y `hash`.
- Tablas nuevas: `RESULTADO`, `CLAVE_SISTEMA` y `RESPALDO`.
- La relación `PERSONA–BIOMETRIA` queda en `1 : 0..1`: administradores y candidatos no necesitan plantilla.

## Limitaciones conocidas (para la discusión del Capítulo IV)

1. **La extracción biométrica ocurre en el cliente.** El servidor valida el formato del descriptor, pero un cliente
   modificado podría enviar un descriptor fabricado. En producción la extracción debería hacerse en el servidor o en
   un dispositivo confiable. Lo mismo vale para la cara de la cédula: el número sí se lee en el servidor.
2. **La prueba de vida es básica**: dos retos al azar entre girar la cabeza a la izquierda, girarla a la derecha y
   sonreír. Resiste fotos impresas y videos pregrabados sencillos, pero no ataques en tiempo real ni máscaras (ver
   Vakhshiteh et al., 2021). El parpadeo se descartó como reto porque el modelo de 68 puntos de face-api casi no
   detecta el ojo cerrado y fallaba con frecuencia.
3. **Clave maestra en el mismo servidor.** Quien controle el servidor y la clave podría descifrar votos antes del
   cierre. La mejora natural es un descifrado umbral (varios custodios), como en Tejedor-Romero et al. (2021).
4. **Correlación a nivel de base de datos.** VOTO y PARTICIPACION se insertan en la misma transacción. Un
   administrador de PostgreSQL con acceso a columnas del sistema (`xmin`) podría relacionarlos. Una mezcla (mixnet)
   o un conteo homomórfico eliminaría ese riesgo.
5. **Resistencia a la coacción limitada**, como en todo voto remoto: el votante podría votar frente a un tercero.
   Estonia lo mitiga permitiendo votar de nuevo; en este prototipo el voto es único e inmutable (RQF14).
6. El "censo" es la tabla de votantes del prototipo; no hay integración con la Registraduría.
7. **La cédula se valida solo por su imagen.** Se comprueban el número impreso y la cara, pero no la autenticidad del
   documento: una cédula falsificada con datos y foto coherentes pasaría. Validarla exigiría leer el chip o el código
   de barras de la cédula digital y consultarlo con la Registraduría.
