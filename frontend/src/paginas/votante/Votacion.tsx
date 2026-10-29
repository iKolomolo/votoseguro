// Paso 4 del votante: elegir la votación y el candidato, confirmar y recibir el comprobante.
import {
  AlertCircle, BarChart3, CheckCircle2, ChevronRight, CircleCheck, Clock, Lock, Play, ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ErrorApi, fechaHora, soloFecha, type Candidato, type Comprobante, type Eleccion } from "../../api";
import {
  Alerta, AvatarCandidato, BigButton, Cargando, GovHeader, InsigniaEstado, LockBadge, NumeroCandidato, Pantalla,
  ProgressSteps,
} from "../../componentes/ui";
import { useVotante } from "../../sesion";

function useSesionVotante() {
  const ctx = useVotante();
  const navegar = useNavigate();
  useEffect(() => {
    if (!ctx.flujo.tokenVotante) navegar("/", { replace: true });
  }, [ctx.flujo.tokenVotante, navegar]);
  return ctx;
}

function manejarSesion(e: unknown, navegar: (r: string) => void, setError: (m: string) => void) {
  if (e instanceof ErrorApi && e.estado === 401) navegar("/");
  else setError(e instanceof Error ? e.message : "Error inesperado");
}

export function Elecciones() {
  const navegar = useNavigate();
  const { flujo, actualizar } = useSesionVotante();
  const [lista, setLista] = useState<Eleccion[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!flujo.tokenVotante) return;
    const orden = { activa: 0, programada: 1, finalizada: 2 };
    api<Eleccion[]>("/api/votante/elecciones", { token: flujo.tokenVotante })
      .then((l) => setLista([...l].sort((a, b) => orden[a.estado] - orden[b.estado])))
      .catch((e) => manejarSesion(e, navegar, setError));
  }, [flujo.tokenVotante, navegar]);

  const activas = lista?.filter((e) => e.estado === "activa").length ?? 0;

  return (
    <Pantalla>
      <GovHeader titulo="Votaciones Disponibles" subtitulo="Elija un proceso electoral activo" onVolver={() => navegar("/")} />
      <ProgressSteps paso={4} />
      <main className="contenido flex flex-1 flex-col gap-4 p-5 md:p-8">
        <LockBadge />
        {error && <Alerta tipo="error" titulo="Error">{error}</Alerta>}
        {!lista && !error && <Cargando />}
        {lista && (
          <p className="text-sm font-semibold tracking-[0.7px] text-tinta-2 uppercase">
            {activas} votación(es) activa(s) hoy
          </p>
        )}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {lista?.map((e) => {
            const puedeVotar = e.estado === "activa" && !e.ya_voto;
            return (
              <article key={e.id_eleccion}
                className={`tarjeta p-5 ${puedeVotar ? "shadow-md" : "bg-sutil-2 opacity-80"}`}>
                <div className="flex items-start justify-between">
                  <InsigniaEstado estado={e.estado} />
                  <span className="font-mono text-xs text-tinta-2">{e.tipo}</span>
                </div>
                <h2 className={`pt-3 font-bold ${puedeVotar ? "text-tinta" : "text-tinta-2"}`}>{e.nombre}</h2>
                <p className="flex items-center gap-2 pt-2 text-xs text-tinta-2"><Clock className="size-3.5" />Inicio: {fechaHora(e.fecha_inicio)}</p>
                <p className="flex items-center gap-2 text-xs text-tinta-2"><Clock className="size-3.5" />Cierre: {fechaHora(e.fecha_fin)}</p>
                {puedeVotar && (
                  <button onClick={() => { actualizar({ eleccion: e, candidato: undefined }); navegar("/candidatos"); }}
                    className="mt-3 flex items-center gap-1 text-sm font-bold text-primary hover:underline">
                    Votar ahora <ChevronRight className="size-4" />
                  </button>
                )}
                {e.ya_voto && (
                  <p className="mt-3 flex items-center gap-1 text-sm font-semibold text-exito">
                    <CheckCircle2 className="size-4" /> Usted ya votó en este proceso
                  </p>
                )}
                {e.estado === "finalizada" && (
                  <Link to={`/resultados/${e.id_eleccion}`} className="mt-3 flex items-center gap-1 text-sm font-bold text-primary hover:underline">
                    <BarChart3 className="size-4" /> Ver resultados
                  </Link>
                )}
              </article>
            );
          })}
        </div>
      </main>
    </Pantalla>
  );
}

export function Candidatos() {
  const navegar = useNavigate();
  const { flujo, actualizar } = useSesionVotante();
  const [lista, setLista] = useState<Candidato[]>();
  const [seleccion, setSeleccion] = useState<number | undefined>(flujo.candidato?.id_candidato);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!flujo.tokenVotante || !flujo.eleccion) return;
    api<{ candidatos: Candidato[] }>(`/api/votante/elecciones/${flujo.eleccion.id_eleccion}/candidatos`,
      { token: flujo.tokenVotante })
      .then((r) => setLista(r.candidatos)).catch((e) => manejarSesion(e, navegar, setError));
  }, [flujo.tokenVotante, flujo.eleccion, navegar]);

  const elegido = lista?.find((c) => c.id_candidato === seleccion);

  return (
    <Pantalla>
      <GovHeader titulo="Candidatos" subtitulo={flujo.eleccion?.nombre} onVolver={() => navegar("/elecciones")} />
      <main className="contenido flex flex-1 flex-col gap-3 p-5 md:p-8">
        {error && <Alerta tipo="error" titulo="Error">{error}</Alerta>}
        {!lista && !error && <Cargando />}
        <fieldset className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 lg:gap-4">
          <legend className="sr-only">Seleccione un único candidato</legend>
          {lista?.map((c) => {
            const activo = c.id_candidato === seleccion;
            return (
              <label key={c.id_candidato}
                className={`tarjeta flex cursor-pointer items-center gap-4 p-4 transition lg:p-5 ${
                  activo ? "border-primary ring-2 ring-primary/30" : "hover:border-primary/50"}`}>
                <input type="radio" name="candidato" className="sr-only" checked={activo}
                  onChange={() => setSeleccion(c.id_candidato)} />
                <AvatarCandidato candidato={c} />
                <div className="flex-1">
                  <NumeroCandidato numero={c.numero} />
                  <p className="pt-1 text-sm leading-[17.5px] font-bold">{c.nombre}</p>
                  <p className="text-xs text-tinta-2">{c.partido}</p>
                </div>
                <span aria-hidden className={`flex size-6 items-center justify-center rounded-full border-2 ${
                  activo ? "border-primary bg-primary text-white" : "border-linea"}`}>
                  {activo && <CheckCircle2 className="size-4" />}
                </span>
              </label>
            );
          })}
        </fieldset>
        <div className="pt-3 pb-6 md:mx-auto md:w-full md:max-w-sm">
          <BigButton variante="primario" disabled={!elegido}
            onClick={() => { actualizar({ candidato: elegido }); navegar("/confirmar"); }}>
            {elegido ? "Proceder a votar →" : "Seleccione un candidato"}
          </BigButton>
        </div>
      </main>
    </Pantalla>
  );
}

export function Confirmar() {
  const navegar = useNavigate();
  const { flujo, actualizar } = useSesionVotante();
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string>();
  const { eleccion, candidato } = flujo;

  useEffect(() => {
    if (!eleccion || !candidato) navegar("/elecciones", { replace: true });
  }, [eleccion, candidato, navegar]);
  if (!eleccion || !candidato) return null;

  async function emitir() {
    setEnviando(true);
    setError(undefined);
    try {
      const comprobante = await api<Comprobante>("/api/votante/votos", {
        token: flujo.tokenVotante, cuerpo: { id_eleccion: eleccion!.id_eleccion, id_candidato: candidato!.id_candidato },
      });
      // El candidato se conserva hasta elegir otra votación: borrarlo aquí haría que esta pantalla
      // redirigiera a /elecciones antes de mostrar el comprobante.
      actualizar({ comprobante });
      navegar("/comprobante", { replace: true });
    } catch (e) {
      manejarSesion(e, navegar, setError);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Confirmar Voto" subtitulo="Revise su selección antes de enviar" />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <LockBadge />
        <Alerta tipo="aviso" icono={<AlertCircle className="size-5 fill-alerta-texto text-alerta-bg" />}>
          <span className="font-semibold">Una vez confirmado, el voto es INMUTABLE y no podrá cambiarse ni eliminarse.</span>
        </Alerta>
        <section className="overflow-hidden rounded-2xl border-[1.5px] border-primary bg-white">
          <p className="bg-primary px-5 py-2 text-xs font-semibold tracking-[0.6px] text-sobre-primario uppercase">
            Candidato seleccionado
          </p>
          <div className="flex items-center gap-4 p-5 md:p-8">
            <AvatarCandidato candidato={candidato} tamano="size-20" />
            <div>
              <NumeroCandidato numero={candidato.numero} />
              <p className="pt-2 text-xl font-bold">{candidato.nombre}</p>
              <p className="text-tinta-2">{candidato.partido}</p>
            </div>
          </div>
          <p className="border-t-[1.5px] border-linea bg-sutil-2 px-5 py-3 text-xs text-tinta-2">
            {eleccion.nombre} · {soloFecha(new Date().toISOString())}
          </p>
        </section>
        {error && <Alerta tipo="error" titulo="No se registró el voto">{error}</Alerta>}
        <div className="flex flex-col gap-5 md:flex-row-reverse md:gap-3">
          <BigButton onClick={emitir} cargando={enviando}>
            {!enviando && <ShieldCheck className="size-5" />} {enviando ? "Cifrando y enviando…" : "Confirmar y emitir voto"}
          </BigButton>
          <BigButton variante="contorno" onClick={() => navegar("/candidatos")} disabled={enviando}>Cambiar selección</BigButton>
        </div>
      </main>
    </Pantalla>
  );
}

export function ComprobanteVoto() {
  const navegar = useNavigate();
  const { flujo } = useVotante();
  const c = flujo.comprobante;
  useEffect(() => {
    if (!c) navegar("/", { replace: true });
  }, [c, navegar]);
  if (!c) return null;

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Voto Registrado" />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <section className="tarjeta flex flex-col gap-4 p-6">
          <div className="flex flex-col items-center gap-2 border-b-[1.5px] border-linea pb-5 text-center">
            <div className="flex size-16 items-center justify-center rounded-full bg-exito-bg">
              <Lock className="size-7 text-exito" />
            </div>
            <h2 className="text-lg font-bold text-exito">Voto cifrado y almacenado</h2>
            <p className="text-sm text-tinta-2">
              Su voto fue protegido con criptografía de curva elíptica (ECC P-256 + AES-256) y registrado de forma inmutable.
            </p>
          </div>
          <p className="text-xs font-semibold tracking-[0.6px] text-tinta-2 uppercase">Comprobante de votación</p>
          <div className="rounded-xl border-[1.5px] border-linea bg-fondo p-4 text-center">
            <p className="text-xs text-tinta-2">Código de verificación único</p>
            <p className="py-1 font-mono text-2xl font-black tracking-[2.4px] break-all text-primary" aria-label={`Código ${c.codigo.split("").join(" ")}`}>
              {c.codigo}
            </p>
            <p className="text-xs text-tinta-2">Este código NO identifica su candidato. Solo confirma que votó.</p>
          </div>
          <button onClick={() => navigator.clipboard?.writeText(c.codigo)}
            className="text-sm font-semibold text-primary underline">Copiar código</button>
          <ul className="flex flex-col gap-2 text-sm text-tinta-2">
            {["Su voto es secreto y anónimo.", "No puede ser modificado ni eliminado.",
              "Puede verificar su participación con el código anterior."].map((t) => (
              <li key={t} className="flex items-start gap-2"><Play className="mt-0.5 size-4 shrink-0 fill-exito text-exito" />{t}</li>
            ))}
          </ul>
        </section>
        <div className="pb-6 md:mx-auto md:w-full md:max-w-sm">
          <BigButton onClick={() => navegar("/gracias", { replace: true })}>Ver confirmación final →</BigButton>
        </div>
      </main>
    </Pantalla>
  );
}

export function Gracias() {
  const navegar = useNavigate();
  const { flujo, actualizar, reiniciar } = useVotante();
  return (
    <Pantalla className="bg-exito text-white">
      <main className="contenido flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center lg:max-w-2xl">
        <div className="flex size-28 items-center justify-center rounded-full bg-white shadow-2xl">
          <CircleCheck className="size-16 fill-exito text-white" />
        </div>
        <h1 className="text-4xl leading-[45px] font-black">¡Gracias por votar!</h1>
        <p className="text-xl font-semibold">Su voto fue guardado correctamente</p>
        <p className="leading-[26px] text-white/85">
          Ha ejercido su derecho democrático. Su participación fortalece la democracia colombiana.
        </p>
        <span className="flex items-center gap-2 rounded-full bg-white/20 px-4 py-2 text-sm font-semibold">
          <Lock className="size-4" /> Proceso finalizado de forma segura
        </span>
        <p className="pt-4 text-sm text-exito-borde">Registraduría Nacional del Estado Civil</p>
        <p className="text-xs text-exito-borde/80">VotoSeguro Colombia · Versión 2026</p>
      </main>
      <footer className="flex flex-col gap-3 px-6 pb-12 md:mx-auto md:w-full md:max-w-sm">
        {flujo.tokenVotante && (
          <button onClick={() => { actualizar({ comprobante: undefined }); navegar("/elecciones"); }}
            className="text-sm font-semibold underline">Ver otras votaciones activas</button>
        )}
        <BigButton variante="contorno" onClick={() => { reiniciar(); navegar("/", { replace: true }); }}>
          Salir de la plataforma
        </BigButton>
      </footer>
    </Pantalla>
  );
}
