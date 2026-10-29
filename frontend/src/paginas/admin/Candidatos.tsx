import { Plus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { urlApi, type Candidato, type Eleccion } from "../../api";
import { Modal } from "../../componentes/Modal";
import { Alerta, AvatarCandidato, Boton, Campo, Cargando, NumeroCandidato } from "../../componentes/ui";
import { useAdmin } from "../../sesion";
import { AdminHeader, puede, useApiAdmin, useDatos } from "./Layout";

/** Selector de elección guardado en ?eleccion=. Por defecto elige la activa, o la más reciente. */
export function useEleccionSeleccionada(filtro?: (e: Eleccion) => boolean) {
  const [params, setParams] = useSearchParams();
  const { datos: elecciones } = useDatos<Eleccion[]>("/api/admin/elecciones?incluir_archivadas=true");
  const lista = elecciones?.filter(filtro ?? (() => true));
  const id = Number(params.get("eleccion")) || undefined;
  const actual = lista?.find((e) => e.id_eleccion === id)
    ?? lista?.find((e) => e.estado === "activa") ?? lista?.[0];
  useEffect(() => {
    if (actual && actual.id_eleccion !== id) setParams({ eleccion: String(actual.id_eleccion) }, { replace: true });
  }, [actual, id, setParams]);
  const selector = lista && lista.length > 0 && (
    <select aria-label="Votación" className="entrada h-11 text-sm lg:max-w-xl" value={actual?.id_eleccion}
      onChange={(e) => setParams({ eleccion: e.target.value })}>
      {lista.map((e) => <option key={e.id_eleccion} value={e.id_eleccion}>{e.codigo} · {e.nombre}</option>)}
    </select>
  );
  return { eleccion: actual, cargado: !!elecciones, selector };
}

function FormularioCandidato({ idEleccion, inicial, onGuardado }: { idEleccion: number; inicial?: Candidato; onGuardado: () => void }) {
  const llamar = useApiAdmin();
  const [error, setError] = useState<string>();
  const [guardando, setGuardando] = useState(false);
  const [vista, setVista] = useState<string | null>(inicial?.imagen_url ? urlApi(inicial.imagen_url) : null);

  async function guardar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formulario = new FormData(e.currentTarget);
    if (!(formulario.get("imagen") as File)?.size) formulario.delete("imagen");
    if (!formulario.get("numero")) formulario.delete("numero");
    setGuardando(true);
    setError(undefined);
    try {
      await llamar(inicial ? `/api/admin/candidatos/${inicial.id_candidato}` : `/api/admin/elecciones/${idEleccion}/candidatos`,
        { metodo: inicial ? "PUT" : "POST", formulario });
      onGuardado();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={guardar} className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        {vista ? <img src={vista} alt="" className="size-20 rounded-xl object-cover" />
          : <div className="flex size-20 items-center justify-center rounded-xl bg-sutil text-xs text-apagado">Sin foto</div>}
        <label className="text-sm font-semibold text-primary">
          <span className="cursor-pointer underline">Subir fotografía</span>
          <input type="file" name="imagen" accept="image/jpeg,image/png,image/webp" className="sr-only"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) setVista(URL.createObjectURL(f)); }} />
          <span className="block text-xs font-normal text-tinta-2">JPG, PNG o WEBP · máx. 2 MB</span>
        </label>
      </div>
      <Campo etiqueta="Nombre completo" id="c-nombre">
        <input id="c-nombre" name="nombre" className="entrada" required minLength={2} defaultValue={inicial?.nombre} />
      </Campo>
      <Campo etiqueta="Partido o movimiento" id="c-partido">
        <input id="c-partido" name="partido" className="entrada" required minLength={2} defaultValue={inicial?.partido} />
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        {!inicial && (
          <Campo etiqueta="Número (opcional)" id="c-numero">
            <input id="c-numero" name="numero" type="number" min={1} max={99} className="entrada" placeholder="Auto" />
          </Campo>
        )}
        <Campo etiqueta="Color en gráficas" id="c-color">
          <input id="c-color" name="color" type="color" className="entrada p-1" defaultValue={inicial?.color ?? "#003da5"} />
        </Campo>
      </div>
      <Campo etiqueta="Descripción / propuestas" id="c-desc">
        <textarea id="c-desc" name="descripcion" rows={3} className="entrada h-auto py-3" defaultValue={inicial?.descripcion ?? ""} />
      </Campo>
      {error && <Alerta tipo="error">{error}</Alerta>}
      <Boton type="submit" cargando={guardando} className="h-12 text-base">{inicial ? "Guardar cambios" : "Agregar candidato"}</Boton>
    </form>
  );
}

export function CandidatosAdmin() {
  const { sesion } = useAdmin();
  const llamar = useApiAdmin();
  const { eleccion, cargado, selector } = useEleccionSeleccionada();
  const { datos, error, recargar } = useDatos<Candidato[]>(eleccion ? `/api/admin/elecciones/${eleccion.id_eleccion}/candidatos` : null);
  const [formulario, setFormulario] = useState<{ inicial?: Candidato } | null>(null);
  const editable = puede(sesion?.usuario, "gestionar") && eleccion?.estado === "programada";

  async function quitar(c: Candidato) {
    if (!eleccion || !confirm(`¿Quitar a ${c.nombre} de esta votación?`)) return;
    try {
      await llamar(`/api/admin/elecciones/${eleccion.id_eleccion}/candidatos/${c.id_candidato}`, { metodo: "DELETE" });
      recargar();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    }
  }

  return (
    <>
      <AdminHeader titulo="Candidatos" subtitulo={eleccion?.nombre} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        {selector}
        {cargado && !eleccion && <p className="text-center text-sm text-tinta-2">Cree primero una votación.</p>}
        {eleccion && !editable && (
          <Alerta tipo="info">
            {eleccion.estado === "programada" ? "Su rol solo permite consultar." :
              "Los candidatos no se pueden modificar porque la votación ya inició o terminó."}
          </Alerta>
        )}
        {editable && (
          <button onClick={() => setFormulario({})}
            className="flex h-14 items-center justify-center gap-2 rounded-xl bg-primary text-lg font-bold text-white hover:bg-primary-dark sm:self-start sm:px-8">
            <Plus className="size-6" /> Agregar candidato
          </button>
        )}
        {error && <Alerta tipo="error">{error}</Alerta>}
        {eleccion && !datos && !error && <Cargando />}
        {datos?.length === 0 && <p className="text-center text-sm text-tinta-2">Sin candidatos inscritos.</p>}
        <div className="grid gap-4 lg:grid-cols-2">
          {datos?.map((c) => (
            <article key={c.id_candidato} className="tarjeta flex items-center gap-4 p-4">
              <AvatarCandidato candidato={c} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <NumeroCandidato numero={c.numero} />
                  <span className="size-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                </div>
                <p className="pt-1 font-bold">{c.nombre}</p>
                <p className="text-xs text-tinta-2">{c.partido}</p>
              </div>
              {editable && (
                <div className="flex flex-col gap-2">
                  <Boton variante="secundario" onClick={() => setFormulario({ inicial: c })}>Editar</Boton>
                  <Boton variante="peligro" onClick={() => quitar(c)}>Quitar</Boton>
                </div>
              )}
            </article>
          ))}
        </div>
      </main>
      <Modal titulo={formulario?.inicial ? "Editar candidato" : "Agregar candidato"} abierto={!!formulario}
        onCerrar={() => setFormulario(null)}>
        {eleccion && formulario && (
          <FormularioCandidato idEleccion={eleccion.id_eleccion} inicial={formulario.inicial}
            onGuardado={() => { setFormulario(null); recargar(); }} />
        )}
      </Modal>
    </>
  );
}
