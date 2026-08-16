PYTHON ?= python3

.PHONY: install generate validate test reproducible check clean

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

generate:
	$(PYTHON) scripts/generate.py

validate:
	$(PYTHON) scripts/validate.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check: validate test
	$(PYTHON) -m pip check

reproducible: generate check
	git diff --check
	git diff --exit-code -- catalog packs

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist htmlcov
