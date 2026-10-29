// Cliente HTTP para la API de VotoSeguro.

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string) {
    super(mensaje);
  }
}

// Dirección del backend. Vacía cuando la API se sirve en el mismo dominio (Docker); en Vercel apunta a Render.
const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

/** Convierte una ruta de la API ("/api/...") en una URL completa hacia el backend. */
export const urlApi = (ruta: string) => API_URL + ruta;

type Opciones = { token?: string | null; metodo?: string; cuerpo?: unknown; formulario?: FormData };

function mensajeDeError(datos: unknown, estado: number): string {
  const detalle = (datos as { detail?: unknown })?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle) && detalle[0]?.msg) {
    // Errores de validación de FastAPI/Pydantic
    return detalle.map((d: { msg: string }) => d.msg.replace(/^Value error, /, "")).join(". ");
  }
  if (estado === 0) return "No hay conexión con el servidor";
  return "Ocurrió un error inesperado";
}

export async function api<T = unknown>(ruta: string, { token, metodo, cuerpo, formulario }: Opciones = {}): Promise<T> {
  const cabeceras: Record<string, string> = {};
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  let respuesta: Response;
  try {
    respuesta = await fetch(urlApi(ruta), {
      method: metodo ?? (cuerpo !== undefined || formulario ? "POST" : "GET"),
      headers: cabeceras,
      body: formulario ?? (cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined),
    });
  } catch {
    throw new ErrorApi(0, "No hay conexión con el servidor");
  }
  const tipo = respuesta.headers.get("content-type") ?? "";
  const datos = tipo.includes("application/json") ? await respuesta.json() : await respuesta.blob();
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, mensajeDeError(datos, respuesta.status));
  return datos as T;
}

export async function descargar(ruta: string, token: string, nombre: string) {
  const blob = await api<Blob>(ruta, { token });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------- Tipos ----------

export type EstadoEleccion = "programada" | "activa" | "finalizada";

export interface Eleccion {
  id_eleccion: number;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  tipo: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado: EstadoEleccion;
  archivada: boolean;
  fecha_cierre: string | null;
  participacion: number;
  habilitados: number;
  num_candidatos: number;
  integridad_ok: boolean | null;
  ya_voto?: boolean;
}

export interface Candidato {
  id_candidato: number;
  numero: number | null;
  nombre: string;
  partido: string;
  descripcion: string | null;
  color: string;
  imagen_url: string | null;
}

export interface CandidatoResultado extends Candidato {
  votos: number;
  porcentaje: number;
}

export interface Resultados {
  eleccion: Eleccion;
  candidatos: CandidatoResultado[];
  total_votos: number;
  habilitados: number;
  votaron: number;
  participacion: number;
  abstencion: number;
  ventaja: { votos: number; porcentaje: number };
  integridad_ok: boolean | null;
}

export interface Comprobante {
  codigo: string;
  hash_voto: string;
  eleccion: string;
  fecha: string;
}

export interface Usuario {
  id_usuario: number;
  correo: string;
  nombre: string;
  rol: "Superadministrador" | "Administrador" | "Supervisor";
  estado: string;
  ultimo_acceso: string | null;
}

export interface RegistroAuditoria {
  id: number;
  accion: string;
  descripcion: string | null;
  actor: string;
  fecha: string;
  resultado: string;
  ip: string | null;
  hash: string;
}

export interface EstadoServicio {
  nombre: string;
  ok: boolean;
  valor: string;
  alerta?: boolean;
}

// ---------- Formato ----------

const ZONA = "America/Bogota";

export function fechaHora(iso: string) {
  return new Intl.DateTimeFormat("es-CO", {
    timeZone: ZONA, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

export function soloFecha(iso: string) {
  return new Intl.DateTimeFormat("es-CO", { timeZone: ZONA, day: "2-digit", month: "2-digit", year: "numeric" })
    .format(new Date(iso));
}

export function soloHora(iso: string) {
  return new Intl.DateTimeFormat("es-CO", { timeZone: ZONA, hour: "2-digit", minute: "2-digit", hour12: false })
    .format(new Date(iso));
}

export const miles = (n: number) => n.toLocaleString("es-CO");
