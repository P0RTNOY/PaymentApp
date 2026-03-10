FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user for Cloud Run security
RUN adduser --disabled-password --gecos "" appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/

# Cloud Run sets PORT env var
ENV PORT=8000

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
