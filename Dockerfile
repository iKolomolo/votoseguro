FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
# Tesseract lee la cédula (OCR): número, nombres, apellidos y fecha. El paquete en español lee la Ñ y las tildes.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /app/frontend/dist /app/frontend/dist
# Los archivos temporales (Tesseract escribe la foto de la cédula un instante para leerla) van a /dev/shm, que está
# en la memoria RAM: la foto nunca se escribe en disco. Si /dev/shm no existiera, Python usa la carpeta temporal normal.
ENV TMPDIR=/dev/shm
# Tesseract en un solo hilo: con la poca CPU del plan gratuito, varios hilos compiten y la lectura es ~3 veces más
# lenta.
ENV OMP_THREAD_LIMIT=1
EXPOSE 8000
# Render asigna el puerto en $PORT; en local se usa 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
