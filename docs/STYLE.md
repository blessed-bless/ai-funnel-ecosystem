# Portfolio style standard

Target look: one developer, calm and concrete. Behavior stays the same; style aligns.

## Layout

```
src/<package>/     # library + app code
tests/             # pytest (or package-equivalent for JS/TS)
Dockerfile         # multi-stage, non-root
docker-compose.yml
Makefile           # run test lint fmt
.env.example       # commented keys, no secrets
README.md
pyproject.toml     # Python projects
```

Single entry per process via console script or `__main__`.

## Python

- Version: **3.12**
- Tooling: **ruff** for lint + format
- Type hints where non-obvious
- Config: **pydantic-settings**
- Logging: stdlib `logging`, one formatter; no `print` in app code
- Comments: English only, explain *why*
- Docstrings: public modules/classes only, short
- Errors: domain exceptions where useful; no bare `except`

## Infra

- Dockerfile: multi-stage when needed; final image non-root
- Makefile: `run`, `test`, `lint`, `fmt`
- `.env.example`: every runtime variable with a short comment

## README

One sentence · screenshot · 4–6 capabilities · mermaid · stack · run · config table.  
No emoji lists, no badge walls.

## Commits

Conventional Commits, English, short. Sole human author.
