// Política de Tratamiento de Datos Personales (Decreto 1377 de 2013, art. 13). El texto viene del backend
// (servicios/politica.py), que es su única fuente, con versión y huella SHA-256.
import { AlertCircle, Printer, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api";
import { Alerta, Cargando, ConNegrilla, GovHeader, Pantalla } from "../../componentes/ui";

type Seccion = {
  id: string; titulo: string; texto?: string; lista?: string[];
  tabla?: { columnas: string[]; filas: string[][] };
};
type Politica = {
  version: string; vigente_desde: string; titulo: string; subtitulo: string; hash: string;
  resumen: string[]; secciones: Seccion[];
};

function Parrafos({ texto }: { texto: string }) {
  // Un bloque cuyas líneas empiezan por "- " es una lista.
  return <>{texto.split("\n\n").map((p) => p.startsWith("- ") ? (
    <ul key={p} className="flex list-disc flex-col gap-1.5 pl-5 text-tinta-2">
      {p.split("\n").map((l) => <li key={l}><ConNegrilla texto={l.slice(2)} /></li>)}
    </ul>
  ) : <p key={p} className="text-tinta-2"><ConNegrilla texto={p} /></p>)}</>;
}

function Contenido({ s }: { s: Seccion }) {
  // Un texto que termina en ":" introduce la lista; si no, la complementa y va después.
  const antes = s.texto && (!s.lista || s.texto.endsWith(":"));
  return (
    <>
      {antes && <Parrafos texto={s.texto!} />}
      {s.lista && (
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-tinta-2">
          {s.lista.map((l) => <li key={l}><ConNegrilla texto={l} /></li>)}
        </ul>
      )}
      {s.texto && !antes && <Parrafos texto={s.texto} />}
      {s.tabla && (
        <div className="flex flex-col gap-3">
          {s.tabla.filas.map((fila) => (
            <dl key={fila[0]} className="grid gap-2 rounded-xl border-[1.5px] border-linea bg-sutil-2 p-4 text-sm md:grid-cols-[1fr_1.4fr_1.4fr] md:gap-4">
              {fila.map((celda, i) => (
                <div key={i}>
                  <dt className={`text-xs font-semibold uppercase tracking-wide text-tinta-2 ${i === 0 ? "md:sr-only" : ""}`}>
                    {s.tabla!.columnas[i]}
                  </dt>
                  <dd className={i === 0 ? "font-bold" : "text-tinta-2"}><ConNegrilla texto={celda} /></dd>
                </div>
              ))}
            </dl>
          ))}
        </div>
      )}
    </>
  );
}

export function Privacidad() {
  const navegar = useNavigate();
  const [politica, setPolitica] = useState<Politica>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    api<Politica>("/api/publico/politica").then(setPolitica)
      .catch((e) => setError(e instanceof Error ? e.message : "No fue posible cargar la política"));
  }, []);

  const vigencia = politica && new Date(`${politica.vigente_desde}T12:00:00`)
    .toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });

  return (
    <Pantalla>
      <GovHeader titulo="Política de privacidad" subtitulo="Tratamiento de datos personales" onVolver={() => navegar("/")} />
      <main className="contenido flex flex-col gap-5 p-5 pb-10 leading-relaxed md:p-8">
        {error && <Alerta tipo="error" titulo="No se pudo cargar" icono={<AlertCircle className="size-5" />}>{error}</Alerta>}
        {!politica && !error && <Cargando texto="Cargando la política…" />}
        {politica && (
          <>
            <section className="tarjeta flex flex-col gap-4 p-5 md:p-8">
              <div className="flex items-start gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-info-bg text-primary">
                  <ShieldCheck className="size-5" />
                </span>
                <div className="flex-1">
                  <h1 className="text-xl font-bold md:text-2xl">{politica.titulo}</h1>
                  <p className="text-sm text-tinta-2">{politica.subtitulo}</p>
                  <p className="text-xs text-tinta-2">Versión {politica.version} · Vigente desde el {vigencia}</p>
                </div>
                <button onClick={() => window.print()} aria-label="Imprimir o guardar en PDF"
                  className="rounded-lg p-2 text-primary transition hover:bg-info-bg print:hidden">
                  <Printer className="size-5" />
                </button>
              </div>
              <div className="rounded-xl bg-info-bg p-4">
                <h2 className="mb-2 font-bold">En resumen</h2>
                <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
                  {politica.resumen.map((r) => <li key={r}><ConNegrilla texto={r} /></li>)}
                </ul>
              </div>
            </section>

            <div className="grid gap-5 lg:grid-cols-[16rem_1fr] lg:items-start">
              <nav aria-label="Contenido" className="tarjeta p-5 text-sm lg:sticky lg:top-4 print:hidden">
                <h2 className="mb-2 font-bold">Contenido</h2>
                <ol className="flex flex-col gap-1">
                  {politica.secciones.map((s) => (
                    <li key={s.id}><a href={`#${s.id}`} className="text-primary hover:underline">{s.titulo}</a></li>
                  ))}
                </ol>
              </nav>
              <div className="flex min-w-0 flex-col gap-5">
                {politica.secciones.map((s) => (
                  <section key={s.id} id={s.id} className="tarjeta flex scroll-mt-4 flex-col gap-3 p-5 md:p-8">
                    <h2 className="text-lg font-bold">{s.titulo}</h2>
                    <Contenido s={s} />
                  </section>
                ))}
                <p className="break-all text-xs text-tinta-2">Huella SHA-256 de esta versión: {politica.hash}</p>
              </div>
            </div>
          </>
        )}
      </main>
    </Pantalla>
  );
}
