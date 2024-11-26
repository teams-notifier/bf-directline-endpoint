#!/usr/bin/env python
import asyncio
import logging
import sys
import traceback
import uuid
from asyncio.log import logger
from datetime import datetime
from typing import Awaitable

import asyncpg
import blibs
import dotenv
from aiohttp import web
from aiohttp.web import Request
from aiohttp.web import Response
from botbuilder.core import TurnContext
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter
from botbuilder.integration.aiohttp import ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes

from bots import NotiTeamsBot
from config import DefaultConfig
from helpers import Helpers
from helpers import MessageHelper
from helpers import MSGraphHelper
from helpers.db_helper import DBHelper

blibs.init_root_logger()
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("msal").setLevel(logging.ERROR)
logging.getLogger("msrest").setLevel(logging.ERROR)

dotenv.load_dotenv()
CONFIG = DefaultConfig()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
ADAPTER = CloudAdapter(
    ConfigurationBotFrameworkAuthentication(
        CONFIG,
        credentials_factory=CONFIG.get_credential_factory(),
    )
)


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # NOPE
    # await context.send_activity("The bot encountered an error or bug, please contact the maintainer.")

    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)


ADAPTER.on_turn_error = on_error

# If the channel is the Emulator, and authentication is not in use, the AppId will be null.
# We generate a random AppId for this case only. This is not required for production, since
# the AppId will have a value.
APP_ID = CONFIG.APP_ID if CONFIG.APP_ID else uuid.uuid4()


# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    return await ADAPTER.process(req, BOT)  # type: ignore


async def healthcheck(req: Request) -> Response:
    helpers: Helpers = req.app["helpers"]
    try:
        async with await helpers.db.acquire() as connection:
            result = await connection.fetchval("SELECT true FROM conversation_reference")
    except Exception as e:
        logger.exception(f"health check failed with {type(e)}: {e}")
        raise web.HTTPInternalServerError(reason=f"{type(e)}: {e}")
    return web.json_response({"ok": result})


def create_task_log_exception(awaitable: Awaitable) -> asyncio.Task:  # type: ignore
    async def _log_exception(awaitable):
        try:
            return await awaitable
        except Exception as e:
            logger.exception(e)

    return asyncio.create_task(_log_exception(awaitable))


async def _log_exception(awaitable):
    try:
        return await awaitable
    except Exception as e:
        logger.exception(e)


async def periodic_task(app):
    async def my_periodic_task():
        helpers: Helpers = app["helpers"]
        while True:
            try:
                connection: asyncpg.pool.PoolConnectionProxy
                async with await helpers.db.acquire() as connection:
                    stmt = await connection.prepare(
                        "SELECT * FROM msg_to_delete WHERE created_at < NOW() - INTERVAL '10 seconds'"
                    )
                    async with connection.transaction():
                        async for record in stmt.cursor():
                            # print(record)
                            try:
                                await helpers.msg.delete_message(record["conv_id"], record["activity_id"])
                                await connection.execute(
                                    "DELETE FROM msg_to_delete WHERE id = $1",
                                    record["id"],
                                )
                                logger.info("deleted message %s", record["id"])
                            except Exception as e:
                                logger.exception(f"Error processing record {record['id']}: {e}")
                # logger.info("Periodic task executed")
            except Exception as e:
                logger.exception(e)
            await asyncio.sleep(30)

    # task = create_task_log_exception(my_periodic_task())
    task = asyncio.create_task(_log_exception(my_periodic_task()))

    yield

    task.cancel()
    await task


async def init_helpers(app: web.Application):
    """Initialize a connection pool."""
    try:
        helpers = Helpers(
            MessageHelper(app, ADAPTER, CONFIG),
            MSGraphHelper(app, ADAPTER, CONFIG),
            DBHelper(app, CONFIG),
        )
        app["helpers"] = helpers
        await helpers.db.check_connection()
    except Exception as e:
        logger.exception(e)
        raise e

    yield

    app["helpers"].db.close()


APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)
APP.router.add_get("/healthz", healthcheck)
APP.cleanup_ctx.append(init_helpers)
APP.cleanup_ctx.append(periodic_task)

# Create the Bot
BOT = NotiTeamsBot(APP)


if __name__ == "__main__":
    try:
        web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)
    except Exception as error:
        raise error
