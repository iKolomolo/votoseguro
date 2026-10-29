// Captura del rostro con la cámara web y extracción del descriptor facial (face-api.js, 128 valores).
// Incluye una prueba de vida: el usuario cumple retos elegidos al azar (girar la cabeza, sonreír), lo que
// dificulta usar una foto impresa o un video grabado. No se usa el parpadeo: el modelo de 68 puntos de face-api
// casi no distingue el ojo cerrado y el reto fallaba con frecuencia.
import { Camera, CameraOff, Loader2, UserRound } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

type FaceApi = typeof import("@vladmandic/face-api");
type Punto = { x: number; y: number };

export type EstadoCaptura = "cargando" | "sin-camara" | "listo" | "capturando";

const MUESTRAS = 5;
const TIEMPO_ENCUADRE_MS = 10000;
const TIEMPO_RETO_MS = 8000;
const RETOS_POR_VERIFICACION = 2;
// Los umbrales son relativos a la referencia de cada persona mirando de frente, no valores absolutos.
const GIRO_MINIMO = 0.1; // desplazamiento de la nariz, como fracción del ancho de la cara
const FRONTAL_MAXIMO = 0.15;
const SONRISA_MINIMA = 0.7; // probabilidad de "happy" del modelo de expresiones
const BOCA_SONRISA = 1.12; // o boca un 12 % más ancha que en reposo
const MISMA_PERSONA = 0.5; // distancia euclidiana máxima entre el rostro inicial y el final

type Reto = "izquierda" | "derecha" | "sonreir";
const RETOS: Record<Reto, string> = {
  izquierda: "Gire la cabeza hacia su izquierda",
  derecha: "Gire la cabeza hacia su derecha",
  sonreir: "Sonría",
};

let modelos: Promise<FaceApi> | null = null;

export function cargarModelos(): Promise<FaceApi> {
  modelos ??= (async () => {
    const faceapi = await import("@vladmandic/face-api");
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri("/models"),
      faceapi.nets.faceLandmark68Net.loadFromUri("/models"),
      faceapi.nets.faceRecognitionNet.loadFromUri("/models"),
      faceapi.nets.faceExpressionNet.loadFromUri("/models"),
    ]);
    return faceapi;
  })();
  modelos.catch(() => (modelos = null));
  return modelos;
}

const dist = (a: Punto, b: Punto) => Math.hypot(a.x - b.x, a.y - b.y);

// Medidas del rostro a partir de los 68 puntos: giro (posición de la nariz entre los extremos de la
// mandíbula; 0.5 es de frente) y ancho de la boca relativo al ancho de la cara.
function medidas(p: Punto[]) {
  return {
    giro: (p[30].x - p[0].x) / (p[16].x - p[0].x),
    boca: dist(p[48], p[54]) / dist(p[0], p[16]),
  };
}

const mediana = (v: number[]) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)];
const siguienteCuadro = () => new Promise((res) => setTimeout(res, 0));

function elegirRetos(): Reto[] {
  const todos = Object.keys(RETOS) as Reto[];
  const azar = crypto.getRandomValues(new Uint32Array(todos.length));
  return todos.map((r, i) => [azar[i], r] as const).sort((a, b) => a[0] - b[0])
    .map(([, r]) => r).slice(0, RETOS_POR_VERIFICACION);
}

export interface ResultadoCaptura {
  descriptor: number[];
}

export function useCapturaFacial() {
  const video = useRef<HTMLVideoElement>(null);
  const [estado, setEstado] = useState<EstadoCaptura>("cargando");
  const [rostroVisible, setRostroVisible] = useState(false);
  const [instruccion, setInstruccion] = useState("Preparando la cámara…");
  const flujo = useRef<MediaStream | null>(null);
  const activo = useRef(true);
  const capturando = useRef(false);

  useEffect(() => {
    activo.current = true;
    (async () => {
      try {
        const [faceapi, stream] = await Promise.all([
          cargarModelos(),
          navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } } }),
        ]);
        if (!activo.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        flujo.current = stream;
        if (video.current) {
          video.current.srcObject = stream;
          await video.current.play();
        }
        setEstado("listo");
        setInstruccion("Centre su rostro en el círculo. Asegúrese de tener buena iluminación.");
        // Vista previa: indica si hay un rostro detectado.
        const opciones = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 });
        const vistaPrevia = async () => {
          if (!activo.current || !video.current) return;
          // Durante la captura se pausa, para no competir por la GPU con la prueba de vida.
          if (video.current.readyState >= 2 && !capturando.current) {
            const d = await faceapi.detectSingleFace(video.current, opciones);
            if (activo.current) setRostroVisible(!!d);
          }
          setTimeout(vistaPrevia, 400);
        };
        vistaPrevia();
      } catch (e) {
        console.error(e);
        if (!activo.current) return;
        setEstado("sin-camara");
        setInstruccion(e instanceof DOMException && e.name === "NotAllowedError"
          ? "Debe permitir el acceso a la cámara para verificar su identidad."
          : "No fue posible iniciar la cámara o cargar el reconocimiento facial.");
      }
    })();
    return () => {
      activo.current = false;
      flujo.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const capturar = useCallback(async (): Promise<ResultadoCaptura> => {
    const faceapi = await cargarModelos();
    const v = video.current;
    if (!v) throw new Error("La cámara no está disponible");
    setEstado("capturando");
    capturando.current = true;
    // El descriptor (128 valores) es costoso: solo se calcula al encuadrar. Los retos usan únicamente
    // detección y puntos faciales, que son rápidos, para reaccionar sin demora al movimiento.
    const precisas = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });
    const rapidas = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 });

    // Toma muestras mirando de frente. Devuelve los descriptores y las medidas de referencia.
    const encuadrar = async (cantidad: number) => {
      const descriptores: Float32Array[] = [];
      const base: ReturnType<typeof medidas>[] = [];
      const inicio = performance.now();
      while (descriptores.length < cantidad) {
        if (!activo.current) throw new Error("La cámara se detuvo");
        if (performance.now() - inicio > TIEMPO_ENCUADRE_MS) {
          throw new Error("No se obtuvo una imagen clara del rostro. Mire de frente, acérquese y mejore la iluminación.");
        }
        const r = await faceapi.detectSingleFace(v, precisas).withFaceLandmarks().withFaceDescriptor();
        if (r && r.detection.box.width / v.videoWidth > 0.18) {
          const m = medidas(r.landmarks.positions);
          if (Math.abs(m.giro - 0.5) < FRONTAL_MAXIMO) {
            descriptores.push(r.descriptor);
            base.push(m);
          }
        }
        await siguienteCuadro();
      }
      return { descriptores, base };
    };

    const cumplirReto = async (reto: Reto, ref: ReturnType<typeof medidas>) => {
      const inicio = performance.now();
      while (performance.now() - inicio < TIEMPO_RETO_MS) {
        if (!activo.current) return false;
        if (reto === "sonreir") {
          const r = await faceapi.detectSingleFace(v, rapidas).withFaceLandmarks().withFaceExpressions();
          if (r && (r.expressions.happy > SONRISA_MINIMA || medidas(r.landmarks.positions).boca > ref.boca * BOCA_SONRISA)) {
            return true;
          }
        } else {
          const r = await faceapi.detectSingleFace(v, rapidas).withFaceLandmarks();
          if (r) {
            const m = medidas(r.landmarks.positions);
            // Las coordenadas son de la imagen sin espejo: la izquierda de la persona queda a la derecha.
            if (reto === "izquierda" && m.giro - ref.giro > GIRO_MINIMO) return true;
            if (reto === "derecha" && ref.giro - m.giro > GIRO_MINIMO) return true;
          }
        }
        await siguienteCuadro();
      }
      return false;
    };

    try {
      setInstruccion("Mire de frente a la cámara…");
      const { descriptores, base } = await encuadrar(MUESTRAS);
      const ref = {
        giro: mediana(base.map((m) => m.giro)),
        boca: mediana(base.map((m) => m.boca)),
      };

      const retos = elegirRetos();
      for (const [i, reto] of retos.entries()) {
        setInstruccion(`Prueba ${i + 1} de ${retos.length}: ${RETOS[reto]}`);
        if (!(await cumplirReto(reto, ref))) {
          throw new Error(`No se detectó la acción solicitada (${RETOS[reto].toLowerCase()}). Intente de nuevo.`);
        }
        setInstruccion("¡Bien! Vuelva a mirar de frente…");
        await new Promise((res) => setTimeout(res, 800));
      }

      // El rostro del final debe ser el mismo del inicio, para que no se cambie de persona durante los retos.
      setInstruccion("Mire de frente a la cámara…");
      const final = await encuadrar(1);
      const promedio = Array.from({ length: 128 }, (_, i) => descriptores.reduce((s, d) => s + d[i], 0) / descriptores.length);
      if (faceapi.euclideanDistance(promedio, Array.from(final.descriptores[0])) > MISMA_PERSONA) {
        throw new Error("El rostro cambió durante la verificación. Intente de nuevo.");
      }
      setInstruccion("Rostro capturado");
      return { descriptor: promedio };
    } catch (e) {
      if (activo.current) setInstruccion("Presione «Iniciar verificación» para intentarlo de nuevo.");
      throw e;
    } finally {
      capturando.current = false;
      if (activo.current) setEstado("listo");
    }
  }, []);

  const detener = useCallback(() => {
    activo.current = false;
    flujo.current?.getTracks().forEach((t) => t.stop());
  }, []);

  return { video, estado, rostroVisible, instruccion, capturar, detener };
}

export function VistaCamara({ video, estado, rostroVisible, verificado }: {
  video: React.RefObject<HTMLVideoElement | null>; estado: EstadoCaptura; rostroVisible: boolean; verificado?: boolean;
}) {
  const borde = verificado ? "border-exito bg-exito-bg/40" : rostroVisible ? "border-primary" : "border-linea bg-sutil-2";
  return (
    <div className={`relative size-52 shrink-0 rounded-full border-[3.5px] transition-colors lg:size-64 ${borde}`}>
      <div className="absolute inset-6 flex items-center justify-center overflow-hidden rounded-full bg-sutil">
        <video ref={video} muted playsInline aria-label="Vista de la cámara"
          className={`size-full scale-x-[-1] object-cover ${estado === "listo" || estado === "capturando" ? "" : "hidden"}`} />
        {estado === "cargando" && <Loader2 className="size-10 animate-spin text-linea" />}
        {estado === "sin-camara" && <CameraOff className="size-12 text-apagado" />}
      </div>
      {estado === "capturando" && (
        <span className="absolute inset-0 animate-pulse rounded-full border-4 border-primary/60" aria-hidden />
      )}
      {!rostroVisible && estado === "listo" && (
        <span className="absolute -bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-bold text-tinta-2 shadow">
          <UserRound className="size-4" /> Sin rostro
        </span>
      )}
      {rostroVisible && estado === "listo" && (
        <span className="absolute -bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-bold text-primary shadow">
          <Camera className="size-4" /> Rostro detectado
        </span>
      )}
    </div>
  );
}
