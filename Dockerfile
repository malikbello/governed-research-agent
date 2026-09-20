# NOOA needs fcntl (Unix-only) -- this image runs it in its native environment,
# sidestepping the native-Windows incompatibility entirely.
FROM python:3.12-slim AS base

WORKDIR /app

# build-essential for common LiteLLM/httpx transitive needs; Node.js for the
# Tavily MCP server (run via `npx tavily-mcp`, a Node package -- confirmed
# during development that WSL's cross-boundary Windows npx was unreliable,
# so this image installs Node natively rather than relying on any host tool.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml PACKAGE_README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

COPY governed_agent.py research_agent.py due_diligence_agent.py nvd_lookup.py \
     checklist.py assessment_runner.py assessment_store.py security.py \
     demo.py demo_due_diligence.py server.py .mcp.json ./
COPY frontend/ ./frontend/

# Never bake secrets into the image -- GEMINI_API_KEY, TAVILY_API_KEY, and
# API_KEY are all injected at run time (docker run -e / Kubernetes Secret),
# never copied in via COPY or ARG.
ENV NOOA_MODEL="gemini/gemini-3.5-flash-lite"
ENV PORT=8000

EXPOSE 8000

# Non-root user -- production-grade default, not root-in-container. Also owns
# /app so npx's runtime cache and the SQLite assessments.db can be written.
RUN useradd --create-home --shell /bin/bash agent && chown -R agent:agent /app
USER agent

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["python", "server.py"]
