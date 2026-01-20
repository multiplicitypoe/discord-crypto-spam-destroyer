.PHONY: venv-install hashes test-openai test-discord run-bot run-docker-bot help

help:
	@echo "make venv-install   - create .venv and install deps"
	@echo "make hashes         - generate hashes from known bad images"
	@echo "make test-openai    - run OpenAI image classification test"
	@echo "make test-discord   - send a dummy mod report"
	@echo "make run-bot        - run the bot with .env"
	@echo "make run-docker-bot - build and run with Docker"

venv-install:
	bash -c 'if [ ! -d .venv ]; then python3 -m venv .venv; fi; . .venv/bin/activate && python -m pip install --upgrade pip && python -m pip install .'

hashes: venv-install
	bash -c '. .venv/bin/activate && python tools/generate_hashes.py'

test-openai: venv-install
	bash -c 'set -a && . ./.env && set +a && . .venv/bin/activate && python tools/check_images.py'

test-discord: venv-install
	bash -c 'set -a && . ./.env && set +a && . .venv/bin/activate && PYTHONPATH=src python tools/send_test_report.py'

run-bot: venv-install
	bash -c 'set -a && . ./.env && set +a && . .venv/bin/activate && PYTHONPATH=src python -m discord_crypto_spam_destroyer.bot'

run-docker-bot:
	sudo docker build -t discord-crypto-spam-destroyer . && sudo docker run --env-file .env discord-crypto-spam-destroyer
