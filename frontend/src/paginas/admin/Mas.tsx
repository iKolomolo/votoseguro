// Sección "Más": cuenta, auditoría, respaldos, cuentas del equipo, historial, votantes y supervisión.
import {
  Activity, ArchiveRestore, ChevronLeft, ClipboardList, DatabaseBackup, FolderClock, ShieldCheck, ShieldX, UserCog,
  Users,
} from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { fechaHora, miles, type EstadoServicio, type RegistroAuditoria, type Usuario } from "../../api";
import { Modal } from "../../componentes/Modal";
import { Alerta, Boton, Campo, Cargando } from "../../componentes/ui";
import { useAdmin } from "../../sesion";
import { AdminHeader, puede, useApiAdmin, useDatos } from "./Layout";

function Subpagina({ titulo, subtitulo, children }: { titulo: string; subtitulo?: string; children: ReactNode }) {
  const navegar = useNavigate();
  return (
    <>
      <AdminHeader titulo={titulo} subtitulo={subtitulo} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <button onClick={() => navegar("/admin/mas")} className="flex items-center gap-1 self-start text-sm font-semibold text-primary">
          <ChevronLeft className="size-4" /> Volver
        </button>
        {children}
      </main>
    </>
  );
}

const OPCIONES = [
  { a: "/admin/auditoria", t: "Auditoría", d: "Log de acciones del sistema", i: ClipboardList, f: "bg-info-bg-2 text-primary" },
  { a: "/admin/respaldos", t: "Respaldo y recuperación", d: "Copias de seguridad y rollback", i: DatabaseBackup, f: "bg-exito-bg text-exito" },
  { a: "/admin/cuentas", t: "Cuentas y permisos", d: "Gestión del equipo electoral", i: UserCog, f: "bg-alerta-bg text-alerta-texto", s: true },
  { a: "/admin/historial", t: "Historial", d: "Elecciones pasadas y resultados", i: FolderClock, f: "bg-sutil text-tinta-2" },
  { a: "/admin/votantes", t: "Votantes", d: "Censo y habilitación", i: Users, f: "bg-info-bg text-primary" },
  { a: "/admin/monitoreo", t: "Supervisión", d: "Rendimiento y errores", i: Activity, f: "bg-peligro-bg text-peligro" },
];

export function Mas() {
  const { sesion, cerrar } = useAdmin();
  const navegar = useNavigate();
  const [cuenta, setCuenta] = useState(false);
  const u = sesion!.usuario;
  return (
    <>
      <AdminHeader titulo="Más opciones" subtitulo="Herramientas del administrador" />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <section className="tarjeta p-4 shadow-none">
          <div className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-xl bg-primary font-black text-white">{u.nombre[0]}</span>
            <div><p className="font-bold">{u.nombre}</p><p className="text-sm text-tinta-2">{u.rol} · {u.correo}</p></div>
          </div>
          <div className="grid grid-cols-2 gap-3 pt-4">
            <Boton variante="secundario" onClick={() => setCuenta(true)}>Mi cuenta</Boton>
            <Boton variante="peligro" onClick={() => { cerrar(); navegar("/admin"); }}>Cerrar sesión</Boton>
          </div>
        </section>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {OPCIONES.filter((o) => !o.s || puede(u, "superadmin")).map(({ a, t, d, i: Icono, f }) => (
            <Link key={a} to={a} className="tarjeta flex flex-col gap-2 p-4 shadow-none transition hover:border-primary">
              <span className={`flex size-10 items-center justify-center rounded-lg ${f}`}><Icono className="size-5" /></span>
              <span className="pt-2 font-bold">{t}</span>
              <span className="text-xs text-tinta-2">{d}</span>
            </Link>
          ))}
        </div>
        <section className="tarjeta p-4 shadow-none">
          <h2 className="pb-2 text-xs font-bold tracking-[0.3px] text-tinta-2 uppercase">Info del sistema</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm [&_dd]:text-right">
            <dt className="text-tinta-2">Versión</dt><dd className="font-semibold">VotoSeguro v1.0.0 (prototipo)</dd>
            <dt className="text-tinta-2">Cifrado</dt><dd className="font-semibold">ECC P-256 (NIST) · ECIES · ECDSA</dd>
            <dt className="text-tinta-2">Biometría</dt><dd className="font-semibold">face-api · plantilla cancelable</dd>
            <dt className="text-tinta-2">Proyecto</dt><dd className="font-semibold">Universidad Manuela Beltrán</dd>
          </dl>
        </section>
      </main>
      <Modal titulo="Mi cuenta" abierto={cuenta} onCerrar={() => setCuenta(false)}>
        <CambiarPassword onListo={() => setCuenta(false)} />
      </Modal>
    </>
  );
}

function CambiarPassword({ onListo }: { onListo: () => void }) {
  const llamar = useApiAdmin();
  const [datos, setDatos] = useState({ actual: "", nueva: "", repetir: "" });
  const [error, setError] = useState<string>();
  const [ok, setOk] = useState(false);
  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (datos.nueva !== datos.repetir) return setError("Las contraseñas no coinciden");
    try {
      await llamar("/api/admin/yo/password", { cuerpo: { actual: datos.actual, nueva: datos.nueva } });
      setOk(true);
      setTimeout(onListo, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    }
  }
  const set = (k: keyof typeof datos) => (e: { target: { value: string } }) => setDatos((d) => ({ ...d, [k]: e.target.value }));
  return (
    <form onSubmit={guardar} className="flex flex-col gap-4">
      <Campo etiqueta="Contraseña actual" id="p1"><input id="p1" type="password" required className="entrada" autoComplete="current-password" onChange={set("actual")} /></Campo>
      <Campo etiqueta="Nueva contraseña (mín. 10 caracteres)" id="p2"><input id="p2" type="password" required minLength={10} className="entrada" autoComplete="new-password" onChange={set("nueva")} /></Campo>
      <Campo etiqueta="Repita la nueva contraseña" id="p3"><input id="p3" type="password" required minLength={10} className="entrada" autoComplete="new-password" onChange={set("repetir")} /></Campo>
      {error && <Alerta tipo="error">{error}</Alerta>}
      {ok && <Alerta tipo="exito">Contraseña actualizada</Alerta>}
      <Boton type="submit" className="h-12 text-base">Cambiar contraseña</Boton>
    </form>
  );
}

export function Auditoria() {
  const [accion, setAccion] = useState("");
  const { datos, error } = useDatos<RegistroAuditoria[]>(`/api/admin/auditoria?limite=200${accion ? `&accion=${accion}` : ""}`);
  const { datos: cadena, recargar } = useDatos<{ integra: boolean; registros: number; roto_en: number | null }>("/api/admin/auditoria/verificar");
  const acciones = ["LOGIN", "CREAR_ELECCION", "CERRAR_ELECCION", "AGREGAR_CANDIDATO", "EMITIR_VOTO", "VERIFICAR_BIOMETRIA",
    "BIOMETRIA_DUPLICADA", "CREAR_RESPALDO", "RESTAURAR_RESPALDO", "GENERAR_REPORTE"];
  return (
    <Subpagina titulo="Auditoría" subtitulo="Registro encadenado con SHA-256">
      {cadena && (
        <Alerta tipo={cadena.integra ? "exito" : "error"}
          icono={cadena.integra ? <ShieldCheck className="size-5" /> : <ShieldX className="size-5" />}
          titulo={cadena.integra ? "Cadena íntegra" : "¡Cadena alterada!"}>
          {cadena.integra ? `Los ${miles(cadena.registros)} registros conservan su encadenamiento de hashes.`
            : `El registro #${cadena.roto_en} fue modificado o eliminado.`}
          <button onClick={recargar} className="ml-2 font-semibold underline">Verificar de nuevo</button>
        </Alerta>
      )}
      <select aria-label="Filtrar por acción" className="entrada h-11 text-sm lg:max-w-xl" value={accion} onChange={(e) => setAccion(e.target.value)}>
        <option value="">Todas las acciones</option>
        {acciones.map((a) => <option key={a}>{a}</option>)}
      </select>
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!datos && <Cargando />}
      <ul className="tarjeta divide-y-[1.5px] divide-fondo px-4 shadow-none">
        {datos?.map((a) => (
          <li key={a.id} className="py-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-bold text-primary">{a.accion}</span>
              <span className={`text-[10px] font-bold uppercase ${a.resultado === "exito" ? "text-exito" : "text-peligro"}`}>{a.resultado}</span>
            </div>
            {a.descripcion && <p className="text-sm">{a.descripcion}</p>}
            <p className="text-xs text-tinta-2">{a.actor} · {fechaHora(a.fecha)}{a.ip ? ` · ${a.ip}` : ""}</p>
            <p className="truncate font-mono text-[10px] text-apagado" title={a.hash}>#{a.id} {a.hash}</p>
          </li>
        ))}
      </ul>
    </Subpagina>
  );
}

interface RespaldoInfo { id_respaldo: number; archivo: string; fecha: string; tamano: number; hash: string; automatico: boolean; creado_por: string; valido: boolean }

export function Respaldos() {
  const { sesion } = useAdmin();
  const llamar = useApiAdmin();
  const { datos, error, recargar } = useDatos<RespaldoInfo[]>("/api/admin/respaldos");
  const [trabajando, setTrabajando] = useState(false);
  const [mensaje, setMensaje] = useState<string>();

  async function crear() {
    setTrabajando(true);
    try { await llamar("/api/admin/respaldos", { metodo: "POST" }); setMensaje("Respaldo creado y firmado"); recargar(); }
    catch (e) { alert(e instanceof Error ? e.message : "Error"); }
    finally { setTrabajando(false); }
  }
  async function restaurar(r: RespaldoInfo) {
    if (!confirm(`¿Restaurar el sistema al ${fechaHora(r.fecha)}? Se perderán los cambios posteriores (incluidos votos).`)) return;
    setTrabajando(true);
    try { await llamar(`/api/admin/respaldos/${r.id_respaldo}/restaurar`, { metodo: "POST" }); setMensaje("Sistema restaurado"); recargar(); }
    catch (e) { alert(e instanceof Error ? e.message : "Error"); }
    finally { setTrabajando(false); }
  }

  return (
    <Subpagina titulo="Respaldo y recuperación" subtitulo="Copias cifradas con ECIES y firmadas con ECDSA">
      {puede(sesion?.usuario, "gestionar") && (
        <Boton className="h-12 text-base sm:self-start sm:px-6" onClick={crear} cargando={trabajando}><DatabaseBackup className="size-5" /> Crear respaldo ahora</Boton>
      )}
      {mensaje && <Alerta tipo="exito">{mensaje}</Alerta>}
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!datos && <Cargando />}
      {datos?.map((r) => (
        <article key={r.id_respaldo} className="tarjeta flex flex-wrap items-center gap-3 p-4 shadow-none">
          <div className="min-w-48 flex-1">
            <p className="font-semibold">{fechaHora(r.fecha)} <span className="text-xs font-normal text-tinta-2">{r.automatico ? "automático" : `por ${r.creado_por}`}</span></p>
            <p className="text-xs text-tinta-2">{(r.tamano / 1024).toFixed(1)} KB · <span className={r.valido ? "text-exito" : "text-peligro"}>{r.valido ? "Firma válida" : "Firma inválida o archivo faltante"}</span></p>
            <p className="truncate font-mono text-[10px] text-apagado">{r.hash}</p>
          </div>
          {puede(sesion?.usuario, "superadmin") && (
            <Boton variante="neutro" disabled={!r.valido || trabajando} onClick={() => restaurar(r)}>
              <ArchiveRestore className="size-4" /> Restaurar
            </Boton>
          )}
        </article>
      ))}
    </Subpagina>
  );
}

export function Cuentas() {
  const llamar = useApiAdmin();
  const { sesion } = useAdmin();
  const { datos, error, recargar } = useDatos<Usuario[]>("/api/admin/usuarios");
  const { datos: roles } = useDatos<{ nombre: string; descripcion: string }[]>("/api/admin/roles");
  const [nuevo, setNuevo] = useState(false);
  const [err, setErr] = useState<string>();

  async function crear(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    try { await llamar("/api/admin/usuarios", { cuerpo: f }); setNuevo(false); recargar(); }
    catch (x) { setErr(x instanceof Error ? x.message : "Error"); }
  }
  async function editar(u: Usuario, cambios: Record<string, string>) {
    try { await llamar(`/api/admin/usuarios/${u.id_usuario}`, { metodo: "PATCH", cuerpo: cambios }); recargar(); }
    catch (x) { alert(x instanceof Error ? x.message : "Error"); }
  }

  return (
    <Subpagina titulo="Cuentas y permisos" subtitulo="Equipo electoral">
      <Boton className="h-12 text-base sm:self-start sm:px-6" onClick={() => { setErr(undefined); setNuevo(true); }}><UserCog className="size-5" /> Nueva cuenta</Boton>
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!datos && <Cargando />}
      {datos?.map((u) => (
        <article key={u.id_usuario} className="tarjeta flex flex-col gap-3 p-4 shadow-none sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <p className="font-bold">{u.nombre}</p>
            <p className="truncate text-xs text-tinta-2">{u.correo}</p>
            <p className="text-xs text-tinta-2">Último acceso: {u.ultimo_acceso ? fechaHora(u.ultimo_acceso) : "nunca"}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select aria-label="Rol" className="entrada h-10 w-auto text-sm" value={u.rol} disabled={u.id_usuario === sesion?.usuario.id_usuario}
              onChange={(e) => editar(u, { rol: e.target.value })}>
              {roles?.map((r) => <option key={r.nombre}>{r.nombre}</option>)}
            </select>
            <select aria-label="Estado" className="entrada h-10 w-auto text-sm" value={u.estado} disabled={u.id_usuario === sesion?.usuario.id_usuario}
              onChange={(e) => editar(u, { estado: e.target.value })}>
              {["activo", "inactivo", "bloqueado"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
        </article>
      ))}
      <Modal titulo="Nueva cuenta" abierto={nuevo} onCerrar={() => setNuevo(false)}>
        <form onSubmit={crear} className="flex flex-col gap-4">
          <Campo etiqueta="Nombre" id="u-nombre"><input id="u-nombre" name="nombre" required minLength={3} className="entrada" /></Campo>
          <Campo etiqueta="Correo institucional" id="u-correo"><input id="u-correo" name="correo" type="email" required className="entrada" /></Campo>
          <Campo etiqueta="Rol" id="u-rol">
            <select id="u-rol" name="rol" className="entrada">{roles?.map((r) => <option key={r.nombre}>{r.nombre}</option>)}</select>
          </Campo>
          <Campo etiqueta="Contraseña inicial (mín. 10)" id="u-pass"><input id="u-pass" name="password" type="password" required minLength={10} className="entrada" autoComplete="new-password" /></Campo>
          {err && <Alerta tipo="error">{err}</Alerta>}
          <Boton type="submit" className="h-12 text-base">Crear cuenta</Boton>
        </form>
      </Modal>
    </Subpagina>
  );
}

interface ItemHistorial { id_eleccion: number; codigo: string; nombre: string; fecha_fin: string; archivada: boolean;
  total_votos: number; participacion_pct: number; integridad_ok: boolean | null; ganador: { nombre: string; votos: number } | null }

export function Historial() {
  const { datos, error } = useDatos<ItemHistorial[]>("/api/admin/historial");
  return (
    <Subpagina titulo="Historial" subtitulo="Elecciones cerradas">
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!datos && <Cargando />}
      {datos?.length === 0 && <p className="text-center text-sm text-tinta-2">Aún no hay elecciones cerradas.</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {datos?.map((e) => (
          <Link key={e.id_eleccion} to={`/admin/resultados?eleccion=${e.id_eleccion}`} className="tarjeta block p-4 shadow-none hover:border-primary">
            <p className="font-mono text-xs text-tinta-2">{e.codigo}{e.archivada ? " · archivada" : ""}</p>
            <p className="font-bold">{e.nombre}</p>
            <p className="text-xs text-tinta-2">Cerró {fechaHora(e.fecha_fin)} · {miles(e.total_votos)} votos · {e.participacion_pct}% participación</p>
            {e.ganador && <p className="pt-1 text-sm">Ganador: <b>{e.ganador.nombre}</b> ({miles(e.ganador.votos)})</p>}
          </Link>
        ))}
      </div>
    </Subpagina>
  );
}

interface VotanteInfo {
  id_votante: number; nombre: string; documento: string; estado: string; biometria: boolean; cedula: boolean;
  fecha_registro: string | null;
}

export function Votantes() {
  const { sesion } = useAdmin();
  const llamar = useApiAdmin();
  const { datos, error, recargar } = useDatos<VotanteInfo[]>("/api/admin/votantes");
  const [filtro, setFiltro] = useState("");
  const gestor = puede(sesion?.usuario, "gestionar");
  const superadmin = puede(sesion?.usuario, "superadmin");
  const [cedula, setCedula] = useState<{ nombre: string; url: string }>();

  async function cambiar(v: VotanteInfo, estado: string) {
    try { await llamar(`/api/admin/votantes/${v.id_votante}`, { metodo: "PATCH", cuerpo: { estado } }); recargar(); }
    catch (e) { alert(e instanceof Error ? e.message : "Error"); }
  }
  async function revocar(v: VotanteInfo) {
    if (!confirm(`¿Revocar la plantilla biométrica de ${v.nombre}? Deberá registrar su rostro de nuevo.`)) return;
    try { await llamar(`/api/admin/votantes/${v.id_votante}/revocar-biometria`, { metodo: "POST" }); recargar(); }
    catch (e) { alert(e instanceof Error ? e.message : "Error"); }
  }
  async function verCedula(v: VotanteInfo) {
    try {
      const imagen = await llamar<Blob>(`/api/admin/votantes/${v.id_votante}/cedula`);
      setCedula({ nombre: v.nombre, url: URL.createObjectURL(imagen) });
    } catch (e) { alert(e instanceof Error ? e.message : "Error"); }
  }
  function cerrarCedula() {
    if (cedula) URL.revokeObjectURL(cedula.url);
    setCedula(undefined);
  }
  const lista = datos?.filter((v) => (v.nombre + v.documento).toLowerCase().includes(filtro.toLowerCase()));

  return (
    <Subpagina titulo="Votantes" subtitulo={datos ? `${miles(datos.length)} registrados` : undefined}>
      <input aria-label="Buscar" placeholder="Buscar por nombre o últimos dígitos" className="entrada h-11 text-sm lg:max-w-xl"
        value={filtro} onChange={(e) => setFiltro(e.target.value)} />
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!datos && <Cargando texto="Descifrando datos…" />}
      {lista?.slice(0, 100).map((v) => (
        <article key={v.id_votante} className="tarjeta flex flex-col gap-2 p-4 shadow-none sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <p className="font-bold">{v.nombre}</p>
            <p className="font-mono text-xs text-tinta-2">{v.documento}</p>
            <p className="text-xs text-tinta-2">
              Biometría: {v.biometria ? "registrada" : "pendiente"} · Cédula: {v.cedula ? "registrada" : "pendiente"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select aria-label="Estado de habilitación" disabled={!gestor} className="entrada h-10 w-auto text-sm" value={v.estado}
              onChange={(e) => cambiar(v, e.target.value)}>
              {["habilitado", "no_habilitado", "sancionado", "bloqueado"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
            {superadmin && v.cedula && <Boton variante="secundario" onClick={() => verCedula(v)}>Ver cédula</Boton>}
            {gestor && v.biometria && <Boton variante="neutro" onClick={() => revocar(v)}>Revocar biometría</Boton>}
          </div>
        </article>
      ))}
      <Modal titulo={`Cédula de ${cedula?.nombre ?? ""}`} abierto={!!cedula} onCerrar={cerrarCedula}>
        {cedula && <img src={cedula.url} alt={`Cédula de ${cedula.nombre}`} className="w-full rounded-lg" />}
        <p className="pt-3 text-xs text-tinta-2">Esta consulta quedó registrada en la auditoría.</p>
      </Modal>
    </Subpagina>
  );
}

interface Monitor { segundos_activo: number; latencia_db_ms: number | null; disponibilidad: number | null; votantes_activos: number;
  total_errores: number; errores_recientes: { fecha: string; mensaje: string }[]; sistema: EstadoServicio[] }

export function Monitoreo() {
  const { datos, error, recargar } = useDatos<Monitor>("/api/admin/monitor");
  useEffect(() => {
    const id = setInterval(recargar, 10000);
    return () => clearInterval(id);
  }, [recargar]);
  const horas = datos ? `${Math.floor(datos.segundos_activo / 3600)} h ${Math.floor((datos.segundos_activo % 3600) / 60)} min` : "";
  return (
    <Subpagina titulo="Supervisión" subtitulo="Se actualiza cada 10 segundos">
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!datos && <Cargando />}
      {datos && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[["Tiempo activo", horas], ["Disponibilidad", datos.disponibilidad === null ? "—" : `${datos.disponibilidad}%`],
              ["Latencia BD", datos.latencia_db_ms === null ? "—" : `${datos.latencia_db_ms} ms`], ["Errores", String(datos.total_errores)]]
              .map(([t, v]) => (
                <div key={t} className="rounded-xl border-[1.5px] border-linea bg-white p-3">
                  <p className="text-xs font-semibold text-tinta-2 uppercase">{t}</p><p className="text-xl font-black">{v}</p>
                </div>
              ))}
          </div>
          <section className="tarjeta p-4 shadow-none">
            <h2 className="pb-2 text-sm font-bold">Servicios</h2>
            {datos.sistema.map((s) => (
              <p key={s.nombre} className="flex justify-between py-1 text-sm">
                <span>{s.nombre}</span><span className={s.ok ? "font-semibold text-exito" : "font-semibold text-peligro"}>{s.valor}</span>
              </p>
            ))}
          </section>
          <section className="tarjeta p-4 shadow-none">
            <h2 className="pb-2 text-sm font-bold">Errores recientes</h2>
            {datos.errores_recientes.length === 0 ? <p className="text-sm text-tinta-2">Sin errores registrados.</p> :
              datos.errores_recientes.map((e, i) => (
                <p key={i} className="border-b border-fondo py-1 font-mono text-xs"><span className="text-tinta-2">{fechaHora(e.fecha)}</span> {e.mensaje}</p>
              ))}
          </section>
        </>
      )}
    </Subpagina>
  );
}
