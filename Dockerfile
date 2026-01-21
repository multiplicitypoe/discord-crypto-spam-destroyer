FROM python:3.11-slim

WORKDIR /app

ENV TZ=America/Los_Angeles
# Override in .env

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir poetry==1.8.5

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY data /app/data

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "discord_crypto_spam_destroyer.bot"]
