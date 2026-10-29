// Registraduría (simulada): inscripción del ciudadano, separada del flujo de votación.
// Datos personales -> foto de la cédula (número por OCR y cara impresa) -> rostro comparado con la cédula.
import { AlertCircle, CheckCircle2, CircleCheck, IdCard, UserPlus, Vote } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ErrorApi } from "../../api";
import { CapturaDocumento, type FotoCedula } from "../../biometria/CapturaDocumento";
import { useCapturaFacial, VistaCamara } from "../../biometria/CapturaFacial";
import { Alerta, BigButton, Campo, GovHeader, LockBadge, Pantalla, ProgressSteps } from "../../componentes/ui";
import { TIPOS } from "../votante/Identificacion";

const PASOS = ["Datos", "Cédula", "Rostro"];
type Etapa = "datos" | "cedula" | "rostro" | "listo";
const NUMERO: Record<Etapa, number> = { datos: 1, cedula: 2, rostro: 3, listo: 4 };

const mensaje = (e: unknown, otro: string) => (e instanceof ErrorApi || e instanceof Error ? e.message : otro);

export function Inscripcion() {
  const navegar = useNavigate();
  const [etapa, setEtapa] = useState<Etapa>("datos");
  const [token, setToken] = useState<string>();
  const [resultado, setResultado] = useState<{ nombre: string; habilitado: boolean }>();

  function reiniciar() {
    setToken(undefined);
    setResultado(undefined);
    setEtapa("datos");
  }

  return (
    <Pantalla estrecha>
      <GovHeader antetitulo="Registraduría Nacional del Estado Civil" titulo="Inscripción de Ciudadanos"
        subtitulo={etapa === "listo" ? "Inscripción completa" : `Paso ${NUMERO[etapa]} de 3`}
        color="bg-primary-dark" onVolver={() => navegar("/")} />
      <ProgressSteps paso={NUMERO[etapa]} pasos={PASOS} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        {etapa === "datos" && <PasoDatos onListo={(t) => { setToken(t); setEtapa("cedula"); }} />}
        {etapa === "cedula" && token && <PasoCedula token={token} onListo={(t) => { setToken(t); setEtapa("rostro"); }} />}
        {etapa === "rostro" && token && <PasoRostro token={token} onListo={(r) => { setResultado(r); setEtapa("listo"); }} />}
        {etapa === "listo" && resultado && (
          <section className="tarjeta flex flex-col items-center gap-4 p-6 text-center md:p-10">
            <div className="flex size-20 items-center justify-center rounded-full bg-exito-bg">
              <CircleCheck className="size-12 fill-exito text-white" />
            </div>
            <h2 className="text-2xl font-bold">¡Inscripción completa, {resultado.nombre}!</h2>
            <p className="text-tinta-2">
              Sus datos, su cédula y su rostro quedaron registrados de forma cifrada. Para votar solo necesitará su
              número de documento y su rostro.
            </p>
            {!resultado.habilitado && (
              <Alerta tipo="aviso" titulo="Aún no está habilitado para votar">Debe ser mayor de 18 años.</Alerta>
            )}
            <div className="flex w-full flex-col gap-3 pt-2 md:flex-row-reverse">
              <BigButton onClick={() => navegar("/identificacion")}><Vote className="size-5" /> Ir a votar</BigButton>
              <BigButton variante="contorno" onClick={reiniciar}><UserPlus className="size-5" /> Nueva inscripción</BigButton>
            </div>
          </section>
        )}
      </main>
    </Pantalla>
  );
}

function PasoDatos({ onListo }: { onListo: (token: string) => void }) {
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
    setEnviando(true);
    try {
      const r = await api<{ token: string }>("/api/registraduria/inscripcion", { cuerpo: datos });
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
          </Campo>
          <Campo etiqueta="Correo electrónico" id="correo">
            <input id="correo" type="email" className="entrada" required autoComplete="email"
              placeholder="Ej: maria@correo.co" value={datos.correo} onChange={cambiar("correo")} />
          </Campo>
        </div>
        <p className="text-xs text-tinta-2">
          Al continuar autoriza el tratamiento de sus datos personales y biométricos únicamente con fines académicos de
          esta prueba piloto (Ley 1581 de 2012). Sus datos se guardan cifrados.
        </p>
      </section>
      {error && <Alerta tipo="error" titulo="No se pudo continuar" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pt-2 pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton type="submit" variante="primario" cargando={enviando}>Continuar →</BigButton>
      </div>
    </form>
  );
}

function PasoCedula({ token, onListo }: { token: string; onListo: (token: string) => void }) {
  const [foto, setFoto] = useState<FotoCedula | null>(null);
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function enviar() {
    if (!foto) return;
    setError(undefined);
    setEnviando(true);
    try {
      const formulario = new FormData();
      formulario.append("imagen", foto.blob, "cedula.jpg");
      formulario.append("descriptor", JSON.stringify(foto.descriptor));
      const r = await api<{ token: string }>("/api/registraduria/cedula", { token, formulario });
      onListo(r.token);
    } catch (err) {
      setError(mensaje(err, "No fue posible validar la cédula"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-info-bg text-primary">
            <IdCard className="size-5" />
          </span>
          <div>
            <h2 className="text-lg font-bold">Cara frontal de la cédula</h2>
            <p className="text-sm text-tinta-2">
              Ubíquela dentro del marco, de frente, con buena luz y sin reflejos. Deben verse la foto y el número.
            </p>
          </div>
        </div>
        <CapturaDocumento onCambio={(f) => { setFoto(f); setError(undefined); }} />
        <p className="text-xs text-tinta-2">
          Se verificará que el número coincida con el registrado y que la foto corresponda al rostro del ciudadano. La
          imagen se guarda cifrada y solo puede consultarla el superadministrador para auditoría.
        </p>
      </section>
      {error && <Alerta tipo="error" titulo="No se pudo validar la cédula" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton variante="primario" onClick={enviar} cargando={enviando} disabled={!foto}>
          {enviando ? "Leyendo el documento…" : foto ? "Continuar al registro del rostro →" : "Tome o suba la foto"}
        </BigButton>
      </div>
    </>
  );
}

function PasoRostro({ token, onListo }: { token: string; onListo: (r: { nombre: string; habilitado: boolean }) => void }) {
  const camara = useCapturaFacial();
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function iniciar() {
    setError(undefined);
    try {
      const { descriptor } = await camara.capturar();
      setEnviando(true);
      const r = await api<{ nombre: string; habilitado: boolean }>("/api/registraduria/rostro",
        { token, cuerpo: { descriptor } });
      camara.detener();
      onListo(r);
    } catch (err) {
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
            no una fotografía.
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
