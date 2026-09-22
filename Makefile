PY   := .venv/bin/python
PIP  := .venv/bin/pip
PORT ?= 3000
BASE := http://127.0.0.1:$(PORT)

.DEFAULT_GOAL := help
.PHONY: help install demo broken profile project all scan run pages watch dash rules inspect clean

# Is something already listening on $(PORT)?
UP := $(PY) -c "import socket,sys; sys.exit(0 if socket.socket().connect_ex(('127.0.0.1',$(PORT)))==0 else 1)"

# Run a scan with the demo app available. If the app is already running
# (someone left `make run` going) it is reused and left alone; otherwise it is
# started, waited for, and stopped again on the way out — including on Ctrl-C
# or failure, so a stray server is never left behind.
define with_app
	@set -e; \
	if $(UP) 2>/dev/null; then \
	  echo "  using the demo app already on :$(PORT)"; \
	else \
	  $(PY) -m demo_app.app $(PORT) >/dev/null 2>&1 & \
	  pid=$$!; \
	  trap "kill $$pid 2>/dev/null || true" EXIT INT TERM; \
	  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do \
	    $(UP) 2>/dev/null && break; sleep 0.2; \
	  done; \
	  $(UP) 2>/dev/null || { echo "demo app failed to start on :$(PORT)"; exit 1; }; \
	fi; \
	$(1)
endef

help:  ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  Start here:  make demo"
	@echo "  Each scan starts and stops the demo app for you."

install:  ## Create the venv and install dependencies
	python3 -m venv .venv
	$(PIP) -q install -r requirements.txt
	$(PY) -m playwright install chromium

demo: broken  ## Start here — scan the page with the planted regression

broken:  ## Scan /profile-broken — expect a violation
	$(call with_app, $(PY) main.py $(BASE)/profile-broken $(ARGS))

profile:  ## Scan /profile — expect all pass
	$(call with_app, $(PY) main.py $(BASE)/profile $(ARGS))

project:  ## Scan /project-settings — expect all pass
	$(call with_app, $(PY) main.py $(BASE)/project-settings $(ARGS))

all:  ## Scan all three demo pages, then build the dashboard
	$(call with_app, \
	  $(PY) main.py $(BASE)/profile          $(ARGS) || true; \
	  $(PY) main.py $(BASE)/profile-broken   $(ARGS) || true; \
	  $(PY) main.py $(BASE)/project-settings $(ARGS) || true)
	@$(PY) -m reporting.dashboard

scan:  ## Scan any URL: make scan URL=http://localhost:8080/settings
	@test -n "$(URL)" || { echo "usage: make scan URL=<url>"; exit 2; }
	$(PY) main.py $(URL) $(ARGS)

pages:  ## Open the three demo pages in your browser
	$(PY) -m demo_app.app $(PORT) --open

watch:  ## Scan the broken page with the browser visible
	$(call with_app, $(PY) main.py $(BASE)/profile-broken --headed $(ARGS))

run:  ## Serve the demo app in the foreground (no browser)
	$(PY) -m demo_app.app $(PORT)

dash:  ## Build runs/dashboard.html from recorded runs and open it
	$(PY) -m reporting.dashboard --open

rules:  ## Print the loaded rule base (no browser, no network)
	$(PY) -m knowledge.engine

inspect:  ## Print a page snapshot: make inspect URL=... (no LLM)
	$(call with_app, $(PY) -m discovery.page_inspector $(or $(URL),$(BASE)/profile))

clean:  ## Remove caches and run records
	rm -rf runs __pycache__ */__pycache__
