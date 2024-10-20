#!/usr/bin/env python3
import json
import logging
import time
from typing import Optional

import httpx
import jwt
from aiohttp import web
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from botbuilder.integration.aiohttp import CloudAdapter
from config import DefaultConfig


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
HTTPXClientInstrumentor().instrument()


def jprint(value):
    print(json.dumps(value, indent=2))


class MSGraphHelper:
    def __init__(self, app: web.Application, adapter: CloudAdapter, config: DefaultConfig):
        self._app = app
        self._config = config
        self._access_token: Optional[str] = None
        self._decoded_access_token: dict = {}
        self._client = httpx.AsyncClient()
        self._base = "https://graph.microsoft.com/v1.0/"

    async def _check_token(self):
        if self._access_token is None or (self._decoded_access_token.get("exp", 0) - time.time()) < 60:
            url = f"https://login.microsoftonline.com/{self._config.APP_TENANTID}/oauth2/v2.0/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self._config.APP_ID,
                "client_secret": self._config.APP_PASSWORD,
                "scope": "https://graph.microsoft.com/.default",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                self._access_token = response.json()["access_token"]
                assert self._access_token is not None
                self._decoded_access_token = jwt.decode(
                    self._access_token,
                    options={"verify_signature": False},
                )  # type: ignore
                self._client.headers = {
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                }

    @tracer.start_as_current_span("query")
    async def _query(self, target: str, params=None, method="GET", json=None) -> dict:
        await self._check_token()
        span = trace.get_current_span()
        span.update_name(f"{method} /v1.0/{target}")
        url = target

        if not url.startswith("https://"):
            url = self._base + target

        response = await self._client.request(method, url, params=params, json=json)
        response.raise_for_status()
        return response.json()

    async def _query_and_consume(self, target: str, params=None) -> dict:
        res = await self._query(
            target,
            params,
        )
        return res
