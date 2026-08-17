FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY config/app.config.yaml ./config.yaml
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8000 50051

# 默认启动 app 服务。lexicon 微服务也复用同一镜像，可通过项目 CLI 启动。
# Start the app service by default. The lexicon service can reuse the same image and be started via the project CLI.

# App example:
#   docker run --rm -p 8000:8000 -v "$PWD/config/app.config.yaml:/app/config.yaml:ro" echocue-app:0.1.0
# Lexicon example:
#   docker run --rm -p 50051:50051 -v "$PWD/config/app.config.yaml:/app/config.yaml:ro" \
#     -v "$PWD/assets:/app/assets:ro" echocue-app:0.1.0 uv run app lexicon serve
CMD ["uv", "run", "app", "run", "--host", "0.0.0.0", "--port", "8000"]
