FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /install /usr/local
COPY alembic.ini ./
COPY alembic ./alembic

RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV DATABASE_URL=sqlite+aiosqlite:///./data/aifunnel.db
EXPOSE 8080

CMD ["aifunnel-api"]
