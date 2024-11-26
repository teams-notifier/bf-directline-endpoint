#!/bin/bash

export OTEL_PYTHON_EXCLUDED_URLS=${OTEL_PYTHON_EXCLUDED_URLS:-healthz}

opentelemetry-instrument \
    --traces_exporter otlp \
    --metrics_exporter otlp \
    --logs_exporter otlp \
    --service_name notifier-bfdl-api \
    ./app.py
