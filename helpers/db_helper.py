#!/usr/bin/env python3

import asyncio
from dataclasses import dataclass
import json
from aiohttp import web
import asyncpg
import asyncpg.connect_utils
import asyncpg.pgproto.pgproto

from config import DefaultConfig
from helpers.lr_seen import LeastRecentlySeen
import logging

from opentelemetry import trace

tracer = trace.get_tracer(__name__)


@dataclass(kw_only=True)
class AADOIDInfo:
    aad_iod: str
    tenant_id: str
    teams_id: str
    name: str | None

    def __hash__(self) -> int:
        return hash((self.aad_iod, self.tenant_id, self.teams_id, self.name))


class NoResetConnection(asyncpg.connection.Connection):
    def __init__(
        self,
        protocol: asyncpg.protocol.protocol.BaseProtocol,
        transport: object,
        loop: asyncio.AbstractEventLoop,
        addr: tuple[str, int] | str,
        config: asyncpg.connect_utils._ClientConfiguration,
        params: asyncpg.connect_utils._ConnectionParameters,
    ) -> None:
        super().__init__(protocol, transport, loop, addr, config, params)
        self._reset_query = []


class DBHelper:
    def __init__(self, app: web.Application, config: DefaultConfig) -> None:
        self._app = app
        self._config = config
        self._pool: asyncpg.Pool | None = None
        self._aid_to_tid_lrs = LeastRecentlySeen(10_000)
        self.log = logging.getLogger(__name__)

    async def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self.log.info("creating database connection pool")
            self._pool = await asyncpg.create_pool(
                dsn=self._config.DATABASE_URL,
                server_settings={"application_name": "notiteams"},
                connection_class=NoResetConnection,
            )
            if self._pool is None:
                raise RuntimeError("could not create database connection pool")
        return self._pool

    async def acquire(self) -> asyncpg.pool.PoolAcquireContext:
        return (await self.pool()).acquire()

    async def save_message_for_deletion(self, conv_id: str, activity_id: str) -> None:
        connection: asyncpg.pool.PoolConnectionProxy
        async with await self.acquire() as connection:
            stmt = await connection.prepare(
                "INSERT INTO msg_to_delete (conv_id, activity_id) VALUES ($1, $2)"
            )
            await stmt.fetch(
                conv_id,
                activity_id,
            )
            # print(stmt.get_statusmsg())

    @tracer.start_as_current_span("save_aadoid_to_tid")
    async def save_aadoid_to_tid(self, aadinfo: AADOIDInfo) -> None:
        record = (aadinfo.aad_iod, aadinfo.tenant_id, aadinfo.teams_id, aadinfo.name)
        if self._aid_to_tid_lrs.look_and_remember(record):
            self.log.debug(f"already saved aadoid infos {record}")
            return
        async with await self.acquire() as connection:
            self.log.debug(f"saving aadoid infos {record}")
            await connection.execute(
                """
                INSERT INTO aadoid_to_tid (aad_oid, tenant_id, teams_id, name) VALUES ($1, $2, $3, $4)
                    ON CONFLICT(aad_oid) DO UPDATE
                    SET tenant_id = EXCLUDED.tenant_id,
                        teams_id = EXCLUDED.teams_id,
                        name = COALESCE(EXCLUDED.name, aadoid_to_tid.name)
                """,
                aadinfo.aad_iod,
                aadinfo.tenant_id,
                aadinfo.teams_id,
                aadinfo.name,
            )

    @tracer.start_as_current_span("get_token")
    async def get_token(
        self,
        *,
        tenant_id: str,
        conversation_teams_id: str,
        requester_aadoid: str,
        conversation_reference: str,
        activity_reference: str,
    ) -> str:
        # Two assumption here:
        # - teams direct line reaction time is not that great a shouldn't create race condition
        # - race condition is not a real problem and will simply create 2 tokens
        token: asyncpg.pgproto.pgproto.UUID | None = None
        conversation_reference_id = -1
        conversation_token_id = -1
        span = trace.get_current_span()
        async with await self.acquire() as connection:
            selectres = await connection.fetchrow(
                """
                SELECT cr.conversation_reference_id, conversation_token, conversation_token_id
                FROM conversation_reference cr
                LEFT JOIN conversation_token ct USING (conversation_reference_id)
                WHERE tenant_id = $1 AND conversation_teams_id = $2 AND requester_aadoid = $3
                ORDER BY ct.created_at ASC LIMIT 1
                """,
                tenant_id,
                conversation_teams_id,
                requester_aadoid,
            )

            # No token not even a conversation reference
            if selectres is None:
                inserted_convref = await connection.fetchrow(
                    """
                    INSERT INTO conversation_reference (
                        tenant_id,
                        conversation_teams_id,
                        requester_aadoid,
                        conversation_reference,
                        activity_reference
                    ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT(tenant_id, conversation_teams_id, requester_aadoid)
                        DO NOTHING RETURNING conversation_reference_id
                    """,
                    tenant_id,
                    conversation_teams_id,
                    requester_aadoid,
                    json.dumps(conversation_reference),
                    json.dumps(activity_reference),
                )
                assert inserted_convref is not None
                conversation_reference_id = inserted_convref["conversation_reference_id"]
            else:
                # Conversation reference yes, token, not sure
                conversation_reference_id = selectres["conversation_reference_id"]
                if selectres["conversation_token"]:
                    token = selectres["conversation_token"]
                    conversation_token_id = selectres["conversation_token_id"]

            # Now we have a conversation_reference_id
            if not token:
                insertres = await connection.fetchrow(
                    """
                    INSERT INTO conversation_token (
                        conversation_reference_id,
                        user_description
                    ) VALUES ($1, 'default initial token for this conversation')
                        RETURNING conversation_token, conversation_token_id
                    """,
                    conversation_reference_id,
                )
                if insertres is None:
                    raise RuntimeError("could not retrieve conversation token")
                token = insertres["conversation_token"]
                conversation_token_id = insertres["conversation_token_id"]
        span.set_attributes(
            {
                "notiteams.conversation_token_id": conversation_token_id,
                "notiteams.conversation_reference_id": conversation_reference_id,
            }
        )
        return str(token)
