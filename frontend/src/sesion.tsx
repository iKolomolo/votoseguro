// Estado de sesión del votante y del administrador. Se guarda en sessionStorage: se borra al cerrar la pestaña.
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import type { Candidato, Comprobante, Eleccion, Usuario } from "./api";

function leer<T>(clave: string, inicial: T): T {
  try {
    const valor = sessionStorage.getItem(clave);
    return valor ? (JSON.parse(valor) as T) : inicial;
  } catch {
    return inicial;
  }
}

function guardar(clave: string, valor: unknown) {
  try {
    if (valor === null) sessionStorage.removeItem(clave);
    else sessionStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    // sessionStorage puede no estar disponible (modo privado); la sesión sigue en memoria.
  }
}

export interface FlujoVotante {
  tokenFlujo?: string;
  tokenVotante?: string;
  nombre?: string;
  eleccion?: Eleccion;
  candidato?: Candidato;
  comprobante?: Comprobante;
}

interface CtxVotante {
  flujo: FlujoVotante;
  actualizar: (cambios: Partial<FlujoVotante>) => void;
  reiniciar: () => void;
}

const ContextoVotante = createContext<CtxVotante | null>(null);

export function ProveedorVotante({ children }: { children: ReactNode }) {
  const [flujo, setFlujo] = useState<FlujoVotante>(() => leer("vs-votante", {}));
  const actualizar = useCallback((cambios: Partial<FlujoVotante>) => {
    setFlujo((prev) => {
      const nuevo = { ...prev, ...cambios };
      guardar("vs-votante", nuevo);
      return nuevo;
    });
  }, []);
  const reiniciar = useCallback(() => {
    guardar("vs-votante", null);
    setFlujo({});
  }, []);
  return <ContextoVotante.Provider value={{ flujo, actualizar, reiniciar }}>{children}</ContextoVotante.Provider>;
}

export function useVotante() {
  const ctx = useContext(ContextoVotante);
  if (!ctx) throw new Error("useVotante fuera de ProveedorVotante");
  return ctx;
}

interface SesionAdmin {
  token: string;
  usuario: Usuario;
}

interface CtxAdmin {
  sesion: SesionAdmin | null;
  iniciar: (s: SesionAdmin) => void;
  cerrar: () => void;
}

const ContextoAdmin = createContext<CtxAdmin | null>(null);

export function ProveedorAdmin({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<SesionAdmin | null>(() => leer("vs-admin", null));
  const iniciar = useCallback((s: SesionAdmin) => {
    guardar("vs-admin", s);
    setSesion(s);
  }, []);
  const cerrar = useCallback(() => {
    guardar("vs-admin", null);
    setSesion(null);
  }, []);
  return <ContextoAdmin.Provider value={{ sesion, iniciar, cerrar }}>{children}</ContextoAdmin.Provider>;
}

export function useAdmin() {
  const ctx = useContext(ContextoAdmin);
  if (!ctx) throw new Error("useAdmin fuera de ProveedorAdmin");
  return ctx;
}
