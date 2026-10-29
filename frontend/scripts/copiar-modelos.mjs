// Copia a public/models los modelos de face-api que usa la verificación facial.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const origen = join(raiz, "node_modules/@vladmandic/face-api/model");
const destino = join(raiz, "public/models");
const modelos = ["tiny_face_detector_model", "face_landmark_68_model", "face_recognition_model",
  "face_expression_model"];

mkdirSync(destino, { recursive: true });
for (const m of modelos) {
  for (const ext of [".bin", "-weights_manifest.json"]) {
    const archivo = m + ext;
    if (!existsSync(join(destino, archivo))) copyFileSync(join(origen, archivo), join(destino, archivo));
  }
}
console.log("Modelos de face-api listos en public/models");
