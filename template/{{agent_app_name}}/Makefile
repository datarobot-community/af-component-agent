SHELL := bash

.PHONY: fix-licenses

req:
	uv sync --all-extras --dev

lint:
	uv run ruff check . --fix
	uv run ruff format .
	uv run mypy --pretty .

test:
	uv run pytest -vv tests/

fix-licenses:
	docker run  --rm -v $(CURDIR):/github/workspace ghcr.io/apache/skywalking-eyes/license-eye:785bb7f3810572d6912666b4f64bad28e4360799 -v info -c .licenserc.yaml header fix

