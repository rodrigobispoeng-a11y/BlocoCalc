.PHONY: setup test lint typecheck check bench

setup:
	conda env create -f environment.yml

test:
	pytest --cov --cov-report=term-missing

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy src tests

check: lint typecheck test

bench:
	pytest -m benchmark
