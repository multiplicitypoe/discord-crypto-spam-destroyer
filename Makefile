.PHONY: hashes check-images test-report run-bot run-docker-bot venv-install

venv-install:
	bash -c 'if [ ! -d .venv ]; then python3 -m venv .venv; fi; . .venv/bin/activate && python -m pip install --upgrade pip && python -m pip install .'

hashes: venv-install
	bash -c '. .venv/bin/activate && python tools/generate_hashes.py'

check-images: venv-install
	bash -c '. .venv/bin/activate && python tools/check_images.py'

test-report: venv-install
	bash -c 'set -a && . ./.env && set +a && . .venv/bin/activate && PYTHONPATH=src python tools/send_test_report.py'

run-bot: venv-install
	bash -c 'set -a && . ./.env && set +a && . .venv/bin/activate && PYTHONPATH=src python -m discord_crypto_spam_destroyer.bot'

run-docker-bot:
	sudo docker build -t discord-crypto-spam-destroyer . && sudo docker run --env-file .env discord-crypto-spam-destroyer
