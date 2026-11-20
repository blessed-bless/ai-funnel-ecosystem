.PHONY: run test lint fmt format

run:
	aifunnel-api

test:
	pytest -q

lint:
	ruff check src tests

fmt format:
	ruff format src tests
	ruff check --fix src tests
