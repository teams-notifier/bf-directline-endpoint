from aiohttp import web
from botbuilder.integration.aiohttp import CloudAdapter
from botbuilder.schema import Activity
from botbuilder.schema import ChannelAccount
from botbuilder.schema import ConversationParameters
from botbuilder.schema import ResourceResponse
from botframework.connector.aio import ConnectorClient
from botframework.connector.auth import AuthenticationConstants
from opentelemetry import trace

from config import DefaultConfig

tracer = trace.get_tracer(__name__)


class MessageHelper:
    def __init__(self, app: web.Application, adapter: CloudAdapter, config: DefaultConfig) -> None:
        self._app = app
        self._config = config
        self._adapter = adapter
        self._connector_client_inst: ConnectorClient | None = None

    async def _connector_client(self) -> ConnectorClient:
        if self._connector_client_inst is None:
            service_url = "https://smba.trafficmanager.net/amer/"
            claims_identity = self._adapter.create_claims_identity(self._config.APP_ID)
            claims_identity.claims[AuthenticationConstants.SERVICE_URL_CLAIM] = service_url
            connector_factory = self._adapter.bot_framework_authentication.create_connector_factory(
                claims_identity
            )
            self._connector_client_inst = await connector_factory.create(service_url, "")
        return self._connector_client_inst

    async def delete_message(self, conversation_id: str, activity_id: str):
        client = await self._connector_client()
        await client.conversations.delete_activity(conversation_id, activity_id)

    @tracer.start_as_current_span("send_private_message")
    async def send_private_message(
        self,
        tenant_id: str,
        user_teams_id: str,
        activity_to_send: Activity | str,
    ) -> str | None:
        activity_response: ResourceResponse | None = None

        @tracer.start_as_current_span("send_activity")
        async def send_activity(turn_context):
            nonlocal activity_response
            response = await turn_context.send_activity(activity_to_send)
            activity_response = response

        with tracer.start_as_current_span("create_conversation") as span:
            await self._adapter.create_conversation(
                self._config.APP_ID,
                send_activity,
                conversation_parameters=ConversationParameters(
                    bot=ChannelAccount(id=self._config.APP_ID),
                    members=[
                        ChannelAccount(
                            id=user_teams_id,
                        )
                    ],
                    is_group=False,
                    tenant_id=tenant_id,
                ),
                service_url="https://smba.trafficmanager.net/amer/",
            )
            if activity_response is not None:
                assert isinstance(activity_response, ResourceResponse)
                span.set_attribute("teams.activity_id", activity_response.id)
                if isinstance(activity_response.id, str):
                    return activity_response.id
                else:
                    return str(activity_response.id)
            return None
