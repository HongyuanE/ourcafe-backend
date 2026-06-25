# syntax=docker/dockerfile:1

# ---- builder stage: install dependencies into an isolated prefix ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage: copy only what's needed, run as non-root ----
FROM python:3.12-slim
# Create an unprivileged user — containers should never run as root (DevSecOps baseline).
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
# Stamp the build with its git commit so the running service can report what's live.
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}
USER appuser
EXPOSE 8000
# Container-native liveness check; the orchestrator can read this status.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
