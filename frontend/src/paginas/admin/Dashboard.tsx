import { Activity, CalendarPlus, CircleX, Server, Users, Vote } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { fechaHora, miles, soloFecha, soloHora, type Eleccion, type EstadoServicio, type RegistroAuditoria } from "../../api";
import { Anillo } from "../../componentes/Graficos";
import { Alerta, Cargando, EccBadge } from "../../componentes/ui";
import { useAdmin } from "../../sesion";
import { AdminHeader, puede, useApiAdmin, useDatos } from "./Layout";

interface Tablero {
  eleccion: Eleccion | null;
  votos_emitidos: number;
  habilitados: number;
  participacion: number;
  votantes_activos: number;
  disponibilidad: number | null;
  sistema: EstadoServicio[];
  actividad: RegistroAuditoria[];
}

function StatCard({ titulo, valor, detalle, icono, fondo }: {
  titulo: string; valor: string; detalle: string; icono: React.ReactNode; fondo: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border-[1.5px] border-linea bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold tracking-[0.3px] text-tinta-2 uppercase">{titulo}</p>
        <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${fondo}`}>{icono}</span>
      </div>
      <p className="text-2xl leading-6 font-black">{valor}</p>
      <p className="text-xs text-tinta-2">{detalle}</p>
    </div>
  );
}

export function Dashboard() {
  const { sesion } = useAdmin();
  const navegar = useNavigate();
  const llamar = useApiAdmin();
  const { datos, error, recargar } = useDatos<Tablero>("/api/admin/dashboard");
  const [cerrando, setCerrando] = useState(false);

  useEffect(() => {
    const id = setInterval(recargar, 15000); // actualización en vivo
    return () => clearInterval(id);
  }, [recargar]);

  async function cerrarVotacion() {
    const e = datos?.eleccion;
    if (!e || !confirm(`¿Cerrar "${e.nombre}" ahora? Se hará el escrutinio y no se recibirán más votos.`)) return;
    setCerrando(true);
    try {
      await llamar(`/api/admin/elecciones/${e.id_eleccion}/cerrar`, { metodo: "POST" });
      navegar(`/admin/resultados?eleccion=${e.id_eleccion}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error");
    } finally {
      setCerrando(false);
    }
  }

  const e = datos?.eleccion;
  const gestor = puede(sesion?.usuario, "gestionar");
  return (
    <>
      <AdminHeader titulo="Dashboard Electoral" subtitulo={`Jornada · ${soloFecha(new Date().toISOString())}`}
        accion={e?.estado === "activa" && (
          <span className="flex items-center gap-1.5 rounded-full border-[1.5px] border-exito/30 bg-exito-bg px-2.5 py-1 text-[10px] font-bold text-exito">
            <span className="size-1.5 animate-pulse rounded-full bg-exito" /> EN VIVO
          </span>
        )} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <EccBadge />
        {error && <Alerta tipo="error" titulo="Error">{error}</Alerta>}
        {!datos && !error && <Cargando />}
        {datos && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatCard titulo="Votos emitidos" valor={miles(datos.votos_emitidos)} detalle={`de ${miles(datos.habilitados)} habilitados`}
                icono={<Vote className="size-4 text-primary" />} fondo="bg-info-bg-2" />
              <StatCard titulo="Participación" valor={`${datos.participacion}%`} detalle="Meta: 60%"
                icono={<Activity className="size-4 text-exito" />} fondo="bg-exito-bg" />
              <StatCard titulo="Usuarios activos" valor={String(datos.votantes_activos)} detalle="en los últimos 15 min"
                icono={<Users className="size-4 text-alerta-texto" />} fondo="bg-alerta-bg" />
              <StatCard titulo="Uptime sistema" valor={datos.disponibilidad === null ? "—" : `${datos.disponibilidad}%`} detalle="Última hora"
                icono={<Server className="size-4 text-exito" />} fondo="bg-exito-bg" />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <section className="tarjeta p-4 shadow-none">
                <h2 className="text-sm font-bold">Estado de la jornada</h2>
                {e ? (
                  <div className="flex flex-wrap items-center gap-4 pt-3">
                    <Anillo porcentaje={datos.participacion} valor={`${datos.participacion}%`} etiqueta="participación" />
                    <div className="min-w-40 flex-1 text-xs">
                      <p className="text-tinta-2">{e.estado === "activa" ? "Elección activa" : "Próxima elección"}</p>
                      <p className="pb-2 text-sm font-bold">{e.nombre}</p>
                      <dl className="grid grid-cols-[1fr_auto] gap-y-1">
                        <dt className="text-tinta-2">{e.estado === "activa" ? "Cierre" : "Inicio"}</dt>
                        <dd className="font-semibold">{e.estado === "activa" ? soloHora(e.fecha_fin) : fechaHora(e.fecha_inicio)}</dd>
                        <dt className="text-tinta-2">Candidatos</dt><dd className="font-semibold">{e.num_candidatos}</dd>
                        <dt className="text-tinta-2">Cifrado</dt><dd className="font-semibold">ECC activo</dd>
                      </dl>
                    </div>
                  </div>
                ) : <p className="pt-3 text-sm text-tinta-2">No hay elecciones activas ni programadas.</p>}
              </section>

              <section className="tarjeta p-4 shadow-none">
                <h2 className="text-sm font-bold">Estado del sistema</h2>
                <ul className="flex flex-col gap-2.5 pt-3">
                  {datos.sistema.map((s) => (
                    <li key={s.nombre} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-2 text-tinta-2">
                        <span className={`size-2 rounded-full ${!s.ok ? "bg-peligro" : s.alerta ? "bg-alerta" : "bg-exito"}`} />
                        {s.nombre}
                      </span>
                      <span className={`font-semibold ${!s.ok ? "text-peligro" : s.alerta ? "text-alerta-texto" : "text-exito"}`}>{s.valor}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            <section className="tarjeta p-4 shadow-none">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold">Actividad reciente</h2>
                <Link to="/admin/auditoria" className="text-xs font-semibold text-primary hover:underline">Ver auditoría →</Link>
              </div>
              <ul className="pt-3">
                {datos.actividad.map((a) => (
                  <li key={a.id} className="flex gap-2 border-b-[1.5px] border-fondo py-1.5 last:border-0">
                    <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${a.resultado === "exito" ? "bg-exito" : "bg-peligro"}`} />
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium">{a.descripcion ?? a.accion}</p>
                      <p className="text-xs text-tinta-2">{a.actor} · {soloHora(a.fecha)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            {gestor && (
              <div className="grid grid-cols-2 gap-3 lg:max-w-md">
                <button onClick={() => navegar("/admin/votaciones?nueva=1")}
                  className="flex flex-col items-center gap-1 rounded-xl bg-primary p-3 text-xs font-bold text-white hover:bg-primary-dark">
                  <CalendarPlus className="size-5" /> Nueva votación
                </button>
                <button onClick={cerrarVotacion} disabled={e?.estado !== "activa" || cerrando}
                  className="flex flex-col items-center gap-1 rounded-xl border-[1.5px] border-linea bg-white p-3 text-xs font-bold text-peligro hover:bg-peligro-bg disabled:opacity-50">
                  <CircleX className="size-5" /> {cerrando ? "Cerrando…" : "Cerrar votación"}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
