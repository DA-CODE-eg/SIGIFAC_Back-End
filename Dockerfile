FROM debian:bookworm-slim AS modelos
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*
COPY descargar-modelos.sh /descargar-modelos.sh
RUN sh /descargar-modelos.sh /modelos

FROM python:3.12-slim
RUN pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.34.2 opencv-python-headless==4.11.0.86 numpy==2.2.5
WORKDIR /app
COPY app.py .
COPY --from=modelos /modelos /modelos
USER 65534
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081", "--no-access-log"]
