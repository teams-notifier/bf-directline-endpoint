FROM python:slim-bookworm

LABEL org.opencontainers.image.source=https://github.com/teams-notifier/bf-directline-endpoint

RUN set -e \
    && useradd -ms /bin/bash -d /app app

WORKDIR /app
USER app

ENV PATH="$PATH:/app/.local/bin/"

COPY requirements.txt /app/

RUN set -e \
    && pip install --no-cache-dir -r /app/requirements.txt --break-system-packages \
    && pip install aiohttp==3.10.11 --break-system-packages \
    && opentelemetry-bootstrap -a install

COPY --chown=app:app . /app/

CMD ["/app/run.sh"]
