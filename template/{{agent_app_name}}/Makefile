SHELL := bash

.PHONY: fix-licenses

req:
	uv sync --all-extras
	uv pip install git+https://github.com/datarobot-forks/litellm@mattn/add-datarobot-support-to-litellm

lint:
	uv run ruff check . --fix
	uv run ruff format .
	uv run mypy --pretty .

test:
	uv run pytest -vv tests/

fix-licenses:
	# Must be run from within the agent_crewai directory inside an app recipe container
	cp ../.github/.licenserc.yaml ./
	docker run  --rm -v $(CURDIR):/github/workspace ghcr.io/apache/skywalking-eyes/license-eye:785bb7f3810572d6912666b4f64bad28e4360799 -v info -c .licenserc.yaml header fix
	rm ./.licenserc.yaml
