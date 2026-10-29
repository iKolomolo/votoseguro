// Foto de la cédula: se toma con la cámara (trasera en el celular) o se sube un archivo. En el navegador se
// reduce la imagen y se extrae el descriptor de la cara impresa con face-api, el mismo espacio de 128 valores
// del rostro en vivo; el número lo lee el servidor con OCR sobre esta misma imagen.
import { Camera, CameraOff, ImageUp, Loader2, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { cargarModelos } from "./CapturaFacial";

const LADO_MAXIMO = 1600;

export interface FotoCedula {
  blob: Blob;
  descriptor: number[];
}

/** Dibuja la fuente en un canvas de como máximo LADO_MAXIMO px por lado. */
function aCanvas(fuente: CanvasImageSource, ancho: number, alto: number) {
  const escala = Math.min(1, LADO_MAXIMO / Math.max(ancho, alto));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(ancho * escala);
  canvas.height = Math.round(alto * escala);
  canvas.getContext("2d")!.drawImage(fuente, 0, 0, canvas.width, canvas.height);
  return canvas;
}

async function procesar(canvas: HTMLCanvasElement): Promise<FotoCedula> {
  const faceapi = await cargarModelos();
  // La cara de la cédula ocupa poco de la foto: se busca con una entrada grande y luego una intermedia.
  let rostro;
  for (const inputSize of [608, 416]) {
    rostro = await faceapi.detectSingleFace(canvas, new faceapi.TinyFaceDetectorOptions({ inputSize, scoreThreshold: 0.3 }))
      .withFaceLandmarks().withFaceDescriptor();
    if (rostro) break;
  }
  if (!rostro) {
    throw new Error("No se encontró el rostro en la cédula. Tome la foto más cerca, de frente y sin reflejos.");
  }
  const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/jpeg", 0.92));
  if (!blob) throw new Error("No fue posible preparar la imagen");
  return { blob, descriptor: Array.from(rostro.descriptor) };
}

export function CapturaDocumento({ onCambio }: { onCambio: (foto: FotoCedula | null) => void }) {
  const [modo, setModo] = useState<"camara" | "archivo">("camara");
  const [vistaPrevia, setVistaPrevia] = useState<string>();
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState<string>();
  const [camaraLista, setCamaraLista] = useState(false);
  const video = useRef<HTMLVideoElement>(null);

  // La cámara solo está encendida mientras se encuadra (modo cámara y sin foto tomada).
  useEffect(() => {
    if (modo !== "camara" || vistaPrevia) return;
    let flujo: MediaStream | undefined;
    let activo = true;
    setCamaraLista(false);
    navigator.mediaDevices?.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    }).then(async (s) => {
      if (!activo) return s.getTracks().forEach((t) => t.stop());
      flujo = s;
      if (video.current) {
        video.current.srcObject = s;
        await video.current.play();
        setCamaraLista(true);
      }
    }).catch(() => activo && setError("No fue posible usar la cámara. Puede subir una foto de la cédula."));
    return () => {
      activo = false;
      flujo?.getTracks().forEach((t) => t.stop());
    };
  }, [modo, vistaPrevia]);

  useEffect(() => () => { if (vistaPrevia) URL.revokeObjectURL(vistaPrevia); }, [vistaPrevia]);

  async function usar(canvas: HTMLCanvasElement) {
    setError(undefined);
    setProcesando(true);
    try {
      const foto = await procesar(canvas);
      setVistaPrevia(URL.createObjectURL(foto.blob));
      onCambio(foto);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No fue posible procesar la imagen");
      onCambio(null);
    } finally {
      setProcesando(false);
    }
  }

  function tomarFoto() {
    const v = video.current;
    if (v) usar(aCanvas(v, v.videoWidth, v.videoHeight));
  }

  async function subir(e: ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    try {
      const imagen = await createImageBitmap(archivo, { imageOrientation: "from-image" });
      await usar(aCanvas(imagen, imagen.width, imagen.height));
    } catch {
      setError("El archivo no es una imagen válida");
    }
  }

  function repetir() {
    setVistaPrevia(undefined);
    setError(undefined);
    onCambio(null);
  }

  const pestana = (activa: boolean) => `flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-bold transition ${
    activa ? "bg-white text-primary shadow-sm" : "text-tinta-2 hover:text-tinta"}`;

  return (
    <div className="flex flex-col gap-4">
      {!vistaPrevia && (
        <div role="tablist" aria-label="Forma de capturar la cédula" className="flex gap-1 rounded-xl bg-sutil p-1">
          <button role="tab" aria-selected={modo === "camara"} className={pestana(modo === "camara")}
            onClick={() => { setModo("camara"); setError(undefined); }}>
            <Camera className="size-4" /> Cámara
          </button>
          <button role="tab" aria-selected={modo === "archivo"} className={pestana(modo === "archivo")}
            onClick={() => { setModo("archivo"); setError(undefined); }}>
            <ImageUp className="size-4" /> Subir foto
          </button>
        </div>
      )}

      <div className="relative flex aspect-[85.6/54] w-full items-center justify-center overflow-hidden rounded-xl bg-tinta">
        {vistaPrevia ? (
          <img src={vistaPrevia} alt="Foto de la cédula" className="size-full object-contain" />
        ) : modo === "camara" ? (
          <>
            <video ref={video} muted playsInline aria-label="Vista de la cámara" className="size-full object-cover" />
            {!camaraLista && !error && <Loader2 className="absolute size-8 animate-spin text-white/70" />}
            {error && !camaraLista && <CameraOff className="absolute size-10 text-white/60" />}
            {/* Guía con la proporción de la cédula (ID-1, 85,6 × 54 mm). */}
            <div aria-hidden className="pointer-events-none absolute inset-[6%] rounded-lg border-2 border-dashed border-white/80" />
          </>
        ) : (
          <label className="flex size-full cursor-pointer flex-col items-center justify-center gap-2 text-white/80 hover:text-white">
            <ImageUp className="size-10" />
            <span className="text-sm font-semibold">Seleccionar imagen de la cédula</span>
            <span className="text-xs text-white/60">JPG, PNG o WEBP</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={subir} />
          </label>
        )}
        {procesando && (
          <div role="status" className="absolute inset-0 flex items-center justify-center gap-2 bg-tinta/70 text-sm font-semibold text-white">
            <Loader2 className="size-5 animate-spin" /> Buscando el rostro en la cédula…
          </div>
        )}
      </div>

      {error && <p role="alert" className="text-center text-sm text-peligro">{error}</p>}

      {vistaPrevia ? (
        <button onClick={repetir} className="flex items-center justify-center gap-1.5 text-sm font-semibold text-primary underline">
          <RotateCcw className="size-4" /> Tomar otra foto
        </button>
      ) : modo === "camara" && (
        <button onClick={tomarFoto} disabled={!camaraLista || procesando}
          className="flex h-12 items-center justify-center gap-2 rounded-xl border-[1.5px] border-primary bg-white font-bold text-primary transition hover:bg-info-bg disabled:opacity-50">
          <Camera className="size-5" /> Tomar foto
        </button>
      )}
    </div>
  );
}
