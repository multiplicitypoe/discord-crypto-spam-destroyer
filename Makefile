.PHONY: ensure-venv install install-dev hashes test-openai test-discord test run-bot run-docker run-docker-bot help

VENV ?= .venv
PYTHON ?= python3
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

PIP_INSTALL_FLAGS ?= --no-cache-dir --only-binary=:all:

help:
	@echo "make ensure-venv    - create .venv if missing"
	@echo "make install        - install runtime deps (pip)"
	@echo "make hashes         - generate hashes from known bad images"
	@echo "make test-openai    - run OpenAI image classification test"
	@echo "make test-discord   - send a dummy mod report"
	@echo "make test           - run pytest (pip)"
	@echo "make run-bot        - run the bot with .env"
	@echo "make run-docker     - build and run with Docker (persist data/)"
	@echo "make run-docker-bot - alias for run-docker"

ensure-venv:
	@test -x "$(PY)" || ($(PYTHON) -m venv "$(VENV)" && "$(PIP)" install --upgrade pip)

install: ensure-venv
	"$(PIP)" install $(PIP_INSTALL_FLAGS) -r requirements.txt

install-dev: ensure-venv
	"$(PIP)" install $(PIP_INSTALL_FLAGS) -r requirements-dev.txt

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

build-docker:
	@mkdir -p data
	sudo docker build -t discord-crypto-spam-destroyer . && sudo docker run --env-file .env -v $(PWD)/data:/app/data --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 512m --cpus 1.0 --user $(shell id -u):$(shell id -g) discord-crypto-spam-destroyer

run-docker:
	sudo docker run --env-file .env -v $(PWD)/data:/app/data --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 512m --cpus 1.0 --user $(shell id -u):$(shell id -g) discord-crypto-spam-destroyer

run-docker-bot: build-docker run-docker
