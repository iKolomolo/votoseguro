# Plan de cambios: protección de datos personales en VotoSeguro

**Estado:** decisiones cerradas (ver §15), listo para implementar. No se ha modificado código.
**Base:** informe *Cédula en imagen y ley colombiana* (`reports/`), Ley Estatutaria 1581 de 2012, Decreto 1377 de 2013 (compilado en el Decreto Único 1074 de 2015, Libro 2, Parte 2, Título 2, Capítulo 25), doctrina y decisiones de la SIC y jurisprudencia de la Corte Constitucional.

> Este documento es un plan técnico-jurídico para un prototipo académico. No es asesoría legal formal. Los puntos marcados **[verificar]** dependen de fuentes que no se pudieron leer en su texto oficial y deben confirmarse antes de citarlos en la tesis.

---

## 1. Decisiones que este plan toma

| Tema | Decisión | Fundamento principal |
|---|---|---|
| Imagen de la cédula | **No se almacena.** Se procesa en memoria (OCR del número y extracción del rostro) y se descarta en la misma petición. | Decreto 1377 art. 4 (datos "pertinentes y adecuados"), art. 11 (temporalidad); C-748/11; T-208/26 |
| Descriptor facial de la cédula | Se guarda cifrado **solo mientras termina la inscripción** (máximo 30 minutos) y se borra al registrar el rostro. | Decreto 1377 art. 11; principio de necesidad |
| Plantilla biométrica del rostro | Se conserva cifrada y cancelable **hasta el fin del piloto** o hasta que el titular la revoque. | Ley 1581 arts. 6(a) y 8(e); Decreto 1377 arts. 9 y 11 |
| Autorización | Dos casillas **separadas y desmarcadas**: datos personales (necesaria para inscribirse) y datos sensibles biométricos (opcional). Se guarda prueba con versión y fecha. | Ley 1581 arts. 6(a), 9 y 12; Decreto 1377 arts. 5–8 |
| Alternativa sin biometría | Quien no autorice la biometría vota de forma **presencial asistida**: un jurado verifica la cédula física en persona y habilita una única sesión de voto. | Decreto 1377 art. 6 ("Ninguna actividad podrá condicionarse…"); SIC Res. 16582/2025 y 52185/2025 |
| Menores de edad | **No se inscriben.** La inscripción exige 18 años cumplidos. | Ley 1581 art. 7; la cédula de ciudadanía solo se expide desde los 18 años |
| Política de Tratamiento | Página pública `/privacidad`, enlazada desde la autorización y el pie de página. | Decreto 1377 art. 13 |
| Derechos del titular | Nueva sección "Mis datos" (consultar, revocar, suprimir) y bandeja de solicitudes en el panel con plazos legales. | Ley 1581 arts. 8, 14 y 15 |
| Retención | Plazos por categoría de dato, borrado automático y **respaldos que caducan a los 7 días**. | Decreto 1377 arts. 11 y 13 |
| Alojamiento en EE. UU. | Se informa en la autorización y se documenta la transmisión a Render y Vercel (Encargados). | Ley 1581 art. 26; Decreto 1377 arts. 24–25; Circular SIC 005/2017 |

---

## 2. Marco normativo aplicable

| Norma | Qué exige para VotoSeguro |
|---|---|
| **Ley 1581 de 2012, art. 3** | Define Responsable, Encargado, Titular y Tratamiento. Los estudiantes que deciden qué datos se recogen y para qué son el **Responsable**. Render y Vercel son **Encargados**. |
| **Art. 4** | Principios: legalidad, finalidad, libertad, veracidad, transparencia, acceso y circulación restringida, seguridad y confidencialidad. |
| **Art. 5** | "los datos biométricos" son **datos sensibles**. Aplica a la foto de la cédula cuando se usa para cotejo, al descriptor y a la plantilla. |
| **Art. 6** | Se prohíbe tratar datos sensibles salvo excepciones. La única aplicable es la **(a): autorización explícita**. La (e), fines científicos, exige suprimir la identidad, así que solo sirve para estadísticas anónimas del piloto. |
| **Art. 7** | Datos de niños, niñas y adolescentes: tratamiento restringido. Motivo para no inscribir menores. |
| **Art. 8** | Derechos del titular: conocer, actualizar, rectificar, pedir prueba de la autorización, ser informado del uso, quejarse ante la SIC, **revocar y pedir supresión**, acceder gratis. |
| **Art. 9** | Autorización previa, expresa e informada, que pueda consultarse después. |
| **Art. 12** | Información obligatoria al titular: tratamiento y finalidad; carácter facultativo de las respuestas sobre datos sensibles; derechos; identificación, dirección y teléfono del Responsable. |
| **Arts. 14 y 15** | Consultas: 10 días hábiles (+5). Reclamos: 15 días hábiles (+8). |
| **Arts. 17 y 18** | Deberes de Responsable y Encargado: seguridad, confidencialidad, conservar la autorización, tramitar consultas y reclamos, **informar a la SIC los incidentes de seguridad** (17-n). |
| **Art. 23** | Sanciones: multas de hasta 2.000 SMMLV, suspensión, cierre temporal y cierre inmediato y definitivo de operaciones con datos sensibles. |
| **Art. 26** | Transferencias internacionales a países con nivel adecuado de protección. |
| **Decreto 1377 de 2013, art. 3** | Distingue transferencia (a otro Responsable) de **transmisión** (a un Encargado). |
| **Art. 4** | Recolección limitada a datos "pertinentes y adecuados para la finalidad". |
| **Art. 5** | Autorización obtenida a más tardar al momento de la recolección. |
| **Art. 6** | Para datos sensibles: informar que **no está obligado a autorizar**, decir cuáles datos son sensibles y su finalidad, y **no condicionar ninguna actividad** a entregarlos. |
| **Art. 7** | Modos de obtener la autorización: escrito, oral o conductas inequívocas. Para datos sensibles se usará la forma escrita explícita (casilla). |
| **Art. 8** | Conservar **prueba** de la autorización. |
| **Art. 9** | Revocatoria y supresión en cualquier momento. |
| **Art. 11** | Conservar los datos solo "durante el tiempo que sea razonable y necesario" y documentar los procedimientos de supresión. |
| **Art. 13** | Contenido mínimo de la Política de Tratamiento. |
| **Arts. 14 y 15** | Aviso de privacidad, si la Política no se pone a disposición. |
| **Arts. 24 y 25** | Contrato de transmisión con el Encargado. |
| **Arts. 26 y 27** | Responsabilidad demostrada: medidas proporcionales al riesgo y capacidad de probarlas ante la SIC. |
| **Circular Externa SIC 005 de 2017** | Lista de países con nivel adecuado; incluye a **Estados Unidos**. [verificar vigencia 2026] |
| **Circular Externa SIC 003 de 2018** | Reporte de incidentes en el RNBD dentro de **15 días hábiles** desde que se detectan. [verificar "hábiles"] |
| **Circular Externa SIC 002 de 2024** | Inteligencia artificial: evaluación de impacto, privacidad desde el diseño y test de proporcionalidad. [verificar texto oficial] |
| **Decreto 090 de 2018** | Inscripción en el RNBD. Los estudiantes, como personas naturales, no están obligados. La UMB podría estarlo si asume el proyecto. |
| **Ley 1273 de 2009, art. 269F** | Delito de violación de datos personales: obtener o emplear datos "sin estar facultado". La autorización válida es lo que faculta al proyecto. |
| **Sentencia C-748 de 2011** | Datos "estrictamente necesarios"; conservación no mayor a la finalidad; un dato sensible no deja de serlo por ser visible. |
| **Sentencia T-208 de 2026** | Conservar biometría de forma indefinida no se justifica, ni siquiera para el Estado; la Registraduría "valida identidad", no retiene copias. |
| **SIC Res. 16582/2025 (Mercado Libre), 52185/2025 (conjunto residencial), 45710/2026 (Worldcoin)** | La biometría debe ser la excepción, con alternativa no biométrica. Cifrar o fragmentar un dato biométrico no le quita su carácter personal. |

---

## 3. Roles

| Rol | Quién | Pendiente |
|---|---|---|
| **Responsable del Tratamiento** | Los tres estudiantes autores del trabajo de grado: **Mario Mendoza, Julieth Riveros y Nicolas Marcelo** (también son los tres superadministradores). La UMB **no** es corresponsable. | Nombres completos, dirección y teléfono (ver §15). |
| **Área de atención de peticiones** | El equipo responsable, por el correo `nicololmomo123@gmail.com`. | Se reemplazará por el correo del proyecto cuando exista. |
| **Encargados** | Render (backend y base de datos) y Vercel (frontend). | Revisar sus DPA (ver §10). |
| **Titulares** | Ciudadanos que participen en el piloto, mayores de 18 años. | — |

---

## 4. Inventario de datos (antes y después)

| Dato | Categoría legal | Hoy | Después del cambio | Finalidad |
|---|---|---|---|---|
| Número de documento | Público (número); se trata con la reserva de toda la ficha | Cifrado ECIES + índice ciego HMAC | Igual | Identificar al votante y evitar doble inscripción |
| Nombres, apellidos | Privado | Cifrado | Igual | Identificación y comunicación |
| Fecha de nacimiento | Privado | Cifrado | Igual | Verificar mayoría de edad |
| Correo electrónico | Semiprivado | Cifrado | Igual | Contacto y atención de solicitudes |
| **Imagen completa de la cédula** | **Sensible** (rostro tratado para cotejo; firma; otros datos impresos) | **Guardada cifrada, indefinida, visible para el superadmin** | **No se guarda.** Solo memoria durante la petición. | Leer el número y extraer el rostro |
| Descriptor de la cara impresa (128 valores) | Sensible | Cifrado, indefinido | Cifrado, **máximo 30 min**, se borra al terminar la inscripción | Comparar con el rostro en vivo |
| Evidencia de verificación de la cédula | Privado (no biométrico) | No existe | Nueva: hash SHA-256 de la imagen, número leído coincide (sí/no), puntaje de cotejo, fecha, versión del sistema | Auditoría sin conservar la imagen |
| Plantilla cancelable del rostro | Sensible | Cifrada, indefinida | Cifrada, hasta fin del piloto o revocación | Verificar identidad al votar |
| Habilitación de voto presencial (alternativa) | Privado | No existe | Registro de qué jurado habilitó, cuándo y para qué elección; hasta fin del piloto | Votar sin biometría |
| Prueba de la autorización | Privado | No existe | Nueva tabla, ver §6.4 | Demostrar consentimiento (Decreto 1377 art. 8) |
| Participación (quién votó en qué elección) | Privado | Sin plazo | Hasta cerrar el periodo de reclamaciones; luego se desvincula del votante | Voto único |
| Voto cifrado | No personal (anónimo, sin vínculo con el votante) | Sin plazo | Sin cambio | Escrutinio y verificabilidad |
| Bitácora de auditoría | Privado (referencias a IDs) | Sin plazo | Solo referencias seudónimas, sin nombres ni documentos | Trazabilidad |
| Respaldos | Contienen todo lo anterior | Cada hora, **nunca se borran** | Cada hora, **caducan a los 7 días** | Continuidad |

---

## 5. Cómo se tratará la cédula del votante

### 5.1 Flujo nuevo

```
Navegador                                   Servidor (una sola petición)                  Base de datos
─────────                                   ────────────────────────────                  ─────────────
Foto de la cédula (cámara o archivo)
  ├─ reduce a ≤1600 px, JPEG
  ├─ extrae descriptor de la cara impresa*
  └─ envía imagen + descriptor ──────────▶  1. Valida tipo, tamaño, que sea imagen
                                            2. OCR del número (Tesseract) en memoria
                                            3. Compara con el documento inscrito
                                            4. Calcula SHA-256 de la imagen
                                            5. DESCARTA la imagen (no toca disco ni logs)
                                            6. Guarda descriptor cifrado con expiración ──▶ cotejo_pendiente (expira 30 min)
                                                                                           verificacion_documento (hash, resultado)
Rostro en vivo ─────────────────────────▶  7. Compara rostro vs. descriptor
                                            8. Guarda plantilla cancelable ──────────────▶ biometria
                                            9. BORRA el descriptor de la cédula ─────────▶ (fila eliminada)
```

\* Solo si el titular marcó la casilla de datos biométricos. Si no la marcó, el navegador no extrae el rostro y el servidor solo hace el OCR (ver §7).

### 5.2 Reglas técnicas

1. La imagen nunca se escribe en la base de datos, en disco, en respaldos ni en los logs. Se lee en memoria con `UploadFile.read()` y la variable se libera al terminar la petición.
2. No se registra el cuerpo de las peticiones en ningún log. Hay que revisar que ningún middleware lo haga.
3. Se elimina la tabla `documento_identidad` con su columna `imagen`. Se reemplaza por:
   - `verificacion_documento`: `id_persona`, `hash_imagen`, `numero_coincide`, `puntaje_cotejo`, `resultado`, `fecha`, `version`. No contiene la imagen.
   - `cotejo_pendiente`: `id_persona`, `descriptor` (ECIES) y `expira_en`. El ciclo de supervisión, que ya corre cada 20 s, borra lo vencido.
4. En el panel desaparece **"Ver cédula"**. En su lugar aparece **"Evidencia de verificación"**: fecha, resultado, puntaje y hash. El superadministrador puede comprobar que se verificó una cédula sin verla.
5. **Migración:** un script borra todas las filas de `documento_identidad`. Hay que ejecutarlo también en la base de Render si tiene datos. Como los respaldos caducan a los 7 días, después de ese plazo no queda ninguna imagen en ninguna copia.
6. Texto que verá el ciudadano: "La foto de su cédula se usa solo para leer el número y comparar su rostro; **no se guarda**."

### 5.3 Por qué se elige esta opción y no "guardar con condiciones"

- La imagen completa no aporta nada después del cotejo que no aporten ya el número, la plantilla y la evidencia (Decreto 1377 art. 4).
- La auditoría que justificaba guardarla se cumple con el hash y el resultado.
- Si una imagen no existe, no se puede filtrar ni hay que borrarla en los respaldos. Esto reduce de forma directa el riesgo del art. 23 y del art. 269F.
- Se descartó el "recorte enmascarado": añade complejidad (ubicar zonas en cédula amarilla y digital) y aun así sería un dato que habría que justificar.

---

## 6. Autorización que el ciudadano debe aceptar

### 6.1 Dónde y cómo

- Primer paso de la Registraduría, antes de pedir cualquier dato.
- Se muestra el texto completo con desplazamiento. Debajo:
  - **Casilla A (necesaria para inscribirse):** "Autorizo el tratamiento de mis datos personales en los términos anteriores."
  - **Casilla B (opcional):** "Autorizo, además, el tratamiento de mis **datos biométricos** (imagen de mi rostro en la cédula y en la cámara) para verificar mi identidad. Sé que **no estoy obligado(a)** a autorizarlo y que, si no lo hago, puedo votar de forma presencial en un punto de votación."
- Ambas casillas aparecen **desmarcadas**. No vale "al continuar". El botón "Continuar" solo se activa con la casilla A.
- Enlace a la Política de Tratamiento completa (`/privacidad`).

### 6.2 Texto propuesto

> **Autorización para el tratamiento de datos personales — VotoSeguro (prototipo académico)**
>
> **Responsables:** Mario Mendoza, Julieth Riveros y Nicolas Marcelo, estudiantes de la Universidad Manuela Beltrán (Bogotá D.C.), autores del trabajo de grado "Prototipo de un sistema web de votación electrónica basado en criptografía de curva elíptica y plantilla biométrica". Contacto: nicololmomo123@gmail.com. Dirección: [pendiente]. Teléfono: [pendiente].
>
> **Qué es esto:** VotoSeguro es una **simulación académica**. No pertenece a la Registraduría Nacional del Estado Civil, no está conectada con ella y **no tiene efectos electorales ni jurídicos**.
>
> **Datos que se recogen:** tipo y número de documento, nombres, apellidos, fecha de nacimiento y correo electrónico. Si usted lo autoriza en la casilla B, también: la imagen de su rostro impresa en la cédula y la captura de su rostro con la cámara.
>
> **Datos sensibles:** la imagen de su rostro y la plantilla biométrica que se obtiene de ella son **datos sensibles** (Ley 1581 de 2012, art. 5). **Usted no está obligado(a) a autorizar su tratamiento**, y no hacerlo no le impide participar: podrá votar de forma presencial asistida, en un punto de votación donde un jurado verificará su cédula física.
>
> **Para qué se usan:**
> 1. Inscribirlo(a) como votante del piloto y verificar que es mayor de edad.
> 2. Comprobar que el número de la cédula coincide con el que escribió (lectura automática de la foto).
> 3. Si lo autoriza: comparar su rostro con la foto de la cédula y verificar su identidad cada vez que vote.
> 4. Impedir que una persona vote dos veces o se inscriba con dos documentos.
> 5. Evaluar el funcionamiento del prototipo con **estadísticas anónimas**.
>
> **Qué NO se hace:** la foto de su cédula **no se guarda**: se usa en el momento y se descarta. Su voto **no queda asociado** a su identidad. Sus datos no se venden, no se comparten con terceros ni se usan para otros fines.
>
> **Cómo se protegen:** todos los datos se guardan cifrados con criptografía de curva elíptica. La plantilla de su rostro es cancelable: se puede anular y no permite reconstruir su imagen. Solo los responsables del proyecto acceden al sistema, y cada acceso queda registrado.
>
> **Dónde se alojan:** en servidores de Render (backend y base de datos) y Vercel (sitio web), ubicados en **Estados Unidos**, país que la Superintendencia de Industria y Comercio considera con nivel adecuado de protección. Estas empresas actúan solo como encargadas del almacenamiento.
>
> **Por cuánto tiempo:** los datos de la cara impresa en la cédula se borran apenas termina su inscripción (máximo 30 minutos). Sus datos personales y su plantilla biométrica se borran a más tardar el **30 de diciembre de 2027**, o antes si usted lo pide. Solo se conserva, sin su nombre ni su número de documento legible, una constancia de que aceptó esta autorización, durante 3 años (ver Política de Tratamiento).
>
> **Sus derechos:** conocer, actualizar y rectificar sus datos; pedir prueba de esta autorización; saber cómo se han usado; **revocar** esta autorización y **pedir que se borren** sus datos en cualquier momento; y presentar quejas ante la Superintendencia de Industria y Comercio. Puede ejercerlos en la sección **"Mis datos"** o escribiendo a nicololmomo123@gmail.com. Las consultas se responden en máximo 10 días hábiles y los reclamos en máximo 15.
>
> **Política de Tratamiento:** disponible en la página "Política de privacidad" (/privacidad). Versión 1.0 de esta autorización, vigente desde su publicación en el sistema.

### 6.3 Requisitos legales que cubre cada parte

| Exigencia | Norma | Dónde está en el texto |
|---|---|---|
| Identificación y contacto del Responsable | Ley 1581 art. 12(d) | "Responsable" |
| Tratamiento y finalidad | art. 12(a) | "Para qué se usan" |
| Carácter facultativo de los datos sensibles | art. 12(b); Decreto 1377 art. 6 | "Datos sensibles" y casilla B |
| Cuáles datos son sensibles | Decreto 1377 art. 6 | "Datos sensibles" |
| No condicionar a datos sensibles | Decreto 1377 art. 6 | Alternativa de voto presencial asistido |
| Derechos del titular | art. 12(c); art. 8 | "Sus derechos" |
| Autorización explícita para datos sensibles | art. 6(a) | Casilla B separada y desmarcada |
| Previa a la recolección | Decreto 1377 art. 5 | Primer paso, antes de pedir datos |
| Transmisión internacional | art. 26; Decreto 1377 arts. 24–25 | "Dónde se alojan" |
| Temporalidad | Decreto 1377 art. 11 | "Por cuánto tiempo" |

### 6.4 Prueba de la autorización (Decreto 1377 art. 8)

Nueva tabla `autorizacion`:

| Campo | Contenido |
|---|---|
| `id_persona` | Referencia al titular |
| `version_texto` y `hash_texto` | Versión y SHA-256 del texto exacto mostrado |
| `acepto_datos` / `acepto_biometria` | Booleanos |
| `fecha` | Fecha y hora UTC |
| `revocada_en` / `alcance_revocacion` | Si el titular revoca, cuándo y qué revocó |

- Se conserva aunque se borren los datos biométricos, porque prueba que hubo consentimiento.
- Cuando el titular pide la supresión total, la fila se seudonimiza: se reemplaza `id_persona` por el índice ciego HMAC del documento y se borran los demás datos personales.

---

## 7. Alternativa sin biometría: voto presencial asistido

Exigida por el Decreto 1377 art. 6 ("Ninguna actividad podrá condicionarse a que el Titular suministre datos personales sensibles"). La SIC ordenó mecanismos alternativos "de carácter no invasivo" en los casos de Mercado Libre (Res. 16582/2025) y del conjunto residencial (Res. 52185/2025). En un sistema electoral real, la alternativa natural es votar en un punto de votación con verificación presencial. El prototipo la simula así:

1. **Inscripción sin casilla B:**
   - el navegador no extrae el rostro de la cédula;
   - el servidor solo hace el OCR del número;
   - no se pide la cámara;
   - el votante queda marcado como "verificación presencial".
2. **El día de la votación:** el ciudadano va al punto de votación (simulado) con su cédula física.
3. **Un jurado** (rol Administrador; el Supervisor solo puede consultar) entra al panel, en la nueva sección **"Mesa presencial"**:
   - busca al votante por número de documento;
   - compara en persona la cédula física con quien la presenta (el sistema no captura ninguna imagen);
   - marca "Identidad verificada presencialmente".
4. El sistema abre **una única sesión de voto**:
   - vale para esa elección y dura 10 minutos;
   - se usa en el mismo equipo de la mesa;
   - el ciudadano vota en privado y la sesión se cierra al emitir el voto.
5. **Trazabilidad:** queda registrado qué jurado habilitó la sesión, cuándo y para qué elección. No queda registrado por quién votó; el voto sigue siendo anónimo.
6. **Si el titular revoca la biometría después:** se borra su plantilla y pasa a verificación presencial.
7. **En la tesis:**
   - esta vía depende de la confianza en el jurado, igual que el sistema electoral actual;
   - es la forma de respetar el carácter facultativo de los datos sensibles;
   - además, deja a cada titular la elección entre verificación biométrica remota y verificación presencial.

## 8. Política de retención

### 8.1 Plazos

| Dato | Plazo | Disparador del borrado | Justificación |
|---|---|---|---|
| Imagen de la cédula | **0**: no se almacena | Fin de la petición | Necesidad (art. 4) |
| Descriptor de la cara impresa | **30 minutos** o al terminar la inscripción | Registro del rostro o vencimiento | Solo sirve para el cotejo |
| Plantilla biométrica | Hasta el **fin del piloto** | Fecha `VOTOSEGURO_FIN_PILOTO`, revocación o supresión | Verificación al votar mientras haya votaciones |
| Habilitaciones de voto presencial | Hasta el fin del piloto | Igual | Trazabilidad de la mesa |
| Datos de identificación (persona, votante) | Hasta el fin del piloto | Igual | Inscripción vigente |
| Participación (quién votó) | Hasta **30 días** después del cierre de cada elección | Tarea automática | Periodo de reclamaciones; después se desvincula del votante |
| Votos cifrados y resultados | Indefinido | — | No son datos personales |
| Evidencia de verificación (hash, puntaje) | Igual que los datos de identificación | Igual | Auditoría de la inscripción |
| Prueba de autorización | Hasta **3 años** después de la supresión, seudonimizada (sin nombre ni número legible: solo índice ciego, versión del texto, casillas y fecha) | Tarea automática | Demostrar el consentimiento si hay un reclamo o una investigación de la SIC (plazo de caducidad de la facultad sancionatoria, CPACA art. 52) [verificar] |
| Bitácora de auditoría | Hasta el fin del piloto + 1 año, sin datos identificativos | Archivo y depuración | Trazabilidad; las supresiones se registran como eventos |
| Respaldos | **7 días** | Rotación automática | Un dato suprimido desaparece de todas las copias en un plazo conocido |
| Logs de la aplicación | 30 días (rotación) | Rotación | No contienen datos personales |
| Cuentas de administración | Mientras estén activas | Baja de la cuenta | Operación |

### 8.2 Fin del piloto

- Nueva variable `VOTOSEGURO_FIN_PILOTO`, con valor **2027-12-30**: el proyecto debe concluir antes de terminar 2027. Si la fecha cambia, se ajusta en la configuración sin tocar código.
- Llegada esa fecha, el ciclo automático borra plantillas, habilitaciones presenciales, personas y votantes. Solo quedan resultados agregados y estadísticas anónimas, amparados por el art. 6(e) de la Ley 1581 porque ya no identifican a nadie.
- El panel muestra los días que faltan y un aviso 15 días antes.

### 8.3 Respaldos y borrado efectivo

- El cifrado actual usa **una sola llave del sistema** para todos los registros. Por eso, borrar una fila no la elimina de los respaldos ya hechos.
- Solución principal: los respaldos **caducan a los 7 días** y se borran del disco y de la tabla `respaldo`.
- Mejora opcional (fase 3): una llave por titular, guardada en una tabla aparte y excluida de los respaldos. Al suprimir a un titular se destruye su llave y sus datos quedan ilegibles en cualquier copia. Esto se llama "borrado criptográfico". La SIC no lo ha validado expresamente, así que se documenta como medida adicional, no como sustituto de la caducidad.
- Al restaurar un respaldo hay que **volver a aplicar las supresiones** ocurridas después de su fecha. Se guarda una lista de supresiones con solo el índice ciego HMAC, sin datos personales.

---

## 9. Política de Tratamiento de Datos Personales (borrador)

Se publicará en `/privacidad` y en `docs/politica-tratamiento-datos.md`. Contenido mínimo del Decreto 1377 art. 13:

> **POLÍTICA DE TRATAMIENTO DE DATOS PERSONALES — VotoSeguro**
>
> **1. Responsables.** Mario Mendoza, Julieth Riveros y Nicolas Marcelo, estudiantes de la Universidad Manuela Beltrán, autores del trabajo de grado VotoSeguro, que actúan como Responsables conjuntos del Tratamiento. La Universidad no actúa como Responsable. Domicilio: Bogotá D.C. Correo: nicololmomo123@gmail.com. Dirección: [pendiente]. Teléfono: [pendiente].
>
> **2. Alcance.** Esta política aplica a los datos personales tratados por el prototipo académico VotoSeguro durante su prueba piloto. VotoSeguro es una simulación sin vínculo con la Registraduría Nacional del Estado Civil y sin efectos electorales.
>
> **3. Marco legal.** Constitución Política art. 15; Ley Estatutaria 1581 de 2012; Decreto 1377 de 2013 (Decreto 1074 de 2015); demás normas que los modifiquen o complementen.
>
> **4. Definiciones.** Las del art. 3 de la Ley 1581 y el art. 3 del Decreto 1377: autorización, base de datos, dato personal, dato sensible, Responsable, Encargado, Titular, Tratamiento, transferencia, transmisión.
>
> **5. Datos tratados y finalidades.** [Tabla del §4 de este plan, en lenguaje claro.]
>
> **6. Datos sensibles.** Los datos biométricos solo se tratan con autorización explícita y facultativa. Ninguna actividad del piloto se condiciona a entregarlos: quien no los autorice vota de forma presencial asistida, con verificación de la cédula física por un jurado. La imagen de la cédula no se almacena.
>
> **7. Datos de menores.** El piloto no trata datos de menores de 18 años.
>
> **8. Principios.** Legalidad, finalidad, libertad, veracidad, transparencia, acceso y circulación restringida, seguridad y confidencialidad (Ley 1581 art. 4), además de necesidad y temporalidad (C-748 de 2011).
>
> **9. Derechos del titular.** Los del art. 8 de la Ley 1581, que se pueden ejercer gratis.
>
> **10. Deberes del Responsable.** Los del art. 17 de la Ley 1581.
>
> **11. Atención de peticiones.** Las atiende el equipo responsable por el correo nicololmomo123@gmail.com o en la sección "Mis datos".
> - **Consultas:** se responden en máximo 10 días hábiles, prorrogables 5 avisando el motivo (Ley 1581 art. 14).
> - **Reclamos** (corrección, actualización, supresión, revocatoria, incumplimiento): deben incluir identificación, descripción de los hechos, dirección y documentos. Si el reclamo está incompleto, se pide completarlo en 5 días; si pasan 2 meses sin respuesta del titular, se entiende desistido. Se responden en máximo 15 días hábiles, prorrogables 8 (Ley 1581 art. 15).
> - **Queja ante la SIC:** el titular puede presentarla después de agotar el trámite ante el Responsable (art. 16).
>
> **12. Seguridad.**
> - Cifrado ECIES (curva P-256 con AES-256-GCM).
> - Índice ciego para el número de documento.
> - Plantilla biométrica cancelable.
> - Acceso por roles.
> - Bitácora de auditoría encadenada con SHA-256.
> - Respaldos cifrados y firmados que caducan a los 7 días.
> - Procedimiento de incidentes con reporte a la SIC.
>
> **13. Transmisión internacional.** Los datos se alojan con Render y Vercel en Estados Unidos, país con nivel adecuado según la Circular Externa SIC 005 de 2017. Los Encargados tratan los datos solo por cuenta del Responsable y bajo sus términos de procesamiento de datos.
>
> **14. Conservación.** [Tabla del §8.1.]
>
> **15. Vigencia.** Esta política rige desde la fecha en que se publique en el sistema. Las bases de datos del piloto estarán vigentes hasta el **30 de diciembre de 2027**; después se suprimen según el §14. Los cambios sustanciales se informarán antes de aplicarse y, si cambian las finalidades, se pedirá una nueva autorización.

---

## 10. Transmisión internacional y seguridad

### 10.1 Encargados (Render y Vercel)

- **Decisión:** el piloto se queda en Render y Vercel (plan gratuito). Desplegar Render en una región de **EE. UU. (Oregon, Ohio o Virginia)**, nunca en Singapur (no figura en la lista de la SIC). Hay que comprobar la región actual del servicio y de la base de datos en el panel de Render.
- Leer los DPA de Render y Vercel y hacer una tabla que compruebe las tres cláusulas mínimas del art. 25 del Decreto 1377:
  - tratar los datos por cuenta del Responsable;
  - medidas de seguridad;
  - confidencialidad.
- Guardar la tabla en `docs/`.
- Alternativa más simple: hacer el piloto en un servidor de la universidad o en Colombia (Docker). Así se elimina la transmisión internacional.

### 10.2 Llave maestra

- Hoy está en una variable de entorno del mismo servidor: quien compromete el backend obtiene a la vez los datos cifrados y la llave.
- Mínimo: activar MFA en Render, Vercel y GitHub, limitar quién ve las variables de entorno y documentar cómo se rota la llave.
- Mejora (fase 3): llevar la llave a un servicio de gestión de llaves (KMS) externo.

### 10.3 Incidentes de seguridad

Procedimiento escrito en `docs/procedimiento-incidentes.md`:
1. Detectar el incidente.
2. Contenerlo: rotar llaves y revocar sesiones.
3. Evaluar qué datos se vieron afectados.
4. Reportar en el RNBD de la SIC dentro de **15 días hábiles** (Ley 1581 art. 17-n; Circular 003/2018).
5. Avisar a los titulares afectados (buena práctica).
6. Registrar lo ocurrido en la bitácora.

---

## 11. Derechos del titular en el software

| Derecho | Cómo se ejercerá | Plazo |
|---|---|---|
| Conocer y acceder | "Mis datos": el titular se identifica con documento + rostro y ve qué datos se guardan, sin mostrar la imagen (no existe). Quien no autorizó biometría lo pide por correo o en la mesa presencial. | Inmediato (por correo: 10 días hábiles) |
| Prueba de la autorización | "Mis datos" muestra versión, fecha y casillas aceptadas | Inmediato |
| Actualizar y rectificar | Solicitud por "Mis datos" o por correo; la resuelve un administrador | 15 días hábiles |
| Revocar la biometría | Botón en "Mis datos": borra la plantilla y el votante pasa a verificación presencial | Inmediato |
| Suprimir todo | Botón en "Mis datos" o por correo. Si hay una elección activa en la que ya votó, la participación se conserva hasta el cierre más 30 días. Lo que impide la supresión inmediata es la necesidad de garantizar el voto único, no un deber legal. Se informa al titular. | 15 días hábiles |
| Queja ante la SIC | Información en la Política | — |

En el panel, nueva sección **"Solicitudes de titulares"**: tipo, fecha, días hábiles restantes y estado. Cada respuesta queda en la bitácora.

---

## 12. Otros ajustes

1. **Identidad visual:**
   - rotular la pantalla de inscripción como "Registraduría (simulación)";
   - agregar en el pie: "Prototipo académico sin vínculo con la Registraduría Nacional del Estado Civil";
   - no usar escudos ni logos oficiales (Decreto 1010 de 2000; Código Penal arts. 425–426).
2. **Datos de prueba:** cédulas sintéticas marcadas "ESPÉCIMEN" para desarrollo y demostraciones. Con personas reales, solo durante el piloto aprobado.
3. **Comité de ética de la UMB:** el equipo decidió **no** tramitar el aval. En consecuencia:
   - el piloto con personas reales se limita a participantes voluntarios mayores de edad que acepten la autorización;
   - las demostraciones y la sustentación se hacen con datos y cédulas de prueba ("ESPÉCIMEN");
   - en la tesis se declara como limitación que no hubo revisión de un comité de ética.
4. **Evaluación de impacto (EIPD):** documentarla en `docs/evaluacion-impacto.md` con el test de idoneidad, necesidad y proporcionalidad (Circular SIC 002/2024).
5. **Estadísticas anónimas:** las métricas del piloto (tasa de acierto del OCR, puntajes de cotejo, tiempos) se guardan sin identificadores, al amparo del art. 6(e).

---

## 13. Plan de implementación por fases

### Fase 1 — Obligaciones legales (prioridad alta)

| # | Cambio | Archivos principales |
|---|---|---|
| 1.1 ✅ | Dejar de guardar la imagen; crear las tablas `verificacion_documento` y `cotejo_pendiente`; migración que borra `documento_identidad` | `models.py`, `rutas/registraduria.py`, `servicios/documento.py`, `main.py` (limpieza en el ciclo) |
| 1.2 ✅ | Quitar "Ver cédula" del panel; agregar "Evidencia de verificación" | `rutas/admin.py`, `paginas/admin/Mas.tsx` |
| 1.3 ✅ | Pantalla de autorización con dos casillas, texto versionado y tabla `autorizacion` | `paginas/registraduria/Inscripcion.tsx`, `rutas/registraduria.py`, `models.py`, nuevo `textos/autorizacion_v1.md` |
| 1.4 | Exigir 18 años en la inscripción | `rutas/registraduria.py` |
| 1.5 | Alternativa sin biometría: inscripción sin casilla B y sección "Mesa presencial" donde un jurado habilita una sesión de voto única de 10 minutos | `rutas/registraduria.py`, nueva `rutas/mesa.py`, `rutas/votante.py`, `seguridad.py` (token de sesión presencial), `Inscripcion.tsx`, nueva `paginas/admin/Mesa.tsx`, `models.py` |
| 1.6 ◐ | Política de retención (hecho: borrado de plantillas y cierre de inscripciones en `FIN_PILOTO`; falta: personas, participación, respaldos): `FIN_PILOTO`, borrado automático, caducidad de respaldos (7 días), desvinculación de la participación a los 30 días, lista de supresiones aplicada al restaurar | `config.py`, `main.py`, `servicios/respaldos.py`, nuevo `servicios/retencion.py` |
| 1.7 ✅ | Política de Tratamiento v1.0 publicada en `/privacidad` (texto único en `servicios/politica.py`, servido en `/api/publico/politica`) y generada en `docs/politica-tratamiento-datos.md`. Datos de contacto completos (11-nov-2026) | `servicios/politica.py`, `paginas/votante/Privacidad.tsx` |
| 1.8 ◐ | "Mis datos" (hecho: consultar y revocar la plantilla; falta: supresión total y bandeja de solicitudes) (consultar, revocar biometría, suprimir) y "Solicitudes de titulares" en el panel | nuevas rutas y páginas |
| 1.9 | Procedimiento de incidentes y tabla de correspondencia con los DPA | `docs/` |

### Fase 2 — Buenas prácticas

| # | Cambio |
|---|---|
| 2.1 | Bitácora solo con referencias seudónimas; registrar las supresiones como eventos |
| 2.2 | Leyendas de simulación y retiro de cualquier referencia visual oficial |
| 2.3 | Evaluación de impacto documentada |
| 2.4 | Estadísticas anónimas del piloto |
| 2.5 | MFA y control de acceso a las variables de entorno en Render, Vercel y GitHub |

### Fase 3 — Mejoras opcionales

| # | Cambio |
|---|---|
| 3.1 | Llave por titular, para borrado criptográfico en los respaldos |
| 3.2 | Llave maestra en un KMS externo |
| 3.3 | Despliegue en Colombia, sin transmisión internacional |

### Pruebas que se agregarán

- La imagen de la cédula no aparece en ninguna tabla ni respaldo después de la inscripción.
- El descriptor pendiente se borra al registrar el rostro y al vencer los 30 minutos.
- No se puede inscribir sin la casilla A; sin la casilla B se inscribe sin biometría y solo puede votar por la mesa presencial.
- La sesión presencial vale para una sola elección, vence a los 10 minutos y se cierra al votar; un Supervisor no puede habilitarla.
- Un menor de 18 años es rechazado.
- La prueba de autorización guarda la versión y el hash del texto.
- Revocar la biometría borra la plantilla y deja al votante en verificación presencial.
- La supresión borra los datos y conserva la participación solo mientras la elección siga activa.
- Al llegar `FIN_PILOTO` se borran las personas y las plantillas y se conservan los resultados.
- Los respaldos de más de 7 días se eliminan.
- Restaurar un respaldo vuelve a aplicar las supresiones posteriores.
- "Evidencia de verificación" no expone la imagen ni datos biométricos.

---

### Cambio adicional — inscripción atómica ✅

Mientras la inscripción está en curso no se guarda nada en la base de datos: los datos de cada paso viajan sellados
(ECIES) en el token del navegador y se confirman en una sola transacción al terminar. Si el ciudadano abandona, se
agotan los 5 intentos del cotejo facial o pasan 30 minutos (`VOTOSEGURO_MINUTOS_INSCRIPCION`), la inscripción se
descarta sin dejar datos. Desaparece la tabla `cotejo_pendiente`. Fundamento: Decreto 1377 arts. 4 y 11 (no
conservar datos que no cumplen una finalidad) y Ley 1581 art. 4 lit. g (seguridad).

### Cambio adicional — transparencia del sitio y encabezados de seguridad ✅

- Portada: enlace a la Política de privacidad y aviso "Simulación académica · No pertenece a la Registraduría Nacional del Estado Civil ni tiene efectos electorales" (antes decía "Registrado por la Registraduría Nacional del Estado Civil").
- Se quitaron otras menciones que podían hacer creer que el sistema es oficial: el encabezado de la inscripción, el pie de la pantalla final del voto, la línea telefónica real de la Registraduría en la pantalla de no habilitado y el "REPORTE OFICIAL" del PDF.
- Encabezados de seguridad en FastAPI y Vercel: Content-Security-Policy, HSTS, Cross-Origin-Opener-Policy (además de los que ya había). Comprobado que face-api (WebGL) funciona con la política.
- `/docs`, `/redoc` y `/openapi.json` apagados por defecto (`VOTOSEGURO_DOCUMENTACION_API=true` para desarrollo).
- Correos de administración: de `@votoseguro.gov.co` (dominio de uso exclusivo del Estado) a `@votoseguro.local` (12-nov-2026), en el código, las pruebas y la base local.
- Ajustes finales: el OCR usa archivos temporales en `/dev/shm` (RAM, nunca en disco); la Política aclara que la bitácora sí guarda el correo del administrador; el código del comprobante se verifica con `POST /api/publico/verificar` (ya no va en la dirección, que queda en los registros de acceso).

### Cambio adicional — prueba de vida comprobada por el servidor ✅

- Antes: el navegador pedía 2 retos al azar (girar a la izquierda, a la derecha o sonreír), pero el servidor aceptaba cualquier descriptor. Bastaba con enviar un descriptor calculado de una foto, sin pasar por la cámara.
- Ahora: el servidor elige **3 retos de 4** (izquierda, derecha, sonreír y el nuevo **abrir la boca**) y los pone en el token. El navegador envía los 68 puntos faciales de frente y de cada reto, y `servicios/vida.py` recalcula las medidas y comprueba cada reto en orden. Una foto inclinada no cambia sus proporciones, así que no pasa.
- Los fallos de la prueba cuentan para la pausa por documento (al votar) y para los intentos de la inscripción.
- Límite: los puntos los calcula el navegador; alguien con conocimientos técnicos podría fabricarlos. Impedirlo del todo exigiría analizar el video en el servidor.

### Cambio adicional — no revelar quién participa y límites de intentos ✅

- Las **dos casillas** de la autorización son necesarias (decisión de los responsables, 12-nov-2026). Siguen separadas porque la de datos sensibles debe ser expresa. El piloto evalúa la verificación con el rostro; quien no la autorice simplemente no participa. Ver el riesgo en la Política §7 y en el informe de la sesión. Con esto desaparece la necesidad del voto presencial (ítem 1.5).
- `/api/votante/identificacion` responde igual esté o no inscrito el documento: el token lleva el documento sellado (ECIES, longitud fija). La verificación del rostro da la misma respuesta para no inscrito, sin rostro, bloqueado o rostro distinto, y usa una plantilla señuelo para que el tiempo de respuesta no delate nada.
- El "ya está inscrito" de la Registraduría se dice en el paso de la cédula, no en el primero.
- Tras 5 rostros fallidos con un documento (exista o no), ese documento se **pausa 30 minutos**, en vez de bloquearse para siempre: nadie puede bloquear la cuenta de otra persona.
- Límites por IP en identificación, inscripción, inicio de sesión del panel y verificación de comprobantes. Los contadores están en la tabla `limite` (claves HMAC, sin IP ni documento), sobreviven a reinicios y se purgan al vencer. Los intentos del cotejo en la inscripción también pasaron a esa tabla.
- En Render, `VOTOSEGURO_CONFIAR_X_FORWARDED_FOR=true` para usar la IP real del ciudadano.

### Cambio adicional — plazos de conservación y supresión ✅

- `servicios/retencion.aplicar` (en cada ciclo) cumple los plazos de la Política:
  - respaldos y archivos huérfanos se borran a los 7 días;
  - la participación se desvincula 30 días después del cierre (el conteo se conserva);
  - las pruebas de autorización seudonimizadas se borran a los 3 años;
  - al terminar el piloto se suprime a todos los titulares, y un año después se depura la bitácora.
- Supresión a solicitud del titular: botón **Borrar datos** en Votantes (solo Superadministrador, `DELETE /api/admin/votantes/{id}`). Se aplaza, con la fecha, si votó en una elección abierta o cerrada hace menos de 30 días.
- La tabla `supresion` (solo índice ciego y fecha, fuera de los respaldos) permite volver a borrar a esos titulares si se restaura un respaldo anterior.
- Los plazos se configuran en `config.py` (`dias_respaldo`, `dias_reclamacion`, `anios_prueba_autorizacion`, `dias_bitacora_post_piloto`).

### Cambio adicional — anonimato del voto ✅

- Antes: la participación (con hora exacta) y el voto se guardaban juntos y en el mismo orden, así que quien tuviera acceso a la base podía relacionarlos.
- Ahora: los votos de una elección abierta van a una **urna** (una sola fila por elección, barajada en cada voto). Al cerrar, pasan a `voto` en orden aleatorio y todos con la hora del cierre. La participación guarda solo el día. El comprobante se puede verificar también mientras el voto está en la urna.
- Al arrancar, `migrar_anonimato` convierte los votos guardados con el formato anterior.
- Límite declarado en la Política (§7): quien administre el servidor podría vigilarlo en tiempo real o comparar respaldos hechos durante la votación. Los Responsables se comprometen a no hacerlo, y los respaldos caducan a los 7 días (pendiente de implementar).

## 14. Skills y herramientas útiles para ejecutar el plan

| Herramienta | Para qué | Estado |
|---|---|---|
| **privacy-legal** (Anthropic): `pia-generation`, `reg-gap-analysis`, `policy-monitor`, `dpa-review` | Evaluación de impacto (§12.4), revisión de brechas frente al plan, comprobar que la Política coincide con lo que hace el código, revisar los DPA de Render y Vercel | Disponible para instalar (tarjeta enviada) |
| **Legal** (Anthropic): `compliance-check`, `legal-risk-assessment` | Revisión final de la autorización y la Política | Disponible para instalar |
| **Security Guidance** / **securitymaxxing** | Revisar el código nuevo en busca de vulnerabilidades y secretos expuestos (`/crypto`, `/secrets`, `/threat-model`) | Disponible para instalar |
| `/security-review` y `/code-review` | Revisión de los cambios antes de desplegar | Ya disponibles |
| `engineering:testing-strategy` | Diseñar las pruebas del §13 | Ya disponible |
| `engineering:documentation` | Redactar los documentos de `docs/` | Ya disponible |
| `anthropic-skills:pdf` / `docx` | Exportar la Política y la autorización para anexarlas a la tesis | Ya disponibles |

Nota: los plugins de protección de datos del directorio están orientados al RGPD europeo. Sirven como guía de estructura (EIPD, registro de actividades), pero los requisitos de este plan siguen la ley colombiana.

---

## 15. Decisiones tomadas

| # | Tema | Decisión | Efecto en el plan |
|---|---|---|---|
| 1 | Responsable | Los tres estudiantes autores: Mario Mendoza, Julieth Riveros y Nicolas Marcelo, como Responsables conjuntos. La UMB no es corresponsable. | §3, §6.2, §9 |
| 2 | Correo de atención | `nicololmomo123@gmail.com` hasta que exista el correo del proyecto | §3, §6.2, §9 |
| 3 | Fin del piloto | Hasta el 30 de diciembre de 2027 → `VOTOSEGURO_FIN_PILOTO=2027-12-30` | §6.2, §8.2, §9 |
| 4 | Prueba de autorización | 3 años después de la supresión, seudonimizada y sin nombre ni número legible | §6.4, §8.1 |
| 5 | Alojamiento | Render y Vercel (gratis), región de EE. UU. | §10.1 |
| 6 | Alternativa sin biometría | Voto presencial asistido en un punto de votación, simulado como "Mesa presencial" en el panel | §7, §11, §13 |
| 7 | Comité de ética | No se tramita; demostraciones con datos de prueba y limitación declarada en la tesis | §12 |

### Datos que aún faltan (no bloquean la implementación)

- **Nombres completos**, **dirección** y **teléfono** de los responsables. La Ley 1581 (art. 12-d) exige informar dirección y teléfono del Responsable. Mientras no estén, el texto muestra "[pendiente]", y deben completarse antes de inscribir personas reales.
- **Correo definitivo del proyecto**, para reemplazar `nicololmomo123@gmail.com`.
