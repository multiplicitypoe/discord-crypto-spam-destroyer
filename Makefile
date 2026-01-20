.PHONY: ensure-poetry install hashes test-openai test-discord test run-bot run-docker-bot help

help:
	@echo "make ensure-poetry  - install poetry if missing"
	@echo "make install        - install deps via poetry"
	@echo "make hashes         - generate hashes from known bad images"
	@echo "make test-openai    - run OpenAI image classification test"
	@echo "make test-discord   - send a dummy mod report"
	@echo "make test           - run pytest (via poetry)"
	@echo "make run-bot        - run the bot with .env"
	@echo "make run-docker-bot - build and run with Docker (persist data/)"

ensure-poetry:
	@command -v poetry >/dev/null 2>&1 || (echo "Poetry is required. Install from https://python-poetry.org/docs/#installation" && exit 1)

install: ensure-poetry
	poetry install

hashes: install
	poetry run python tools/generate_hashes.py

test-openai: install
	bash -c 'set -a && . ./.env && set +a && poetry run python tools/check_images.py'

test-discord: install
	bash -c 'set -a && . ./.env && set +a && PYTHONPATH=src poetry run python tools/send_test_report.py'

test: ensure-poetry
	poetry install --with dev
	poetry run pytest

run-bot: install
	bash -c 'set -a && . ./.env && set +a && PYTHONPATH=src poetry run python -m discord_crypto_spam_destroyer.bot'

run-docker-bot:
	sudo docker build -t discord-crypto-spam-destroyer . && sudo docker run --env-file .env -v $(PWD)/data:/app/data discord-crypto-spam-destroyer
