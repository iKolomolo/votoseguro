// Pantallas públicas: acceso restringido, verificación de participación y resultados de votaciones cerradas.
import { CheckCircle2, Lock, Search, XCircle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { api, ErrorApi, fechaDia, miles, soloFecha, type Resultados } from "../../api";
import { BarrasCandidatos, Dona } from "../../componentes/Graficos";
import { Alerta, AvatarCandidato, BigButton, Cargando, Campo, GovHeader, LockBadge, Pantalla } from "../../componentes/ui";
import { useVotante } from "../../sesion";
import { TIPOS } from "./Identificacion";

export function Bloqueado() {
  const navegar = useNavigate();
  const { reiniciar } = useVotante();
  const motivo = (useLocation().state as { motivo?: string } | null)?.motivo;
  return (
    <Pantalla estrecha>
      <header className="bg-peligro pt-10 pb-6 text-white md:pt-7 lg:pt-8 lg:pb-8">
        <div className="contenido px-5 md:px-8">
          <h1 className="text-2xl leading-8 font-bold lg:text-3xl lg:leading-10">Acceso Restringido</h1>
          <p className="pt-1 text-sm text-peligro-borde lg:text-base">No es posible continuar con el proceso</p>
        </div>
      </header>
      <main className="contenido flex flex-1 flex-col gap-5 px-5 py-6 md:p-8">
        <section className="flex flex-col items-center gap-4 rounded-2xl border-[1.5px] border-peligro/30 bg-white p-6 text-center shadow-sm">
          <div className="flex size-20 items-center justify-center rounded-full bg-peligro-bg-2">
            <Lock className="size-10 fill-peligro text-peligro" />
          </div>
          <h2 className="text-xl font-bold">{motivo ? "Cuenta bloqueada" : "No cumple los requisitos electorales"}</h2>
          <p className="leading-[26px] text-tinta-2">
            {motivo ?? "Su documento no está habilitado en el censo electoral para esta votación. Esto puede deberse a que no realizó inscripción o tiene una restricción vigente."}
          </p>
        </section>
        <section className="rounded-xl border-[1.5px] border-alerta-texto/30 bg-alerta-bg p-4">
          <p className="text-sm font-bold text-alerta-texto">¿Qué puede hacer?</p>
          <ul className="flex flex-col gap-1 pt-2 text-sm text-alerta-fuerte">
            <li>• Volver a inscribirse en la Registraduría simulada de VotoSeguro</li>
            <li>• Escribir al equipo del proyecto (el correo está en la <a href="/privacidad" className="font-bold underline">Política de privacidad</a>)</li>
            <li>• Recuerde que VotoSeguro es una simulación: no afecta su inscripción real como votante</li>
          </ul>
        </section>
        <BigButton variante="contorno" onClick={() => { reiniciar(); navegar("/", { replace: true }); }}>
          Volver al inicio
        </BigButton>
      </main>
    </Pantalla>
  );
}

interface Participacion {
  nombre: string;
  tipo_documento: string;
  documento: string | null;
  votaciones: { eleccion: string; codigo: string; fecha: string }[];
}

/** Verificación de comprobante por cédula y fecha de nacimiento: dice si la persona votó y en qué votación. */
export function VerificarComprobante() {
  const navegar = useNavigate();
  const [consulta, setConsulta] = useState({ tipo_documento: "CC", documento: "", fecha_nacimiento: "" });
  const [datos, setDatos] = useState<Participacion>();
  const [error, setError] = useState<string>();
  const [cargando, setCargando] = useState(false);

  async function consultar(e: FormEvent) {
    e.preventDefault();
    setCargando(true);
    setError(undefined);
    setDatos(undefined);
    try {
      setDatos(await api<Participacion>("/api/publico/participacion", { cuerpo: consulta }));
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No fue posible hacer la consulta");
    } finally {
      setCargando(false);
    }
  }

  const cambiar = (campo: keyof typeof consulta) => (e: { target: { value: string } }) =>
    setConsulta((c) => ({ ...c, [campo]: e.target.value }));

  return (
    <Pantalla estrecha>
      <GovHeader titulo="Verificar comprobante" subtitulo="Consulte con su cédula si su voto quedó registrado"
        onVolver={() => navegar("/")} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <LockBadge />
        <form onSubmit={consultar} className="tarjeta flex flex-col gap-4 p-5 md:p-8">
          <div className="grid gap-4 md:grid-cols-2">
            <Campo etiqueta="Tipo de Documento" id="tipo">
              <select id="tipo" className="entrada" value={consulta.tipo_documento} onChange={cambiar("tipo_documento")}>
                {TIPOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Número de Documento" id="documento">
              <input id="documento" className="entrada" inputMode="numeric" required autoComplete="off"
                pattern="[0-9A-Za-z]{5,15}" title="Entre 5 y 15 caracteres, sin puntos ni espacios"
                placeholder="Ej: 1020304050" value={consulta.documento} onChange={cambiar("documento")} />
            </Campo>
            <Campo etiqueta="Fecha de nacimiento" id="nacimiento">
              <input id="nacimiento" type="date" className="entrada" required max={new Date().toISOString().slice(0, 10)}
                value={consulta.fecha_nacimiento} onChange={cambiar("fecha_nacimiento")} />
            </Campo>
          </div>
          <BigButton type="submit" variante="primario" cargando={cargando}><Search className="size-5" /> Consultar</BigButton>
        </form>
        {error && <Alerta tipo="error" titulo="Sin resultados" icono={<XCircle className="size-5" />}>{error}</Alerta>}
        {datos && <ResultadoParticipacion datos={datos} />}
      </main>
    </Pantalla>
  );
}

function ResultadoParticipacion({ datos }: { datos: Participacion }) {
  const voto = datos.votaciones.length > 0;
  return (
    <>
      <section className="tarjeta flex flex-col gap-4 p-5 pb-6 md:p-8">
        <div className={`flex items-center gap-2 text-lg font-bold ${voto ? "text-exito" : "text-alerta-texto"}`}>
          {voto ? <CheckCircle2 className="size-6" /> : <XCircle className="size-6" />}
          {voto ? "Sí registra voto" : "No registra votos"}
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-tinta-2">Votante</dt><dd className="font-semibold">{datos.nombre}</dd>
          <dt className="text-tinta-2">Documento</dt><dd>{datos.tipo_documento} {datos.documento ?? "—"}</dd>
          <dt className="text-tinta-2">Fecha de consulta</dt><dd>{soloFecha(new Date().toISOString())}</dd>
        </dl>
        {voto && (
          <div className="overflow-x-auto rounded-xl border-[1.5px] border-linea">
            <table className="w-full text-left text-sm">
              <thead className="bg-sutil-2 text-xs text-tinta-2 uppercase">
                <tr>
                  <th scope="col" className="px-3 py-2">Votación en la que participó</th>
                  <th scope="col" className="px-3 py-2">Fecha del voto</th>
                </tr>
              </thead>
              <tbody>
                {datos.votaciones.map((v) => (
                  <tr key={v.codigo} className="border-t border-linea">
                    <td className="px-3 py-2">
                      <p className="font-semibold">{v.eleccion}</p>
                      <p className="font-mono text-xs text-tinta-2">{v.codigo}</p>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">{fechaDia(v.fecha)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-tinta-2">
          Esta consulta solo confirma si usted votó y en qué fecha. No muestra por quién: su voto no está asociado a su
          identidad.
        </p>
      </section>
    </>
  );
}

export function ResultadosPublicos() {
  const navegar = useNavigate();
  const { id } = useParams();
  const [datos, setDatos] = useState<Resultados>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    api<Resultados>(`/api/publico/elecciones/${id}/resultados`).then(setDatos)
      .catch((e) => setError(e instanceof ErrorApi ? e.message : "Error"));
  }, [id]);
  const ganador = datos?.candidatos[0];
  return (
    <Pantalla>
      <GovHeader titulo="Resultados" subtitulo={datos?.eleccion.nombre} onVolver={() => navegar(-1)} />
      <main className="contenido flex flex-1 flex-col gap-4 p-5 md:p-8">
        {error && <Alerta tipo="error" titulo="No disponible">{error}</Alerta>}
        {!datos && !error && <Cargando />}
        {datos && ganador && (
          <>
            <section className="rounded-2xl bg-primary p-5 text-white">
              <p className="text-xs font-semibold tracking-[0.6px] text-sobre-primario uppercase">Candidato con más votos</p>
              <div className="flex items-center gap-3 pt-3">
                <AvatarCandidato candidato={ganador} />
                <div>
                  <p className="text-lg font-bold">{ganador.nombre}</p>
                  <p className="text-sm text-sobre-primario">{ganador.partido}</p>
                  <p className="text-2xl font-black">{miles(ganador.votos)} <span className="text-base font-normal">votos</span></p>
                </div>
              </div>
            </section>
            <div className="grid gap-4 md:grid-cols-2">
              <section className="tarjeta p-5 md:p-8"><Dona candidatos={datos.candidatos} total={datos.total_votos} /></section>
              <section className="tarjeta p-5 md:p-8"><BarrasCandidatos candidatos={datos.candidatos} /></section>
            </div>
            <p className="text-center text-xs text-tinta-2">
              Participación {datos.participacion}% · {miles(datos.votaron)} de {miles(datos.habilitados)} habilitados
            </p>
          </>
        )}
      </main>
    </Pantalla>
  );
}
