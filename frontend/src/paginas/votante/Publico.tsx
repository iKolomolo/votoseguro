// Pantallas públicas: acceso restringido, verificación de comprobante y resultados de votaciones cerradas.
import { CheckCircle2, Lock, Search, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { api, ErrorApi, fechaHora, miles, type Resultados } from "../../api";
import { BarrasCandidatos, Dona } from "../../componentes/Graficos";
import { Alerta, AvatarCandidato, BigButton, Cargando, GovHeader, Pantalla } from "../../componentes/ui";
import { useVotante } from "../../sesion";

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
            <li>• Acercarse a un puesto de atención de la Registraduría</li>
            <li>• Verificar su inscripción en la página oficial</li>
            <li>• Llamar a la línea de atención: 018000 965 965</li>
          </ul>
        </section>
        <BigButton variante="contorno" onClick={() => { reiniciar(); navegar("/", { replace: true }); }}>
          Volver al inicio
        </BigButton>
      </main>
    </Pantalla>
  );
}

interface Verificacion {
  encontrado: boolean; eleccion?: string; codigo_eleccion?: string; hora_aproximada?: string; hash_voto?: string;
  integro?: boolean; firma_valida?: boolean; escrutado?: boolean;
}

export function VerificarComprobante() {
  const navegar = useNavigate();
  const [codigo, setCodigo] = useState("");
  const [resultado, setResultado] = useState<Verificacion>();
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string>();

  async function verificar(e: FormEvent) {
    e.preventDefault();
    setCargando(true);
    setError(undefined);
    try {
      setResultado(await api<Verificacion>(`/api/publico/verificar/${encodeURIComponent(codigo.trim())}`));
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "Error al verificar");
    } finally {
      setCargando(false);
    }
  }

  const valido = resultado?.encontrado && resultado.integro && resultado.firma_valida;
  return (
    <Pantalla estrecha>
      <GovHeader titulo="Verificar comprobante" subtitulo="Confirme que su voto fue registrado" onVolver={() => navegar("/")} />
      <main className="contenido flex flex-1 flex-col gap-5 p-5 md:p-8">
        <form onSubmit={verificar} className="tarjeta flex flex-col gap-3 p-5 md:p-8">
          <label htmlFor="codigo" className="text-sm font-semibold">Código de verificación</label>
          <input id="codigo" className="entrada font-mono tracking-widest uppercase" placeholder="VS-2026-XXXXXXXX"
            required pattern="[Vv][Ss]-\d{4}-[A-Za-z0-9]{8}" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
          <BigButton variante="primario" cargando={cargando}><Search className="size-5" /> Verificar</BigButton>
        </form>
        {error && <Alerta tipo="error" titulo="Error">{error}</Alerta>}
        {resultado && !resultado.encontrado && (
          <Alerta tipo="error" titulo="Comprobante no encontrado" icono={<XCircle className="size-5" />}>
            Revise que el código esté bien escrito.
          </Alerta>
        )}
        {resultado?.encontrado && (
          <section className="tarjeta flex flex-col gap-3 p-5 md:p-8">
            <div className={`flex items-center gap-2 font-bold ${valido ? "text-exito" : "text-peligro"}`}>
              {valido ? <CheckCircle2 className="size-6" /> : <ShieldAlert className="size-6" />}
              {valido ? "Voto registrado e íntegro" : "El voto no superó la verificación de integridad"}
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-tinta-2">Votación</dt><dd className="font-semibold">{resultado.eleccion}</dd>
              <dt className="text-tinta-2">Código</dt><dd className="font-mono">{resultado.codigo_eleccion}</dd>
              <dt className="text-tinta-2">Hora aprox.</dt><dd>{fechaHora(resultado.hora_aproximada!)}</dd>
              <dt className="text-tinta-2">Firma ECDSA</dt><dd>{resultado.firma_valida ? "Válida" : "Inválida"}</dd>
              <dt className="text-tinta-2">Escrutado</dt><dd>{resultado.escrutado ? "Sí" : "Pendiente del cierre"}</dd>
              <dt className="text-tinta-2">Hash</dt><dd className="font-mono text-[10px] break-all">{resultado.hash_voto}</dd>
            </dl>
            <p className="text-xs text-tinta-2">La verificación confirma que su voto cifrado está en la urna digital. No revela por quién votó.</p>
          </section>
        )}
      </main>
    </Pantalla>
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
