import { FileSpreadsheet, FileText, History, Lock, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { descargar, miles, type Resultados } from "../../api";
import { BarrasCandidatos, Dona } from "../../componentes/Graficos";
import { Alerta, AvatarCandidato, Boton, Cargando, EccBadge } from "../../componentes/ui";
import { useAdmin } from "../../sesion";
import { useEleccionSeleccionada } from "./Candidatos";
import { AdminHeader, useDatos } from "./Layout";

export function ResultadosAdmin() {
  const { sesion } = useAdmin();
  const navegar = useNavigate();
  const { eleccion, cargado, selector } = useEleccionSeleccionada((e) => e.estado === "finalizada");
  const { datos, error } = useDatos<Resultados>(eleccion ? `/api/admin/elecciones/${eleccion.id_eleccion}/resultados` : null);
  const [descargando, setDescargando] = useState<string>();

  async function bajar(formato: "pdf" | "csv") {
    if (!eleccion || !sesion) return;
    setDescargando(formato);
    try {
      await descargar(`/api/admin/elecciones/${eleccion.id_eleccion}/reporte.${formato}`, sesion.token,
        `resultados-${eleccion.codigo}.${formato}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setDescargando(undefined);
    }
  }

  const ganador = datos?.candidatos[0];
  return (
    <>
      <AdminHeader titulo="Resultados" subtitulo={eleccion?.nombre} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <EccBadge />
        {selector}
        {cargado && !eleccion && (
          <Alerta tipo="info" icono={<Lock className="size-5" />} titulo="Aún no hay votaciones cerradas">
            Los votos permanecen cifrados con ECC hasta el cierre. Al cerrar una votación se hace el escrutinio.
          </Alerta>
        )}
        {error && <Alerta tipo="error">{error}</Alerta>}
        {eleccion && !datos && !error && <Cargando />}
        {datos && (
          <>
            {ganador && datos.total_votos > 0 && (
              <section className="rounded-2xl bg-primary p-5 text-white">
                <p className="text-xs font-semibold tracking-[0.6px] text-sobre-primario uppercase">Candidato con más votos</p>
                <div className="flex items-center gap-3 border-b border-white/20 pt-3 pb-4">
                  <AvatarCandidato candidato={ganador} />
                  <div>
                    <p className="text-lg font-bold">{ganador.nombre}</p>
                    <p className="text-sm text-sobre-primario">{ganador.partido}</p>
                    <p className="text-3xl font-black">{miles(ganador.votos)} <span className="text-base font-normal">votos</span></p>
                  </div>
                </div>
                <p className="pt-3 text-sm text-sobre-primario">
                  Ventaja sobre 2.° lugar: <b className="text-white">{miles(datos.ventaja.votos)} votos ({datos.ventaja.porcentaje}%)</b>
                </p>
              </section>
            )}
            <div className="grid grid-cols-3 gap-3">
              {[["Habilitados", miles(datos.habilitados)], ["Votaron", miles(datos.votaron)], ["Abstención", `${datos.abstencion}%`]].map(([t, v]) => (
                <div key={t} className="rounded-xl border-[1.5px] border-linea bg-white p-3 text-center">
                  <p className="text-lg font-black sm:text-xl">{v}</p><p className="text-xs text-tinta-2">{t}</p>
                </div>
              ))}
            </div>
            <Alerta tipo={datos.integridad_ok ? "exito" : "error"}
              icono={datos.integridad_ok ? <ShieldCheck className="size-5" /> : <ShieldAlert className="size-5" />}
              titulo={datos.integridad_ok ? "Integridad verificada" : "Alerta de integridad"}>
              {datos.integridad_ok
                ? `Los ${miles(datos.total_votos)} votos descifrados coinciden con las ${miles(datos.votaron)} participaciones registradas y todas las firmas ECDSA son válidas.`
                : "El número de votos válidos no coincide con las participaciones. Revise la auditoría."}
            </Alerta>
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="tarjeta p-5 shadow-none">
                <h2 className="pb-4 font-bold">Distribución de votos</h2>
                <Dona candidatos={datos.candidatos} total={datos.total_votos} />
              </section>
              <section className="tarjeta p-5 shadow-none">
                <h2 className="pb-4 font-bold">Comparación por candidato</h2>
                <BarrasCandidatos candidatos={datos.candidatos} />
              </section>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:max-w-xl">
              <Boton className="h-12" onClick={() => bajar("pdf")} cargando={descargando === "pdf"}><FileText className="size-4" /> PDF</Boton>
              <Boton variante="secundario" className="h-12" onClick={() => bajar("csv")} cargando={descargando === "csv"}>
                <FileSpreadsheet className="size-4" /> Excel</Boton>
              <Boton variante="neutro" className="h-12" onClick={() => navegar("/admin/historial")}><History className="size-4" /> Historial</Boton>
            </div>
          </>
        )}
      </main>
    </>
  );
}
