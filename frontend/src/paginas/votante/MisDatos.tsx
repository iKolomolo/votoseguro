// Derechos del titular sobre su plantilla biométrica (Ley 1581 de 2012, art. 8): consultar qué se conserva y
// hasta cuándo, y revocarla. Antes debe probar su identidad con su documento y su rostro, como al votar.
import { AlertCircle, CircleCheck, Fingerprint, ShieldOff } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, ErrorApi, fechaDia, soloFecha } from "../../api";
import { retosDelToken, useCapturaFacial, VistaCamara } from "../../biometria/CapturaFacial";
import { Alerta, BigButton, Campo, GovHeader, LockBadge, Pantalla, ProgressSteps } from "../../componentes/ui";
import { TIPOS } from "./Identificacion";

const PASOS = ["Documento", "Rostro", "Mis datos"];
const mensaje = (e: unknown, otro: string) => (e instanceof Error ? e.message : otro);

interface DatosTitular {
  nombre: string;
  tipo_documento: string;
  documento: string | null;
  correo: string | null;
  inscrito_el: string | null;
  plantilla: { registrada_el: string | null; se_borra_el: string; dias_restantes: number } | null;
  cedula_verificada_el: string | null;
  autorizacion: {
    version: string; hash: string; fecha: string; acepto_datos: boolean; acepto_biometria: boolean;
    revocada_en: string | null;
  } | null;
}

export function MisDatos() {
  const navegar = useNavigate();
  const [paso, setPaso] = useState<1 | 2 | 3>(1);
  const [token, setToken] = useState<string>();
  const [datos, setDatos] = useState<DatosTitular>();

  async function cargar(t: string) {
    setDatos(await api<DatosTitular>("/api/votante/mis-datos", { token: t }));
  }

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Mis datos personales" subtitulo="Consulte o revoque su plantilla biométrica" onVolver={() => navegar("/")} />
      <ProgressSteps paso={paso} pasos={PASOS} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <LockBadge />
        {paso === 1 && <PasoDocumento onListo={(t) => { setToken(t); setPaso(2); }} />}
        {paso === 2 && token && (
          <PasoRostro token={token} onListo={async (t) => { setToken(t); await cargar(t); setPaso(3); }} />
        )}
        {paso === 3 && token && datos && <Resumen token={token} datos={datos} onCambio={() => cargar(token)} />}
      </main>
    </Pantalla>
  );
}

function PasoDocumento({ onListo }: { onListo: (token: string) => void }) {
  const navegar = useNavigate();
  const [datos, setDatos] = useState({ tipo_documento: "CC", documento: "" });
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setEnviando(true);
    try {
      onListo((await api<{ token: string }>("/api/votante/identificacion", { cuerpo: datos })).token);
    } catch (err) {
      if (err instanceof ErrorApi && err.estado === 423) {
        navegar("/bloqueado", { state: { motivo: err.message } });
        return;
      }
      setError(mensaje(err, "No fue posible validar el documento"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
        <div>
          <h2 className="text-lg font-bold">Identifíquese</h2>
          <p className="text-sm text-tinta-2">
            Para proteger sus datos, primero comprobamos que es usted con su documento y su rostro.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Campo etiqueta="Tipo de Documento" id="tipo">
            <select id="tipo" className="entrada" value={datos.tipo_documento}
              onChange={(e) => setDatos((d) => ({ ...d, tipo_documento: e.target.value }))}>
              {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Número de Documento" id="documento">
            <input id="documento" className="entrada" inputMode="numeric" required autoComplete="off"
              pattern="[0-9A-Za-z]{5,15}" title="Entre 5 y 15 caracteres, sin puntos ni espacios"
              placeholder="Ej: 1020304050" value={datos.documento}
              onChange={(e) => setDatos((d) => ({ ...d, documento: e.target.value }))} />
          </Campo>
        </div>
      </section>
      {error && <Alerta tipo="error" titulo="No se pudo continuar" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pt-2 pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton type="submit" variante="primario" cargando={enviando}>Continuar →</BigButton>
      </div>
    </form>
  );
}

function PasoRostro({ token, onListo }: { token: string; onListo: (token: string) => Promise<void> }) {
  const navegar = useNavigate();
  const camara = useCapturaFacial();
  const [error, setError] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function iniciar() {
    setError(undefined);
    try {
      const { descriptor, vida } = await camara.capturar(retosDelToken(token));
      setEnviando(true);
      const r = await api<{ token: string }>("/api/votante/biometria", { token, cuerpo: { descriptor, vida } });
      camara.detener();
      await onListo(r.token);
    } catch (err) {
      if (err instanceof ErrorApi && err.estado === 423) {
        navegar("/bloqueado", { state: { motivo: err.message } });
        return;
      }
      setError(mensaje(err, "No fue posible verificar el rostro"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <section className="tarjeta flex flex-col items-center gap-5 p-6 lg:flex-row lg:justify-center lg:gap-12 lg:p-10">
        <VistaCamara video={camara.video} estado={camara.estado} rostroVisible={camara.rostroVisible} />
        <p aria-live="polite" className="max-w-[320px] text-center text-2xl font-bold leading-snug text-tinta lg:max-w-sm lg:text-left lg:text-3xl">
          {camara.instruccion}
        </p>
      </section>
      {error && <Alerta tipo="error" titulo="Verificación fallida" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
      <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
        <BigButton variante="primario" onClick={iniciar} cargando={camara.estado === "capturando" || enviando}
          disabled={camara.estado !== "listo"}>
          {camara.estado === "capturando" ? "Analizando rostro…" : enviando ? "Verificando…" : "Verificar mi identidad"}
        </BigButton>
      </div>
    </>
  );
}

function Resumen({ token, datos, onCambio }: { token: string; datos: DatosTitular; onCambio: () => Promise<void> }) {
  const [revocando, setRevocando] = useState(false);
  const [revocada, setRevocada] = useState(false);
  const [error, setError] = useState<string>();
  const p = datos.plantilla;

  async function revocar() {
    if (!confirm("¿Revocar su plantilla biométrica? Se borrará de inmediato y no podrá votar con su rostro hasta "
      + "inscribirse de nuevo en la Registraduría.")) return;
    setRevocando(true);
    setError(undefined);
    try {
      await api("/api/votante/revocar-biometria", { token, metodo: "POST" });
      setRevocada(true);
      await onCambio();
    } catch (err) {
      setError(mensaje(err, "No fue posible revocar la plantilla"));
    } finally {
      setRevocando(false);
    }
  }

  return (
    <>
      <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
        <h2 className="text-lg font-bold">Bienvenido, {datos.nombre}</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-tinta-2">Documento</dt>
          <dd>{datos.tipo_documento} {datos.documento ?? "—"}</dd>
          <dt className="text-tinta-2">Correo</dt><dd className="break-all">{datos.correo ?? "—"}</dd>
          <dt className="text-tinta-2">Inscrito el</dt><dd>{datos.inscrito_el ? soloFecha(datos.inscrito_el) : "—"}</dd>
          <dt className="text-tinta-2">Cédula verificada</dt>
          <dd>{datos.cedula_verificada_el ? `${soloFecha(datos.cedula_verificada_el)} (la imagen no se guardó)` : "—"}</dd>
          <dt className="text-tinta-2">Plantilla biométrica</dt>
          <dd className="font-semibold">{p ? "Registrada, cifrada y cancelable" : "No hay plantilla registrada"}</dd>
          {p && (
            <>
              <dt className="text-tinta-2">Se borra el</dt>
              <dd>{fechaDia(p.se_borra_el)} — fin del piloto ({p.dias_restantes} días)</dd>
            </>
          )}
          {datos.autorizacion && (
            <>
              <dt className="text-tinta-2">Autorización</dt>
              <dd>
                Versión {datos.autorizacion.version}, aceptada el {soloFecha(datos.autorizacion.fecha)}.{" "}
                Datos biométricos: {datos.autorizacion.revocada_en
                  ? `revocados el ${soloFecha(datos.autorizacion.revocada_en)}`
                  : datos.autorizacion.acepto_biometria ? "autorizados" : "no autorizados"}.
              </dd>
              <dt className="text-tinta-2">Huella del texto</dt>
              <dd className="font-mono text-[10px] break-all">{datos.autorizacion.hash}</dd>
            </>
          )}
        </dl>
        <p className="text-xs text-tinta-2">
          La plantilla no es una fotografía: es una transformación secreta y revocable de las medidas de su rostro, que
          no permite reconstruir su imagen. Sus votos no están asociados a ella.
        </p>
      </section>

      {revocada && (
        <Alerta tipo="exito" titulo="Plantilla revocada" icono={<CircleCheck className="size-5" />}>
          Su plantilla biométrica fue borrada. Si quiere volver a votar con su rostro, inscríbase de nuevo en la{" "}
          <Link to="/registraduria" className="font-bold underline">Registraduría</Link>.
        </Alerta>
      )}
      {error && <Alerta tipo="error" titulo="No se pudo revocar" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}

      {p && (
        <section className="tarjeta flex flex-col gap-3 p-5 md:p-8">
          <h3 className="flex items-center gap-2 font-bold"><Fingerprint className="size-5 text-primary" /> Revocar mi plantilla</h3>
          <p className="text-sm text-tinta-2">
            Puede retirar en cualquier momento la autorización de sus datos biométricos (Ley 1581 de 2012, art. 8). La
            plantilla se borra de inmediato. Los votos que ya emitió no cambian.
          </p>
          <BigButton variante="peligro" onClick={revocar} cargando={revocando}>
            <ShieldOff className="size-5" /> Revocar y borrar mi plantilla
          </BigButton>
        </section>
      )}
      <p className="pb-6 text-center text-xs text-tinta-2">
        ¿Otra solicitud sobre sus datos? Escriba a nicololmomo123@gmail.com. Las consultas se responden en máximo 10
        días hábiles y los reclamos en máximo 15.
      </p>
    </>
  );
}

