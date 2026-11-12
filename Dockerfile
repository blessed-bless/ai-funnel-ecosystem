FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite+aiosqlite:///./data/aifunnel.db
EXPOSE 8080

CMD ["aifunnel-api"]
