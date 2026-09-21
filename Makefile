PY  := .venv/bin/python
PIP := .venv/bin/pip
PORT ?= 3000
BASE := http://127.0.0.1:$(PORT)

.DEFAULT_GOAL := help
.PHONY: help install run demo scan profile broken project rules inspect clean

help:  ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  Start the demo app with 'make run', then scan it from another terminal."

install:  ## Create the venv and install dependencies
	python3 -m venv .venv
	$(PIP) -q install -r requirements.txt
	$(PY) -m playwright install chromium

run:  ## Start the demo application (leave this running)
	$(PY) -m demo_app.app $(PORT)

demo: broken  ## Scan the page with the planted regression

broken:  ## Scan /profile-broken — expect a violation
	$(PY) main.py $(BASE)/profile-broken

profile:  ## Scan /profile — expect all pass
	$(PY) main.py $(BASE)/profile

project:  ## Scan /project-settings — expect all pass
	$(PY) main.py $(BASE)/project-settings

scan:  ## Scan any URL: make scan URL=http://localhost:8080/settings
	@test -n "$(URL)" || { echo "usage: make scan URL=<url>"; exit 2; }
	$(PY) main.py $(URL) $(ARGS)

rules:  ## Print the loaded rule base (no browser, no network)
	$(PY) -m knowledge.engine

inspect:  ## Print a page snapshot: make inspect URL=... (no LLM)
	$(PY) -m discovery.page_inspector $(or $(URL),$(BASE)/profile)

clean:  ## Remove caches and run records
	rm -rf runs __pycache__ */__pycache__
