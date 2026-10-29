# Shared image for every Python microservice. Build with --build-arg SERVICE=<identity|integrations|...>.
FROM python:3.12-slim
ARG SERVICE
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY services ./services
RUN uv sync --frozen --no-dev --no-editable --package alphaview-${SERVICE}

RUN useradd --create-home --uid 10001 app
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
