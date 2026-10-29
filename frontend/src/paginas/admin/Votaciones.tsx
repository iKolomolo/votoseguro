import { KeyRound, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { fechaHora, miles, type Candidato, type Eleccion } from "../../api";
import { Modal } from "../../componentes/Modal";
import { Alerta, AvatarCandidato, Barra, Boton, Campo, Cargando, InsigniaEstado, NumeroCandidato } from "../../componentes/ui";
import { useAdmin } from "../../sesion";
import { AdminHeader, puede, useApiAdmin, useDatos } from "./Layout";

const TIPOS = ["Municipal", "Distrital", "Departamental", "Nacional", "Consulta", "Institucional"];

/** Convierte una fecha ISO al formato de <input type="datetime-local"> en la hora del navegador. */
function aLocal(iso: string) {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function FormularioEleccion({ inicial, onGuardado }: { inicial?: Eleccion; onGuardado: () => void }) {
  const llamar = useApiAdmin();
  const manana = new Date(Date.now() + 86400000);
  manana.setHours(8, 0, 0, 0);
  const [datos, setDatos] = useState({
    nombre: inicial?.nombre ?? "", descripcion: inicial?.descripcion ?? "", tipo: inicial?.tipo ?? "Municipal",
    fecha_inicio: inicial ? aLocal(inicial.fecha_inicio) : aLocal(manana.toISOString()),
    fecha_fin: inicial ? aLocal(inicial.fecha_fin) : aLocal(new Date(manana.getTime() + 8 * 3600000).toISOString()),
  });
  const [error, setError] = useState<string>();
  const [guardando, setGuardando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(undefined);
    try {
      const cuerpo = { ...datos, descripcion: datos.descripcion || null,
        fecha_inicio: new Date(datos.fecha_inicio).toISOString(), fecha_fin: new Date(datos.fecha_fin).toISOString() };
      await llamar(inicial ? `/api/admin/elecciones/${inicial.id_eleccion}` : "/api/admin/elecciones",
        { metodo: inicial ? "PUT" : "POST", cuerpo });
      onGuardado();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setGuardando(false);
    }
  }

  const set = (k: keyof typeof datos) => (e: { target: { value: string } }) => setDatos((d) => ({ ...d, [k]: e.target.value }));
  return (
    <form onSubmit={guardar} className="flex flex-col gap-4">
      <Campo etiqueta="Nombre del proceso" id="nombre">
        <input id="nombre" className="entrada" required minLength={5} maxLength={120} value={datos.nombre} onChange={set("nombre")} />
      </Campo>
      <Campo etiqueta="Tipo" id="tipo">
        <select id="tipo" className="entrada" value={datos.tipo} onChange={set("tipo")}>
          {TIPOS.map((t) => <option key={t}>{t}</option>)}
        </select>
      </Campo>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Inicio" id="inicio">
          <input id="inicio" type="datetime-local" className="entrada" required value={datos.fecha_inicio} onChange={set("fecha_inicio")} />
        </Campo>
        <Campo etiqueta="Cierre" id="fin">
          <input id="fin" type="datetime-local" className="entrada" required min={datos.fecha_inicio} value={datos.fecha_fin} onChange={set("fecha_fin")} />
        </Campo>
      </div>
      <Campo etiqueta="Descripción (opcional)" id="desc">
        <textarea id="desc" rows={3} className="entrada h-auto py-3" value={datos.descripcion} onChange={set("descripcion")} />
      </Campo>
      {!inicial && (
        <p className="flex items-start gap-2 text-xs text-tinta-2">
          <KeyRound className="mt-0.5 size-4 shrink-0" />
          Al crear la votación se genera su propio par de llaves ECC P-256. Los votos se cifran con la llave pública y
          solo se descifran en el escrutinio, después del cierre.
        </p>
      )}
      {error && <Alerta tipo="error">{error}</Alerta>}
      <Boton type="submit" cargando={guardando} className="h-12 text-base">{inicial ? "Guardar cambios" : "Crear votación"}</Boton>
    </form>
  );
}

export function Votaciones() {
  const { sesion } = useAdmin();
  const llamar = useApiAdmin();
  const [params, setParams] = useSearchParams();
  const [archivadas, setArchivadas] = useState(false);
  const { datos, error, recargar } = useDatos<Eleccion[]>(`/api/admin/elecciones?incluir_archivadas=${archivadas}`);
  const [editando, setEditando] = useState<Eleccion>();
  const [detalle, setDetalle] = useState<Eleccion & { candidatos: Candidato[] }>();
  const creando = params.get("nueva") === "1";
  const gestor = puede(sesion?.usuario, "gestionar");

  async function accion(ruta: string, confirmacion: string) {
    if (!confirm(confirmacion)) return;
    try {
      await llamar(ruta, { metodo: "POST" });
      recargar();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    }
  }

  async function verDetalle(e: Eleccion) {
    setDetalle(await llamar(`/api/admin/elecciones/${e.id_eleccion}`));
  }

  return (
    <>
      <AdminHeader titulo="Votaciones" subtitulo="Gestión de procesos electorales" />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        {gestor && (
          <button onClick={() => setParams({ nueva: "1" })}
            className="flex h-14 items-center justify-center gap-2 rounded-xl bg-primary text-lg font-bold text-white hover:bg-primary-dark sm:self-start sm:px-8">
            <Plus className="size-6" /> Crear nueva votación
          </button>
        )}
        <label className="flex items-center gap-2 self-end text-xs text-tinta-2">
          <input type="checkbox" checked={archivadas} onChange={(e) => setArchivadas(e.target.checked)} /> Mostrar archivadas
        </label>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {!datos && !error && <Cargando />}
        {datos?.length === 0 && <p className="text-center text-sm text-tinta-2">Aún no hay votaciones.</p>}
        <div className="grid gap-4 lg:grid-cols-2">
          {datos?.map((e) => {
            const pct = e.habilitados ? (100 * e.participacion) / e.habilitados : 0;
            return (
              <article key={e.id_eleccion} className="tarjeta flex flex-col gap-2 p-4">
                <div className="flex items-center gap-2">
                  <InsigniaEstado estado={e.estado} />
                  <span className="font-mono text-xs text-tinta-2">{e.codigo}</span>
                  {e.archivada && <span className="text-xs text-apagado">(archivada)</span>}
                </div>
                <h2 className="font-bold">{e.nombre}</h2>
                <p className="text-xs text-tinta-2">Inicio: {fechaHora(e.fecha_inicio)}<br />Cierre: {fechaHora(e.fecha_fin)}</p>
                {e.estado !== "programada" && (
                  <div className="flex flex-col gap-1 pt-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-tinta-2">Participación</span>
                      <span className="font-bold">{miles(e.participacion)} / {miles(e.habilitados)} ({pct.toFixed(0)}%)</span>
                    </div>
                    <Barra porcentaje={pct} />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2 pt-2">
                  {gestor && e.estado === "activa" && (
                    <Boton variante="peligro" onClick={() => accion(`/api/admin/elecciones/${e.id_eleccion}/cerrar`,
                      `¿Cerrar "${e.nombre}"? Se hará el escrutinio y no se aceptarán más votos.`)}>Cerrar votación</Boton>
                  )}
                  {gestor && e.estado === "programada" && <Boton variante="neutro" onClick={() => setEditando(e)}>Editar</Boton>}
                  {gestor && e.estado === "finalizada" && (
                    <Boton variante="neutro" onClick={() => accion(
                      `/api/admin/elecciones/${e.id_eleccion}/archivar?archivar=${!e.archivada}`,
                      e.archivada ? "¿Restaurar al historial?" : "¿Archivar? Se ocultará del historial pero no se borrará.")}>
                      {e.archivada ? "Desarchivar" : "Archivar"}
                    </Boton>
                  )}
                  <Boton variante="secundario" onClick={() => verDetalle(e)}
                    className={!gestor ? "col-span-2" : ""}>Ver detalles</Boton>
                </div>
              </article>
            );
          })}
        </div>
      </main>

      <Modal titulo="Nueva votación" abierto={creando} onCerrar={() => setParams({})}>
        <FormularioEleccion onGuardado={() => { setParams({}); recargar(); }} />
      </Modal>
      <Modal titulo="Editar votación" abierto={!!editando} onCerrar={() => setEditando(undefined)}>
        <FormularioEleccion inicial={editando} onGuardado={() => { setEditando(undefined); recargar(); }} />
      </Modal>
      <Modal titulo={detalle?.codigo ?? ""} abierto={!!detalle} onCerrar={() => setDetalle(undefined)}>
        {detalle && (
          <div className="flex flex-col gap-3 text-sm">
            <InsigniaEstado estado={detalle.estado} />
            <h3 className="text-lg font-bold">{detalle.nombre}</h3>
            {detalle.descripcion && <p className="text-tinta-2">{detalle.descripcion}</p>}
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="text-tinta-2">Tipo</dt><dd>{detalle.tipo}</dd>
              <dt className="text-tinta-2">Inicio</dt><dd>{fechaHora(detalle.fecha_inicio)}</dd>
              <dt className="text-tinta-2">Cierre</dt><dd>{fechaHora(detalle.fecha_fin)}</dd>
              <dt className="text-tinta-2">Votos</dt><dd>{miles(detalle.participacion)}</dd>
              {detalle.integridad_ok !== null && (<>
                <dt className="text-tinta-2">Integridad</dt>
                <dd className={detalle.integridad_ok ? "text-exito" : "text-peligro"}>{detalle.integridad_ok ? "Verificada" : "Con alertas"}</dd>
              </>)}
            </dl>
            <h4 className="pt-2 font-bold">Candidatos ({detalle.candidatos.length})</h4>
            <ul className="flex flex-col gap-2">
              {detalle.candidatos.map((c) => (
                <li key={c.id_candidato} className="flex items-center gap-3">
                  <AvatarCandidato candidato={c} tamano="size-10" />
                  <NumeroCandidato numero={c.numero} />
                  <span className="font-semibold">{c.nombre}</span>
                </li>
              ))}
            </ul>
            <div className="flex gap-2 pt-2">
              <Link to={`/admin/candidatos?eleccion=${detalle.id_eleccion}`} className="text-sm font-bold text-primary hover:underline">Gestionar candidatos →</Link>
              {detalle.estado === "finalizada" && (
                <Link to={`/admin/resultados?eleccion=${detalle.id_eleccion}`} className="ml-auto text-sm font-bold text-primary hover:underline">Resultados →</Link>
              )}
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
