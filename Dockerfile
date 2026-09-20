# Stage 1: genera gli asset PNG (richiede Pillow, solo qui in fase di build).
FROM python:3.12-slim AS assets
WORKDIR /app
COPY requirements-dev.txt ./
COPY tools/ ./tools/
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN python tools/generate_assets.py webapp/assets \
 && python tools/npc_portraits.py webapp/assets

# Stage 2: immagine di runtime, senza Pillow.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=assets /app/webapp/assets ./webapp/assets

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
