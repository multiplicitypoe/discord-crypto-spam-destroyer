FROM python:3.11-slim-bookworm

WORKDIR /app

ENV TZ=America/Los_Angeles
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOME=/tmp
ENV PIP_NO_CACHE_DIR=1
ENV PIP_ONLY_BINARY=:all:
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Override in .env

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    apt-get update; \
    if [ "$arch" = "armhf" ]; then \
        apt-get install -y --no-install-recommends \
            tzdata \
            libatomic1 \
            libfreetype6 \
            libgcc-s1 \
            libgfortran5 \
            libjpeg62-turbo \
            liblcms2-2 \
            libopenblas0 \
            libopenjp2-7 \
            libstdc++6 \
            libtiff6 \
            libwebp7 \
            libwebpdemux2 \
            libwebpmux3 \
            libxcb1 \
            zlib1g; \
    else \
        apt-get install -y --no-install-recommends tzdata; \
    fi; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN set -eux; \
    extra=""; \
    if [ "$(dpkg --print-architecture)" = "armhf" ]; then \
        extra="--extra-index-url https://www.piwheels.org/simple"; \
    fi; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir --only-binary=:all: $extra -r requirements.txt

RUN python -c "import PIL, numpy, scipy, pywt"

COPY README.md /app/
COPY src /app/src
COPY data /app/data

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app

ENV PYTHONPATH=/app/src

USER app

CMD ["python", "-m", "discord_crypto_spam_destroyer.bot"]
