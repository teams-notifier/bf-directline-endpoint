FROM python:slim-bookworm

ARG VERSION
ARG SEMVER_CORE
ARG COMMIT_SHA
ARG GITHUB_REPO
ARG BUILD_DATE

ENV VERSION=${VERSION}
ENV SEMVER_CORE=${SEMVER_CORE}
ENV COMMIT_SHA=${COMMIT_SHA}
ENV BUILD_DATE=${BUILD_DATE}
ENV GITHUB_REPO=${GITHUB_REPO}

LABEL org.opencontainers.image.source=${GITHUB_REPO}
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.version=${VERSION}
LABEL org.opencontainers.image.revision=${COMMIT_SHA}

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
