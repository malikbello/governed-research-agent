# NOOA needs fcntl (Unix-only) -- this image runs it in its native environment,
# sidestepping the native-Windows incompatibility entirely.
FROM python:3.12-slim AS base

WORKDIR /app

# System deps for common LiteLLM/httpx transitive needs; kept minimal deliberately.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY governed_agent.py research_agent.py demo.py ./
COPY frontend/ ./frontend/
COPY server.py ./

# Never bake secrets into the image -- GEMINI_API_KEY is injected at run time
# (docker run -e / Kubernetes Secret), never copied in via COPY or ARG.
ENV NOOA_MODEL="gemini/gemini-3.5-flash-lite"
ENV PORT=8000

EXPOSE 8000

# Non-root user -- production-grade default, not root-in-container.
RUN useradd --create-home --shell /bin/bash agent
USER agent

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["python", "server.py"]
