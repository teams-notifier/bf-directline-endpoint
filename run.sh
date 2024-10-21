#!/bin/bash

opentelemetry-instrument \
    --traces_exporter otlp \
    --metrics_exporter otlp \
    --logs_exporter otlp \
    --service_name notifier-bfdl-api \
    ./app.py
