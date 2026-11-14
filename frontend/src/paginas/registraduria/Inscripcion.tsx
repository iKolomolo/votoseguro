// Registraduría (simulada): inscripción del ciudadano, separada del flujo de votación.
// Autorización -> datos personales -> foto de la cédula (número por OCR y, con autorización biométrica, cara
// impresa) -> rostro comparado con la cédula. Sin autorización biométrica la inscripción termina en la cédula.
import { AlertCircle, CheckCircle2, CircleCheck, ExternalLink, IdCard, ShieldCheck, UserPlus, Vote } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { api, ErrorApi, fechaDia } from "../../api";
import { CapturaDocumento, type FotoCedula } from "../../biometria/CapturaDocumento";
import { retosDelToken, useCapturaFacial, VistaCamara } from "../../biometria/CapturaFacial";
import { Alerta, BigButton, Campo, Cargando, ConNegrilla, GovHeader, LockBadge, Pantalla, ProgressSteps } from "../../componentes/ui";
import { TIPOS } from "../votante/Identificacion";

type Etapa = "autorizacion" | "datos" | "cedula" | "rostro" | "listo";
const NUMERO: Record<Etapa, number> = { autorizacion: 1, datos: 2, cedula: 3, rostro: 4, listo: 5 };

interface Inscrito { nombre: string; habilitado: boolean; plantilla_hasta?: string }

/** Lo que se envía con los datos: versión y huella del texto leído y las dos casillas. */
interface Aceptada { version: string; hash: string; acepto_datos: boolean; acepto_biometria: boolean }

interface TextoAutorizacion {
  version: string; hash: string; titulo: string; subtitulo: string;
  secciones: { titulo: string; texto?: string; lista?: string[] }[];
  casillas: { datos: string; biometria: string };
}

/** Respuestas que significan que la inscripción en curso se descartó: venció, se canceló o no es válida. */
const descartada = (e: unknown) => e instanceof ErrorApi && [400, 401, 423].includes(e.estado);
const motivoDescarte = (e: unknown) => e instanceof ErrorApi && e.estado === 401
  ? "Pasaron más de 30 minutos y la inscripción se descartó sin guardar ningún dato. Empiece de nuevo."
  : mensaje(e, "La inscripción se descartó sin guardar ningún dato. Empiece de nuevo.");

const mensaje = (e: unknown, otro: string) => (e instanceof ErrorApi || e instanceof Error ? e.message : otro);

export function Inscripcion() {
  const navegar = useNavigate();
  const [etapa, setEtapa] = useState<Etapa>("autorizacion");
  const [aceptada, setAceptada] = useState<Aceptada>();
  const [token, setToken] = useState<string>();
  const [resultado, setResultado] = useState<Inscrito>();
  // Motivo por el que la inscripción se descartó y volvió al inicio (venció el plazo o se agotaron los intentos).
  const [aviso, setAviso] = useState<string>();

  function reiniciar(motivo?: string) {
    setToken(undefined);
    setResultado(undefined);
    setAviso(motivo);
    setAceptada(undefined);
    setEtapa("autorizacion");
  }

  const conBiometria = aceptada?.acepto_biometria ?? true;
  const pasos = conBiometria ? ["Autorización", "Datos", "Cédula", "Rostro"] : ["Autorización", "Datos", "Cédula"];

  return (
    <Pantalla estrecha>
      <GovHeader antetitulo="Registraduría simulada · VotoSeguro" titulo="Inscripción de Ciudadanos"
        subtitulo={etapa === "listo" ? "Inscripción completa" : `Paso ${NUMERO[etapa]} de ${pasos.length}`}
        color="bg-primary-dark" onVolver={() => navegar("/")} />
      <ProgressSteps paso={etapa === "listo" ? pasos.length + 1 : NUMERO[etapa]} pasos={pasos} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        {etapa === "autorizacion" && aviso && (
          <Alerta tipo="aviso" titulo="La inscripción no se guardó" icono={<AlertCircle className="size-5" />}>{aviso}</Alerta>
        )}
        {etapa === "autorizacion" && <PasoAutorizacion onListo={(a) => { setAceptada(a); setAviso(undefined); setEtapa("datos"); }} />}
        {etapa === "datos" && aceptada && (
          <PasoDatos aceptada={aceptada} onListo={(t) => { setToken(t); setEtapa("cedula"); }} />
        )}
        {etapa === "cedula" && token && (
          <PasoCedula token={token} conRostro={conBiometria} onDescartada={reiniciar}
            onListo={(t) => { setToken(t); setEtapa("rostro"); }}
            onCompleta={(r) => { setResultado(r); setEtapa("listo"); }} />
        )}
        {etapa === "rostro" && token && (
          <PasoRostro token={token} onListo={(r) => { setResultado(r); setEtapa("listo"); }}
            onDescartada={reiniciar} />
        )}
        {etapa === "listo" && resultado && (
          <section className="tarjeta flex flex-col items-center gap-4 p-6 text-center md:p-10">
            <div className="flex size-20 items-center justify-center rounded-full bg-exito-bg">
              <CircleCheck className="size-12 fill-exito text-white" />
            </div>
            <h2 className="text-2xl font-bold">¡Inscripción completa, {resultado.nombre}!</h2>
            {resultado.plantilla_hasta ? (
              <>
                <p className="text-tinta-2">
                  Sus datos y su plantilla biométrica quedaron registrados de forma cifrada; la foto de la cédula no se
                  guardó. Para votar solo necesitará su número de documento y su rostro.
                </p>
                <p className="text-sm text-tinta-2">
                  Su plantilla biométrica se borrará automáticamente el <b>{fechaDia(resultado.plantilla_hasta)}</b>, al
                  terminar el piloto. Puede revocarla antes en <b>Mis datos personales</b>, desde la pantalla de inicio.
                </p>
              </>
            ) : (
              <>
                <p className="text-tinta-2">
                  Sus datos quedaron registrados de forma cifrada y su cédula fue verificada por su número; la foto no se
                  guardó. Como no autorizó sus datos biométricos, no se tomó ninguna medida de su rostro.
                </p>
                <Alerta tipo="info" titulo="Votará de forma presencial">
                  El día de la votación acérquese a un punto de votación con su cédula física: un jurado verificará su
                  identidad. (La votación presencial asistida está en desarrollo en este prototipo.)
                </Alerta>
              </>
            )}
            {!resultado.habilitado && (
              <Alerta tipo="aviso" titulo="Aún no está habilitado para votar">Debe ser mayor de 18 años.</Alerta>
            )}
            <div className="flex w-full flex-col gap-3 pt-2 md:flex-row-reverse">
              {resultado.plantilla_hasta && (
                <BigButton onClick={() => navegar("/identificacion")}><Vote className="size-5" /> Ir a votar</BigButton>
              )}
              <BigButton variante="contorno" onClick={() => reiniciar()}><UserPlus className="size-5" /> Nueva inscripción</BigButton>
            </div>
          </section>
        )}
      </main>
    </Pantalla>
  );
}

function PasoAutorizacion({ onListo }: { onListo: (aceptada: Aceptada) => void }) {
  const [texto, setTexto] = useState<TextoAutorizacion>();
  const [error, setError] = useState<string>();
  const [datos, setDatos] = useState(false);
  const [biometria, setBiometria] = useState(false);

  useEffect(() => {
    api<TextoAutorizacion>("/api/publico/autorizacion").then(setTexto)
      .catch((e) => setError(mensaje(e, "No fue posible cargar el texto de la autorización")));
  }, []);

  if (error) return <Alerta tipo="error" titulo="No se pudo cargar" icono={<AlertCircle className="size-5" />}>{error}</Alerta>;
  if (!texto) return <Cargando texto="Cargando la autorización…" />;

  const casilla = "mt-0.5 size-5 shrink-0 accent-primary";
  return (
    <>
      <LockBadge />
      <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-info-bg text-primary">
            <ShieldCheck className="size-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold">{texto.titulo}</h2>
            <p className="text-sm text-tinta-2">{texto.subtitulo} · Versión {texto.version}</p>
          </div>
        </div>
        <div tabIndex={0} aria-label="Texto de la autorización"
          className="flex max-h-[46dvh] flex-col gap-3 overflow-y-auto rounded-xl border-[1.5px] border-linea bg-sutil-2 p-4 text-sm leading-relaxed">
          {texto.secciones.map((s) => (
            <div key={s.titulo}>
              <h3 className="font-bold">{s.titulo}</h3>
              {s.texto && <p className="text-tinta-2"><ConNegrilla texto={s.texto} /></p>}
              {s.lista && (
                <ol className="list-decimal pl-5 text-tinta-2">
                  {s.lista.map((l) => <li key={l}><ConNegrilla texto={l} /></li>)}
                </ol>
              )}
            </div>
          ))}
          <a href="/privacidad" target="_blank" rel="noopener noreferrer"
            className="flex w-fit items-center gap-1 font-semibold text-primary underline">
            Política de privacidad <ExternalLink className="size-3.5" />
          </a>
        </div>
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border-[1.5px] border-linea p-3 text-sm">
          <input type="checkbox" className={casilla} checked={datos} onChange={(e) => setDatos(e.target.checked)} />
          <span><ConNegrilla texto={texto.casillas.datos} /> <span className="text-xs text-tinta-2">(necesaria para inscribirse)</span></span>
        </label>
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border-[1.5px] border-linea p-3 text-sm">
          <input type="checkbox" className={casilla} checked={biometria} onChange={(e) => setBiometria(e.target.checked)} />
          <span><ConNegrilla texto={texto.casillas.biometria} /> <span className="text-xs text-tinta-2">(necesaria para participar)</span></span>
        </label>
      </section>
      <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton variante="primario" disabled={!datos || !biometria}
          onClick={() => onListo({ version: texto.version, hash: texto.hash, acepto_datos: datos, acepto_biometria: biometria })}>
          {datos && biometria ? "Continuar →" : "Marque las dos autorizaciones para participar"}
        </BigButton>
      </div>
    </>
  );
}

const EDAD_MINIMA = 18;

/** Última fecha de nacimiento con la que hoy ya se tienen 18 años cumplidos (AAAA-MM-DD, hora local). */
function fechaMayoriaEdad(): string {
  const hoy = new Date();
  const limite = new Date(hoy.getFullYear() - EDAD_MINIMA, hoy.getMonth(), hoy.getDate());
  if (limite.getMonth() !== hoy.getMonth()) limite.setDate(0); // 29 de febrero en un año no bisiesto
  const dos = (n: number) => String(n).padStart(2, "0");
  return `${limite.getFullYear()}-${dos(limite.getMonth() + 1)}-${dos(limite.getDate())}`;
}

function PasoDatos({ aceptada, onListo }: { aceptada: Aceptada; onListo: (token: string) => void }) {
  const [datos, setDatos] = useState({
    tipo_documento: "CC", documento: "", nombres: "", apellidos: "", fecha_nacimiento: "", correo: "",
  });
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);
  const cambiar = (campo: keyof typeof datos) => (e: { target: { value: string } }) =>
    setDatos((d) => ({ ...d, [campo]: e.target.value }));

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    if (datos.fecha_nacimiento > fechaMayoriaEdad()) {
      setError(`Debe tener al menos ${EDAD_MINIMA} años cumplidos para inscribirse como votante.`);
      return;
    }
    setEnviando(true);
    try {
      const r = await api<{ token: string }>("/api/registraduria/inscripcion", { cuerpo: { ...datos, autorizacion: aceptada } });
      onListo(r.token);
    } catch (err) {
      setError(mensaje(err, "No fue posible registrar los datos"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <LockBadge />
      <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
        <h2 className="text-lg font-bold">Datos del ciudadano</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Campo etiqueta="Tipo de Documento" id="tipo">
            <select id="tipo" className="entrada" value={datos.tipo_documento} onChange={cambiar("tipo_documento")}>
              {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Número de Documento" id="documento">
            <input id="documento" className="entrada" inputMode="numeric" required autoComplete="off"
              pattern="[0-9A-Za-z]{5,15}" title="Entre 5 y 15 caracteres, sin puntos ni espacios"
              placeholder="Ej: 1020304050" value={datos.documento} onChange={cambiar("documento")} />
          </Campo>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta="Nombres" id="nombres">
            <input id="nombres" className="entrada" required minLength={2} autoComplete="given-name"
              placeholder="Ej: María" value={datos.nombres} onChange={cambiar("nombres")} />
          </Campo>
          <Campo etiqueta="Apellidos" id="apellidos">
            <input id="apellidos" className="entrada" required minLength={2} autoComplete="family-name"
              placeholder="Ej: Torres" value={datos.apellidos} onChange={cambiar("apellidos")} />
          </Campo>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Campo etiqueta="Fecha de Nacimiento" id="nacimiento">
            <input id="nacimiento" type="date" className="entrada" required max={new Date().toISOString().slice(0, 10)}
              value={datos.fecha_nacimiento} onChange={cambiar("fecha_nacimiento")} />
            <span className="text-xs text-tinta-2">Debe tener {EDAD_MINIMA} años cumplidos.</span>
          </Campo>
          <Campo etiqueta="Correo electrónico" id="correo">
            <input id="correo" type="email" className="entrada" required autoComplete="email"
              placeholder="Ej: maria@correo.co" value={datos.correo} onChange={cambiar("correo")} />
          </Campo>
        </div>
        <p className="text-xs text-tinta-2">
          Aceptó la autorización de tratamiento de datos (versión {aceptada.version})
          {aceptada.acepto_biometria ? ", incluidos sus datos biométricos." : ", sin datos biométricos: votará de forma presencial."}
          {" "}Nada se guarda hasta que termine la inscripción: tiene 30 minutos; si no la completa, se descarta.
        </p>
      </section>
      {error && <Alerta tipo="error" titulo="No se pudo continuar" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pt-2 pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton type="submit" variante="primario" cargando={enviando}>Continuar →</BigButton>
      </div>
    </form>
  );
}

function PasoCedula({ token, conRostro, onListo, onCompleta, onDescartada }: {
  token: string; conRostro: boolean; onListo: (token: string) => void; onCompleta: (r: Inscrito) => void;
  onDescartada: (motivo: string) => void;
}) {
  const [frente, setFrente] = useState<FotoCedula | null>(null);
  const [reverso, setReverso] = useState<FotoCedula | null>(null);
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function enviar() {
    if (!frente || !reverso) return;
    setError(undefined);
    setEnviando(true);
    try {
      const formulario = new FormData();
      formulario.append("imagen", frente.blob, "frente.jpg");
      formulario.append("reverso", reverso.blob, "reverso.jpg");
      // Sin autorización biométrica no se envía ningún dato del rostro.
      if (frente.descriptor) formulario.append("descriptor", JSON.stringify(frente.descriptor));
      const r = await api<{ completa: boolean; token?: string } & Inscrito>("/api/registraduria/cedula", { token, formulario });
      if (r.completa) onCompleta(r);
      else if (r.token) onListo(r.token);
    } catch (err) {
      if (descartada(err)) {
        onDescartada(motivoDescarte(err));
        return;
      }
      setError(mensaje(err, "No fue posible validar la cédula"));
    } finally {
      setEnviando(false);
    }
  }

  const cara = (titulo: string, ayuda: string, contenido: ReactNode) => (
    <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-info-bg text-primary">
          <IdCard className="size-5" />
        </span>
        <div>
          <h2 className="text-lg font-bold">{titulo}</h2>
          <p className="text-sm text-tinta-2">{ayuda}</p>
        </div>
      </div>
      {contenido}
    </section>
  );

  return (
    <>
      <Alerta tipo="info" titulo="Escriba sus datos tal como aparecen en su cédula">
        Se leerán el número, los nombres, los apellidos y la fecha de nacimiento de las dos caras y deben coincidir
        con lo que escribió. Sirve la cédula amarilla o la digital.
      </Alerta>
      {cara("1. Cara frontal", "De frente, con buena luz y sin reflejos. Deben verse la foto, el número, los nombres y los apellidos.",
        <CapturaDocumento conRostro={conRostro} onCambio={(f) => { setFrente(f); setError(undefined); }} />)}
      {/* El reverso aparece después del frente: así nunca hay dos cámaras abiertas a la vez. */}
      {frente && cara("2. Reverso", "La cara de atrás completa. En la cédula digital debe verse la zona de abajo con los símbolos <<<.",
        <CapturaDocumento conRostro={false} onCambio={(f) => { setReverso(f); setError(undefined); }} />)}
      <p className="text-xs text-tinta-2">
        Las fotos se usan solo para leer esos datos{conRostro ? " y comparar el rostro" : ""}: <b>no se guardan</b>. No se
        analiza la huella dactilar ni los demás datos del reverso.
        {conRostro ? " El dato del rostro impreso viaja cifrado hasta el siguiente paso y tampoco se guarda."
          : " Como no autorizó sus datos biométricos, no se analiza el rostro impreso."}
      </p>
      {error && <Alerta tipo="error" titulo="No se pudo validar la cédula" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton variante="primario" onClick={enviar} cargando={enviando} disabled={!frente || !reverso}>
          {enviando ? "Leyendo la cédula, puede tardar hasta 2 minutos…" : !frente ? "Tome o suba la foto del frente" : !reverso ? "Tome o suba la foto del reverso"
            : conRostro ? "Continuar al registro del rostro →" : "Terminar inscripción →"}
        </BigButton>
      </div>
    </>
  );
}

function PasoRostro({ token, onListo, onDescartada }: {
  token: string; onListo: (r: Inscrito) => void; onDescartada: (motivo: string) => void;
}) {
  const camara = useCapturaFacial();
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function iniciar() {
    setError(undefined);
    try {
      const { descriptor, vida } = await camara.capturar(retosDelToken(token));
      setEnviando(true);
      const r = await api<Inscrito>("/api/registraduria/rostro",
        { token, cuerpo: { descriptor, vida } });
      camara.detener();
      onListo(r);
    } catch (err) {
      if (descartada(err)) {
        // Venció el plazo o se agotaron los intentos: no se guardó nada y hay que empezar de nuevo.
        camara.detener();
        onDescartada(motivoDescarte(err));
        return;
      }
      setError(mensaje(err, "No fue posible registrar el rostro"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <section className="tarjeta flex flex-col items-center gap-5 p-6 lg:flex-row lg:justify-center lg:gap-12 lg:p-10">
        <VistaCamara video={camara.video} estado={camara.estado} rostroVisible={camara.rostroVisible} />
        <div className="flex flex-col items-center gap-5 lg:max-w-sm lg:items-start">
          <p aria-live="polite" className="max-w-[320px] text-center text-2xl font-bold leading-snug text-tinta lg:max-w-none lg:text-left lg:text-3xl">
            {camara.instruccion}
          </p>
          <p className="flex items-start gap-2 text-center text-base font-medium text-tinta-2 lg:text-left">
            <CheckCircle2 className="mt-1 hidden size-4 shrink-0 text-exito lg:block" />
            El rostro se comparará con la foto de la cédula. Se guarda una plantilla biométrica cancelable y cifrada,
            no una fotografía, hasta el fin del piloto o hasta que usted la revoque.
          </p>
        </div>
      </section>
      {error && <Alerta tipo="error" titulo="No se registró el rostro" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton variante="primario" onClick={iniciar} cargando={camara.estado === "capturando" || enviando}
          disabled={camara.estado !== "listo"}>
          {camara.estado === "capturando" ? "Analizando rostro…" : enviando ? "Registrando…" : "Registrar rostro"}
        </BigButton>
      </div>
    </>
  );
}
