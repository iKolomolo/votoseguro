import { CalendarDays, Ellipsis, LayoutGrid, Lock, LogIn, BarChart3, Users } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useNavigate } from "react-router";
import { api, ErrorApi, type Usuario } from "../../api";
import { Alerta } from "../../componentes/ui";
import { useAdmin } from "../../sesion";

/** Llama a la API con el token del administrador y cierra la sesión si expiró. */
export function useApiAdmin() {
  const { sesion, cerrar } = useAdmin();
  const navegar = useNavigate();
  return useCallback(async <T,>(ruta: string, opciones: Parameters<typeof api>[1] = {}) => {
    try {
      return await api<T>(ruta, { ...opciones, token: sesion?.token });
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) {
        cerrar();
        navegar("/admin");
      }
      throw e;
    }
  }, [sesion?.token, cerrar, navegar]);
}

/** Carga datos al montar y permite recargarlos. */
export function useDatos<T>(ruta: string | null) {
  const llamar = useApiAdmin();
  const [datos, setDatos] = useState<T>();
  const [error, setError] = useState<string>();
  const recargar = useCallback(() => {
    if (!ruta) return;
    llamar<T>(ruta).then((d) => { setDatos(d); setError(undefined); })
      .catch((e) => setError(e instanceof Error ? e.message : "Error"));
  }, [ruta, llamar]);
  useEffect(recargar, [recargar]);
  return { datos, error, recargar, setDatos };
}

export function puede(usuario: Usuario | undefined, accion: "gestionar" | "superadmin") {
  if (!usuario) return false;
  if (accion === "superadmin") return usuario.rol === "Superadministrador";
  return usuario.rol !== "Supervisor";
}

export function AdminHeader({ titulo, subtitulo, accion }: { titulo: string; subtitulo?: string; accion?: ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-3 bg-primary px-4 pt-10 pb-4 text-white md:px-6 lg:pt-6">
      <div>
        <p className="text-[10px] leading-[15px] font-black tracking-[1px] text-info-borde uppercase">VotoSeguro · Admin</p>
        <h1 className="pt-0.5 text-lg leading-[22.5px] font-bold">{titulo}</h1>
        {subtitulo && <p className="pt-0.5 text-xs text-info-borde">{subtitulo}</p>}
      </div>
      {accion}
    </header>
  );
}

const NAV = [
  { a: "/admin/dashboard", t: "Dashboard", i: LayoutGrid },
  { a: "/admin/votaciones", t: "Votaciones", i: CalendarDays },
  { a: "/admin/candidatos", t: "Candidatos", i: Users },
  { a: "/admin/resultados", t: "Resultados", i: BarChart3 },
  { a: "/admin/mas", t: "Más", i: Ellipsis },
];

export function AdminLayout() {
  const { sesion } = useAdmin();
  if (!sesion) return <Navigate to="/admin" replace />;
  // Celular y tablet: barra de navegación inferior. Escritorio (lg): barra lateral fija.
  return (
    <div className="min-h-dvh bg-fondo-admin lg:flex">
      <nav aria-label="Navegación del panel"
        className="fixed inset-x-0 bottom-0 z-10 flex border-t-[1.5px] border-linea bg-white lg:sticky lg:top-0 lg:h-dvh lg:w-60 lg:shrink-0 lg:flex-col lg:gap-1 lg:border-t-0 lg:border-r-[1.5px] lg:p-3">
        <div className="hidden items-center gap-2.5 px-2 pt-3 pb-6 lg:flex">
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary"><Lock className="size-4 text-white" /></span>
          <div>
            <p className="leading-5 font-black text-primary">VotoSeguro</p>
            <p className="text-xs text-tinta-2">Panel de administración</p>
          </div>
        </div>
        {NAV.map(({ a, t, i: Icono }) => (
          <NavLink key={a} to={a}
            className={({ isActive }) => `relative flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[9px] leading-[13.5px] font-bold tracking-[0.225px] uppercase lg:flex-none lg:flex-row lg:gap-3 lg:rounded-lg lg:px-3 lg:text-sm lg:tracking-normal lg:normal-case ${
              isActive ? "text-primary lg:bg-info-bg" : "text-apagado hover:text-tinta-2 lg:text-tinta-2 lg:hover:bg-sutil"}`}>
            {({ isActive }) => (
              <>
                {isActive && <span className="absolute top-0 h-0.5 w-full rounded-b bg-primary lg:hidden" />}
                <Icono className="size-5" />{t}
              </>
            )}
          </NavLink>
        ))}
        <div className="mt-auto hidden border-t-[1.5px] border-linea px-2 pt-3 lg:block">
          <p className="truncate text-sm font-bold">{sesion.usuario.nombre}</p>
          <p className="truncate text-xs text-tinta-2">{sesion.usuario.rol}</p>
        </div>
      </nav>
      <div className="mx-auto flex w-full max-w-3xl min-w-0 flex-col pb-24 lg:max-w-none lg:pb-6">
        <Outlet />
      </div>
    </div>
  );
}

export function LoginAdmin() {
  const { sesion, iniciar } = useAdmin();
  const navegar = useNavigate();
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [cargando, setCargando] = useState(false);
  if (sesion) return <Navigate to="/admin/dashboard" replace />;

  async function entrar(e: FormEvent) {
    e.preventDefault();
    setCargando(true);
    setError(undefined);
    try {
      const r = await api<{ token: string; usuario: Usuario }>("/api/admin/login", { cuerpo: { correo, password } });
      iniciar(r);
      navegar("/admin/dashboard");
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No fue posible iniciar sesión");
    } finally {
      setCargando(false);
    }
  }

  const campo = "h-12 w-full rounded-xl border-[1.5px] border-white/20 bg-white/15 px-4 text-sm font-medium text-white placeholder:text-sobre-primario-2 outline-none focus:border-white/60";
  return (
    <div className="min-h-dvh bg-primary-dark text-white">
      <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-6">
        <main className="flex flex-1 flex-col items-center justify-center gap-8 py-10">
          <div className="flex flex-col items-center gap-2 text-center">
            <div className="mb-2 flex size-16 items-center justify-center rounded-2xl bg-white"><Lock className="size-7 fill-primary text-primary" /></div>
            <h1 className="text-3xl leading-9 font-black">VotoSeguro</h1>
            <p className="font-semibold text-sobre-primario-2">Panel de Administración</p>
            <p className="mt-2 rounded-full bg-white/10 px-3 py-1 text-xs text-sobre-primario">Acceso restringido — Solo personal autorizado</p>
          </div>
          <form onSubmit={entrar} className="flex w-full flex-col gap-4 rounded-2xl border-[1.5px] border-white/20 bg-white/10 p-5 backdrop-blur-lg">
            <label className="flex flex-col gap-2 text-xs font-bold tracking-[0.6px] uppercase">Correo institucional
              <input type="email" required autoComplete="username" className={campo} placeholder="usuario@votoseguro.gov.co"
                value={correo} onChange={(e) => setCorreo(e.target.value)} />
            </label>
            <label className="flex flex-col gap-2 text-xs font-bold tracking-[0.6px] uppercase">Contraseña
              <input type="password" required autoComplete="current-password" className={campo} placeholder="••••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && <Alerta tipo="error">{error}</Alerta>}
            <button disabled={cargando}
              className="flex h-13 items-center justify-center gap-2 rounded-xl bg-exito font-bold transition hover:bg-exito-fuerte disabled:opacity-60">
              <LogIn className="size-5" /> {cargando ? "Ingresando…" : "Ingresar al panel"}
            </button>
          </form>
          <p className="flex items-center gap-1.5 text-xs text-sobre-primario-2"><Lock className="size-3" /> Cifrado ECC P-256 · Sesión auditada</p>
        </main>
        <Link to="/" className="pb-12 text-center text-sm font-semibold text-sobre-primario-2 hover:underline">← Volver a la app del votante</Link>
      </div>
    </div>
  );
}
