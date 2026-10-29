// Pasos 1 a 3 del votante: documento, verificación facial y elegibilidad. La inscripción se hace antes en la
// Registraduría (paginas/registraduria).
import { AlertCircle, Check, CheckCircle2, CircleCheck, Landmark, Lock, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, ErrorApi } from "../../api";
import { useCapturaFacial, VistaCamara } from "../../biometria/CapturaFacial";
import { Alerta, BigButton, Campo, Cargando, GovHeader, LockBadge, Pantalla, ProgressSteps } from "../../componentes/ui";
import { useVotante } from "../../sesion";

export const TIPOS = [
  ["CC", "Cédula de Ciudadanía (CC)"],
  ["CE", "Cédula de Extranjería (CE)"],
  ["PA", "Pasaporte (PA)"],
  ["PPT", "Permiso por Protección Temporal (PPT)"],
] as const;

export function Identificacion() {
  const navegar = useNavigate();
  const { actualizar } = useVotante();
  const [datos, setDatos] = useState({ tipo_documento: "CC", documento: "" });
  const [error, setError] = useState<{ mensaje: string; noInscrito: boolean }>();
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setEnviando(true);
    try {
      const r = await api<{ token: string }>("/api/votante/identificacion", { cuerpo: datos });
      actualizar({ tokenFlujo: r.token });
      navegar("/biometria");
    } catch (err) {
      if (err instanceof ErrorApi && err.estado === 423) {
        navegar("/bloqueado", { state: { motivo: err.message } });
        return;
      }
      setError({
        mensaje: err instanceof ErrorApi ? err.message : "No fue posible validar el documento",
        noInscrito: err instanceof ErrorApi && err.estado === 404,
      });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Identificación del Votante" subtitulo="Paso 1 de 3" onVolver={() => navegar("/")} />
      <ProgressSteps paso={1} />
      <form onSubmit={enviar} className="contenido flex flex-1 flex-col gap-4 p-5 md:p-8">
        <LockBadge />
        <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
          <div>
            <h2 className="text-lg font-bold">Documento de identidad</h2>
            <p className="text-sm text-tinta-2">Use el documento con el que se inscribió en la Registraduría.</p>
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
        {error && (
          <Alerta tipo={error.noInscrito ? "aviso" : "error"} titulo={error.noInscrito ? "Documento no inscrito" : "No se pudo continuar"}
            icono={<AlertCircle className="size-5" />}>
            {error.mensaje}
            {error.noInscrito && (
              <Link to="/registraduria" className="mt-2 flex items-center gap-1 font-bold text-primary underline">
                <Landmark className="size-4" /> Ir a la Registraduría
              </Link>
            )}
          </Alerta>
        )}
        <div className="pt-2 pb-6 md:mx-auto md:w-full md:max-w-sm">
          <BigButton type="submit" cargando={enviando}>Continuar →</BigButton>
        </div>
      </form>
    </Pantalla>
  );
}

export function Biometria() {
  const navegar = useNavigate();
  const { flujo, actualizar } = useVotante();
  const camara = useCapturaFacial();
  const [error, setError] = useState<string>();
  const [verificado, setVerificado] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!flujo.tokenFlujo) navegar("/identificacion", { replace: true });
  }, [flujo.tokenFlujo, navegar]);

  async function iniciar() {
    setError(undefined);
    try {
      const { descriptor } = await camara.capturar();
      setEnviando(true);
      const r = await api<{ token: string }>("/api/votante/biometria", { token: flujo.tokenFlujo, cuerpo: { descriptor } });
      camara.detener();
      actualizar({ tokenFlujo: r.token });
      setVerificado(true);
    } catch (err) {
      if (err instanceof ErrorApi && err.estado === 423) {
        navegar("/bloqueado", { state: { motivo: err.message } });
        return;
      }
      setError(err instanceof Error ? err.message : "No fue posible verificar el rostro");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Verificación Facial"
        subtitulo="Paso 2 de 3 — Confirme su identidad"
        onVolver={() => navegar("/identificacion")} />
      <ProgressSteps paso={2} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <LockBadge />
        <section className="tarjeta flex flex-col items-center gap-5 p-6 lg:flex-row lg:justify-center lg:gap-12 lg:p-10">
          {verificado ? (
            <div className="relative size-52 shrink-0 rounded-full border-[3.5px] border-exito bg-exito-bg/40 lg:size-64">
              <div className="absolute inset-6 flex items-center justify-center rounded-full bg-sutil">
                <CheckCircle2 className="size-16 fill-exito text-white" />
              </div>
            </div>
          ) : (
            <VistaCamara video={camara.video} estado={camara.estado} rostroVisible={camara.rostroVisible} />
          )}
          <div className="flex flex-col items-center gap-5 lg:max-w-sm lg:items-start">
            {verificado ? (
              <Alerta tipo="exito" titulo="Identidad verificada correctamente">
                Puede continuar con el proceso de votación.
              </Alerta>
            ) : (
              // Letra grande y en negrilla: quien usa gafas puede tener que quitárselas para la verificación.
              <p aria-live="polite" className="max-w-[320px] text-center text-2xl font-bold leading-snug text-tinta lg:max-w-none lg:text-left lg:text-3xl">
                {camara.instruccion}
              </p>
            )}
          </div>
        </section>
        {error && <Alerta tipo="error" titulo="Verificación fallida" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
        <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
          {verificado ? (
            <BigButton onClick={() => navegar("/elegibilidad")}>Continuar →</BigButton>
          ) : (
            <BigButton variante="primario" onClick={iniciar} cargando={camara.estado === "capturando" || enviando}
              disabled={camara.estado !== "listo"}>
              {camara.estado === "capturando" ? "Analizando rostro…" : enviando ? "Verificando…" : "Iniciar verificación"}
            </BigButton>
          )}
        </div>
      </main>
    </Pantalla>
  );
}

interface Requisito { clave: string; texto: string; ok: boolean }

export function Elegibilidad() {
  const navegar = useNavigate();
  const { flujo, actualizar } = useVotante();
  const [datos, setDatos] = useState<{ habilitado: boolean; requisitos: Requisito[]; nombre: string; token?: string }>();
  const [error, setError] = useState<string>();
  const consultado = useRef(false);

  useEffect(() => {
    if (consultado.current) return; // solo una consulta, aunque React monte dos veces en desarrollo
    consultado.current = true;
    if (!flujo.tokenFlujo) {
      navegar("/identificacion", { replace: true });
      return;
    }
    api<typeof datos>("/api/votante/elegibilidad", { token: flujo.tokenFlujo })
      .then((r) => {
        setDatos(r);
        if (r?.token) actualizar({ tokenVotante: r.token, nombre: r.nombre, tokenFlujo: undefined });
      })
      .catch((e) => setError(e instanceof ErrorApi ? e.message : "Error al validar"));
  }, [flujo.tokenFlujo, navegar, actualizar]);

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Validación de Elegibilidad" subtitulo="Verificando requisitos" onVolver={() => navegar("/")} />
      <ProgressSteps paso={3} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <LockBadge />
        {error && <Alerta tipo="error" titulo="No se pudo validar">{error}</Alerta>}
        {!datos && !error && <Cargando texto="Revisando habilitación…" />}
        {datos && (
          <>
            <section className="tarjeta p-6">
              <h2 className="text-lg font-bold">Revisando habilitación electoral</h2>
              <ul className="grid gap-3 pt-4 md:grid-cols-2">
                {datos.requisitos.map((r) => (
                  <li key={r.clave} className={`flex items-center gap-3 rounded-xl border-[1.5px] p-3 ${
                    r.ok ? "border-exito/30 bg-exito-suave" : "border-peligro/30 bg-peligro-bg"}`}>
                    <span className={`flex size-8 items-center justify-center rounded-full text-white ${r.ok ? "bg-exito" : "bg-peligro"}`}>
                      {r.ok ? <Check className="size-4" strokeWidth={3} /> : <X className="size-4" strokeWidth={3} />}
                    </span>
                    <span className="text-sm font-semibold">{r.texto}</span>
                    <span className="sr-only">{r.ok ? "cumple" : "no cumple"}</span>
                  </li>
                ))}
              </ul>
            </section>
            {datos.habilitado ? (
              <>
                <Alerta tipo="exito" titulo="Votante habilitado" icono={<CircleCheck className="size-6" />}>
                  Todos los requisitos fueron verificados exitosamente{datos.nombre ? `, ${datos.nombre}` : ""}.
                </Alerta>
                <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
                  <BigButton onClick={() => navegar("/elecciones")}>Ver votaciones disponibles →</BigButton>
                </div>
              </>
            ) : (
              <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
                <BigButton variante="peligro" onClick={() => navegar("/bloqueado")}>
                  <Lock className="size-5" /> Ver detalle
                </BigButton>
              </div>
            )}
          </>
        )}
      </main>
    </Pantalla>
  );
}
