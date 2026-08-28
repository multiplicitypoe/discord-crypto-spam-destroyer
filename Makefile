.PHONY: ensure-venv install install-dev hashes test-openai test-discord test run-bot ensure-data ensure-env build-docker stop-docker run-docker docker run-docker-bot help

VENV ?= .venv
PYTHON ?= python3
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

PIP_INSTALL_FLAGS ?= --no-cache-dir --only-binary=:all:
DOCKER_BIN ?= docker
DOCKER ?= $(shell \
	if command -v "$(DOCKER_BIN)" >/dev/null 2>&1; then \
		if "$(DOCKER_BIN)" ps >/dev/null 2>&1; then \
			printf '%s' "$(DOCKER_BIN)"; \
		elif command -v sudo >/dev/null 2>&1 && sudo -n "$(DOCKER_BIN)" ps >/dev/null 2>&1; then \
			printf '%s' "sudo -n $(DOCKER_BIN)"; \
		else \
			printf '%s' "$(DOCKER_BIN)"; \
		fi; \
	else \
		printf '%s' "$(DOCKER_BIN)"; \
	fi)
IMAGE ?= discord-crypto-spam-destroyer
TAG ?= latest
CONTAINER ?= discord-crypto-spam-destroyer

help:
	@echo "make ensure-venv    - create .venv if missing"
	@echo "make install        - install runtime deps (pip)"
	@echo "make hashes         - generate hashes from known bad images"
	@echo "make test-openai    - run OpenAI image classification test"
	@echo "make test-discord   - send a dummy mod report"
	@echo "make test           - run pytest (pip)"
	@echo "make run-bot        - run the bot with .env"
	@echo "make build-docker   - build Docker image ($(IMAGE):$(TAG))"
	@echo "make stop-docker    - stop/remove current Docker container ($(CONTAINER))"
	@echo "make run-docker     - restart named Docker container in foreground"
	@echo "make docker         - build image then run container"
	@echo "make run-docker-bot - alias for run-docker"

ensure-venv:
	@test -x "$(PY)" || ($(PYTHON) -m venv "$(VENV)" && "$(PIP)" install --upgrade pip)

install: ensure-venv
	"$(PIP)" install $(PIP_INSTALL_FLAGS) -r requirements.txt

install-dev: ensure-venv
	"$(PIP)" install $(PIP_INSTALL_FLAGS) -r requirements-dev.txt

ensure-data:
	@mkdir -p data

ensure-env:
	@test -f "$(CURDIR)/.env" || (cp "$(CURDIR)/.env.example" "$(CURDIR)/.env" && \
		printf '%s\n' "Created .env from .env.example. Edit .env, then re-run." && \
		exit 1)

hashes: install
	"$(PY)" tools/generate_hashes.py

test-openai: install
	bash -c 'set -a && . ./.env && set +a && PYTHONPATH=src "$(PY)" tools/check_images.py'

test-discord: install
	bash -c 'set -a && . ./.env && set +a && PYTHONPATH=src "$(PY)" tools/send_test_report.py'

test: install-dev
	PYTHONPATH=src "$(PY)" -m pytest -o asyncio_mode=auto

run-bot: install
	bash -c 'set -a && . ./.env && set +a && PYTHONPATH=src "$(PY)" -m discord_crypto_spam_destroyer.bot'

build-docker: ensure-data
	@if [ ! -s data/report_store.json ]; then \
		printf '%s\n' '{"reports": []}' > data/report_store.json; \
	fi
	@chmod a+rw data/report_store.json 2>/dev/null || (command -v sudo >/dev/null 2>&1 && sudo chmod a+rw data/report_store.json) || true
	$(DOCKER) build -t "$(IMAGE):$(TAG)" "$(CURDIR)"

stop-docker:
	@if $(DOCKER) container inspect "$(CONTAINER)" >/dev/null 2>&1; then \
		if [ "$$($(DOCKER) inspect -f '{{.State.Running}}' "$(CONTAINER)" 2>/dev/null)" = "true" ]; then \
			echo "Stopping container $(CONTAINER)"; \
			$(DOCKER) stop "$(CONTAINER)" >/dev/null; \
		fi; \
		echo "Removing container $(CONTAINER)"; \
		$(DOCKER) rm "$(CONTAINER)" >/dev/null 2>&1 || true; \
	else \
		echo "Container $(CONTAINER) not found; nothing to stop."; \
	fi

run-docker: ensure-env ensure-data stop-docker
	@if [ ! -s data/report_store.json ]; then \
		printf '%s\n' '{"reports": []}' > data/report_store.json; \
	fi
	@chmod a+rw data/report_store.json 2>/dev/null || (command -v sudo >/dev/null 2>&1 && sudo chmod a+rw data/report_store.json) || true
	$(DOCKER) run --rm \
		--name "$(CONTAINER)" \
		--env-file "$(CURDIR)/.env" \
		-v "$(CURDIR)/data:/app/data" \
		--read-only \
		--tmpfs /tmp:rw,noexec,nosuid,nodev \
		--cap-drop ALL \
		--security-opt no-new-privileges \
		--pids-limit 256 \
		--memory 512m \
		--cpus 1.0 \
		--user "$$(id -u):$$(id -g)" \
		"$(IMAGE):$(TAG)"

docker: build-docker run-docker

run-docker-bot: run-docker
