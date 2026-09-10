# discord-crypto-spam-destroyer: catches crypto scam posts and reports them.

VENV ?= .venv
PYTHON ?= python3
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python
PIP_INSTALL_FLAGS ?= --no-cache-dir --only-binary=:all:

IMAGE ?= discord-crypto-spam-destroyer
CONTAINER ?= discord-crypto-spam-destroyer
DATA_DIR ?= data
PRE_RUN = sh scripts/prepare-data.sh

RUN_ARGS = \
	--env-file "$(CURDIR)/.env" \
	-v "$(CURDIR)/data:/app/data"
RUN_ARGS += $(HARDENED_ARGS)

include docker.mk

.PHONY: help ensure-venv install install-dev hashes test-openai test-discord test run-bot

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
