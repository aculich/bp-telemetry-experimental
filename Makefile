.PHONY: setup run clean verify

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	touch $(VENV)/bin/activate

run: setup
	$(PYTHON) src/processing/server.py

verify: setup
	$(PYTHON) scripts/verify_antigravity.py

install-extension: setup
	$(PYTHON) scripts/install_antigravity.py

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
