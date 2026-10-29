import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

/** Diálogo modal accesible basado en <dialog>. */
export function Modal({ titulo, abierto, onCerrar, children }: {
  titulo: string; abierto: boolean; onCerrar: () => void; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);
  return (
    <dialog ref={ref} onClose={onCerrar} aria-label={titulo}
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl p-0 backdrop:bg-tinta/50">
      <div className="flex items-center justify-between border-b-[1.5px] border-linea px-5 py-4">
        <h2 className="text-lg font-bold">{titulo}</h2>
        <button onClick={onCerrar} aria-label="Cerrar" className="rounded-lg p-1 text-tinta-2 hover:bg-sutil"><X className="size-5" /></button>
      </div>
      <div className="max-h-[75dvh] overflow-y-auto p-5">{abierto && children}</div>
    </dialog>
  );
}
