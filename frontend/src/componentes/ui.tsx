// Componentes base que replican el diseño de Figma (GovHeader, ProgressSteps, BigButton, LockBadge...).
import { Check, ChevronLeft, Loader2, Lock } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { urlApi, type Candidato, type EstadoEleccion } from "../api";

/**
 * Pantalla del votante: ocupa toda la ventana en cualquier tamaño. Encabezado y fondo van de lado a lado y el
 * contenido se centra con la utilidad `contenido` (72rem, o 48rem si es `estrecha` para pantallas de un solo foco).
 */
export function Pantalla({ children, className = "", estrecha = false }: {
  children: ReactNode; className?: string; estrecha?: boolean;
}) {
  const fondo = /\bbg-/.test(className) ? "" : "bg-fondo";
  const ancho = estrecha ? "[--ancho-contenido:48rem]" : "";
  return (
    <div className={`flex min-h-dvh w-full flex-col ${ancho} ${fondo} ${className}`}>
      {children}
    </div>
  );
}

export function GovHeader({ titulo, subtitulo, onVolver, antetitulo = "VotoSeguro Colombia", color = "bg-primary" }: {
  titulo: string; subtitulo?: string; onVolver?: () => void; antetitulo?: string; color?: string;
}) {
  return (
    <header className={`${color} pt-10 pb-6 text-white md:pt-7 lg:pt-8 lg:pb-8`}>
      <div className="contenido flex items-center gap-3 px-5 md:px-8">
        {onVolver && (
          <button onClick={onVolver} aria-label="Volver"
            className="rounded-lg bg-white/15 p-2 transition hover:bg-white/25">
            <ChevronLeft className="size-5" />
          </button>
        )}
        <div>
          <p className="text-xs font-semibold tracking-[1.2px] text-info-borde uppercase">{antetitulo}</p>
          <h1 className="text-xl leading-[25px] font-bold lg:text-3xl lg:leading-10">{titulo}</h1>
          {subtitulo && <p className="pt-0.5 text-sm text-sobre-primario lg:text-base">{subtitulo}</p>}
        </div>
      </div>
    </header>
  );
}

const PASOS_VOTANTE = ["Identificación", "Rostro", "Elegibilidad", "Votación"];

/** Barra de pasos. `paso` mayor que la cantidad de pasos los marca todos como completados. */
export function ProgressSteps({ paso, pasos = PASOS_VOTANTE }: { paso: number; pasos?: string[] }) {
  return (
    <nav aria-label="Progreso" className="border-b-[1.5px] border-linea bg-white py-3">
      <div className="contenido px-5 md:px-8">
        <ol className="flex items-center">
          {pasos.map((nombre, i) => {
            const n = i + 1;
            const hecho = n < paso;
            const actual = n === paso;
            return (
              <li key={nombre} className="flex flex-1 flex-col items-center gap-1" aria-current={actual ? "step" : undefined}>
                <span className={`flex size-8 items-center justify-center rounded-full text-sm font-bold ${
                  hecho ? "bg-exito text-white" : actual ? "bg-primary text-white" : "bg-linea text-tinta-2"}`}>
                  {hecho ? <Check className="size-3.5" strokeWidth={3} aria-label="Completado" /> : n}
                </span>
                <span className={`text-[10px] leading-[12.5px] font-semibold lg:text-xs ${hecho || actual ? "text-primary" : "text-tinta-2"}`}>
                  {nombre}
                </span>
              </li>
            );
          })}
        </ol>
        <div className="mt-2 h-1.5 rounded-full bg-linea">
          <div className="h-1.5 rounded-full bg-primary transition-all" style={{ width: `${Math.min((paso - 1) / (pasos.length - 1), 1) * 100}%` }} />
        </div>
      </div>
    </nav>
  );
}

export function LockBadge({ texto = "Conexión cifrada SSL/TLS" }: { texto?: string }) {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-full border-[1.5px] border-info-borde bg-info-bg px-3 py-1 text-xs text-primary">
      <Lock className="size-3" /> {texto}
    </span>
  );
}

export function EccBadge() {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-full border-[1.5px] border-exito-borde bg-exito-suave px-2.5 py-1 text-[11px] font-semibold text-exito">
      <Lock className="size-3" /> ECC P-256 activo
    </span>
  );
}

type Variante = "exito" | "primario" | "contorno" | "enlace" | "peligro";

const ESTILOS: Record<Variante, string> = {
  exito: "bg-exito text-white hover:bg-exito-fuerte",
  primario: "bg-primary text-white hover:bg-primary-dark",
  contorno: "border-[1.5px] border-primary bg-white text-primary hover:bg-info-bg",
  enlace: "text-primary underline hover:text-primary-dark",
  peligro: "border-[1.5px] border-peligro-borde bg-peligro-bg text-peligro hover:bg-peligro-bg-2",
};

export function BigButton({ variante = "exito", cargando, children, className = "", ...props }: {
  variante?: Variante; cargando?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button {...props} disabled={props.disabled || cargando}
      className={`flex min-h-[58px] w-full items-center justify-center gap-2 rounded-xl px-6 py-4 text-lg leading-7 font-bold transition disabled:cursor-not-allowed disabled:opacity-60 ${ESTILOS[variante]} ${className}`}>
      {cargando && <Loader2 className="size-5 animate-spin" />}
      {children}
    </button>
  );
}

export function Boton({ variante = "primario", cargando, children, className = "", ...props }: {
  variante?: "primario" | "secundario" | "peligro" | "neutro" | "exito"; cargando?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const estilos = {
    primario: "bg-primary text-white hover:bg-primary-dark",
    exito: "bg-exito text-white hover:bg-exito-fuerte",
    secundario: "border-[1.5px] border-info-borde bg-info-bg text-primary hover:bg-info-bg-2",
    peligro: "border-[1.5px] border-peligro-borde bg-peligro-bg text-peligro hover:bg-peligro-bg-2",
    neutro: "border-[1.5px] border-linea bg-sutil-2 text-tinta-2 hover:bg-sutil",
  }[variante];
  return (
    <button {...props} disabled={props.disabled || cargando}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-60 ${estilos} ${className}`}>
      {cargando && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Alerta({ tipo, titulo, children, icono }: {
  tipo: "exito" | "error" | "aviso" | "info"; titulo?: string; children?: ReactNode; icono?: ReactNode;
}) {
  const estilos = {
    exito: ["border-exito bg-exito-bg", "text-exito", "text-exito-fuerte"],
    error: ["border-peligro-borde bg-peligro-bg", "text-peligro", "text-peligro"],
    aviso: ["border-alerta-texto/30 bg-alerta-bg", "text-alerta-texto", "text-alerta-fuerte"],
    info: ["border-info-borde bg-info-bg", "text-primary", "text-tinta-2"],
  }[tipo];
  return (
    <div role={tipo === "error" ? "alert" : "status"} className={`flex gap-3 rounded-xl border-[1.5px] p-4 ${estilos[0]}`}>
      {icono && <div className={`pt-0.5 ${estilos[1]}`}>{icono}</div>}
      <div>
        {titulo && <p className={`font-bold ${estilos[1]}`}>{titulo}</p>}
        {children && <div className={`text-sm ${estilos[2]}`}>{children}</div>}
      </div>
    </div>
  );
}

export function Campo({ etiqueta, id, error, children }: { etiqueta: string; id: string; error?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-semibold text-tinta">{etiqueta}</label>
      {children}
      {error && <p className="text-xs text-peligro">{error}</p>}
    </div>
  );
}

const INSIGNIAS: Record<EstadoEleccion, [string, string]> = {
  activa: ["Activa", "border-exito/30 bg-exito-bg text-exito"],
  programada: ["Próxima", "border-alerta-texto/40 bg-alerta-bg text-alerta-texto"],
  finalizada: ["Cerrada", "border-linea-suave bg-sutil text-tinta-2"],
};

export function InsigniaEstado({ estado }: { estado: EstadoEleccion }) {
  const [texto, clases] = INSIGNIAS[estado];
  return (
    <span className={`rounded-full border-[1.5px] px-2.5 py-0.5 text-[10px] leading-[15px] font-bold tracking-[0.5px] uppercase ${clases}`}>
      {texto}
    </span>
  );
}

export function AvatarCandidato({ candidato, tamano = "size-16" }: { candidato: Candidato; tamano?: string }) {
  if (candidato.imagen_url) {
    return <img src={urlApi(candidato.imagen_url)} alt={`Foto de ${candidato.nombre}`} className={`${tamano} shrink-0 rounded-xl object-cover`} />;
  }
  const iniciales = candidato.nombre.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]).join("");
  return (
    <div aria-hidden className={`${tamano} flex shrink-0 items-center justify-center rounded-xl text-xl font-black text-white`}
      style={{ backgroundColor: candidato.color }}>
      {iniciales}
    </div>
  );
}

export function NumeroCandidato({ numero }: { numero: number | null }) {
  return (
    <span className="rounded-md bg-primary px-2 py-0.5 text-xs font-bold text-white">
      #{String(numero ?? 0).padStart(2, "0")}
    </span>
  );
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div role="status" className="flex flex-1 items-center justify-center gap-2 p-10 text-tinta-2">
      <Loader2 className="size-5 animate-spin" /> {texto}
    </div>
  );
}

export function Barra({ porcentaje, color = "var(--color-primary)", alto = "h-2" }: { porcentaje: number; color?: string; alto?: string }) {
  return (
    <div className={`${alto} w-full overflow-hidden rounded-full bg-sutil`} role="progressbar"
      aria-valuenow={Math.round(porcentaje)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`${alto} rounded-full transition-all`} style={{ width: `${Math.min(porcentaje, 100)}%`, backgroundColor: color }} />
    </div>
  );
}
