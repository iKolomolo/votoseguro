// Gráficos de participación y resultados (SVG sin dependencias).
import { miles, type CandidatoResultado } from "../api";
import { Barra } from "./ui";

export function Anillo({ porcentaje, etiqueta, valor, tamano = 130, color = "var(--color-primary)" }: {
  porcentaje: number; etiqueta: string; valor: string; tamano?: number; color?: string;
}) {
  const r = 50;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 130 130" width={tamano} height={tamano} role="img" aria-label={`${valor} ${etiqueta}`}>
      <circle cx="65" cy="65" r={r} fill="none" stroke="var(--color-linea-suave)" strokeWidth="14" />
      <circle cx="65" cy="65" r={r} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round"
        strokeDasharray={`${(c * Math.min(porcentaje, 100)) / 100} ${c}`} transform="rotate(-90 65 65)" />
      <text x="65" y="66" textAnchor="middle" className="fill-tinta text-[20px] font-bold">{valor}</text>
      <text x="65" y="82" textAnchor="middle" className="fill-tinta-2 text-[10px]">{etiqueta}</text>
    </svg>
  );
}

export function Dona({ candidatos, total }: { candidatos: CandidatoResultado[]; total: number }) {
  const r = 70;
  const c = 2 * Math.PI * r;
  let acumulado = 0;
  return (
    <div className="flex flex-col items-center gap-5">
      <svg viewBox="0 0 200 200" width="200" height="200" role="img"
        aria-label={`Distribución de ${miles(total)} votos`}>
        <circle cx="100" cy="100" r={r} fill="none" stroke="var(--color-sutil)" strokeWidth="26" />
        {total > 0 && candidatos.map((cand) => {
          const largo = (c * cand.votos) / total;
          const segmento = (
            <circle key={cand.id_candidato} cx="100" cy="100" r={r} fill="none" stroke={cand.color} strokeWidth="26"
              strokeDasharray={`${largo} ${c - largo}`} strokeDashoffset={-acumulado} transform="rotate(-90 100 100)" />
          );
          acumulado += largo;
          return segmento;
        })}
        <circle cx="100" cy="100" r="52" fill="white" />
        <text x="100" y="100" textAnchor="middle" className="fill-tinta text-[24px] font-black">{miles(total)}</text>
        <text x="100" y="118" textAnchor="middle" className="fill-tinta-2 text-[10px]">votos totales</text>
      </svg>
      <ul className="grid w-full grid-cols-2 gap-x-4 gap-y-2">
        {candidatos.map((cand) => (
          <li key={cand.id_candidato} className="flex items-center gap-2 text-[11px]">
            <span className="size-3 rounded" style={{ backgroundColor: cand.color }} />
            <span className="flex-1 truncate">#{String(cand.numero).padStart(2, "0")} {cand.nombre.split(" ")[0]}</span>
            <span className="font-bold">{cand.porcentaje}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BarrasCandidatos({ candidatos }: { candidatos: CandidatoResultado[] }) {
  const maximo = Math.max(...candidatos.map((c) => c.porcentaje), 1);
  return (
    <ul className="flex flex-col gap-4">
      {candidatos.map((c) => (
        <li key={c.id_candidato} className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 text-sm">
            <span className="size-2.5 rounded-full" style={{ backgroundColor: c.color }} />
            <span className="flex-1 font-semibold">{c.nombre.split(" ").slice(0, 2).join(" ")}</span>
            <span className="font-bold">{miles(c.votos)}</span>
            <span className="w-12 text-right text-xs text-tinta-2">{c.porcentaje}%</span>
          </div>
          <Barra porcentaje={(100 * c.porcentaje) / maximo} color={c.color} alto="h-4" />
        </li>
      ))}
    </ul>
  );
}
