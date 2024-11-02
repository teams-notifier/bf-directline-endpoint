import json
import logging

from aiohttp import web
from botbuilder.core import ActivityHandler
from botbuilder.core import CardFactory
from botbuilder.core import TurnContext
from botbuilder.core.teams.teams_info import TeamsInfo
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import ChannelAccount
from botbuilder.schema import ResourceResponse
from opentelemetry import trace

from helpers import Helpers
from helpers.db_helper import AADOIDInfo

tracer = trace.get_tracer(__name__)


class NotiTeamsBot(ActivityHandler):
    def __init__(self, app: web.Application):
        self.app = app
        self.log = logging.getLogger(__name__)

    @property
    def helpers(self) -> Helpers:
        ret: Helpers = self.app["helpers"]
        return ret

    async def on_turn(self, turn_context: TurnContext):
        with tracer.start_as_current_span("on_turn"):
            return await super().on_turn(turn_context)

    async def on_message_reaction_activity(self, turn_context: TurnContext):
        return await super().on_message_reaction_activity(turn_context)

    async def on_event_activity(self, turn_context: TurnContext):
        return await super().on_event_activity(turn_context)

    async def on_end_of_conversation_activity(self, turn_context: TurnContext): ...

    async def on_typing_activity(self, turn_context: TurnContext):
        # print(turn_context.activity.as_dict())
        ...

    async def on_installation_update(self, turn_context: TurnContext):
        return await super().on_installation_update(turn_context)

    async def on_unrecognized_activity_type(self, turn_context: TurnContext): ...

    async def on_conversation_update_activity(self, turn_context: TurnContext):
        await self._add_conversation_reference(turn_context.activity)
        return await super().on_conversation_update_activity(turn_context)

    async def on_members_added_activity(self, members_added: list[ChannelAccount], turn_context: TurnContext):
        await self._add_conversation_reference(turn_context.activity)

    async def on_installation_update_add(self, turn_context: TurnContext):
        await self._add_conversation_reference(turn_context.activity)
        try:
            await self._on_request_token(turn_context)
        except Exception as ex:
            print(ex)

    @tracer.start_as_current_span("on_message_activity")
    async def on_message_activity(self, turn_context: TurnContext):
        await self._add_conversation_reference(turn_context.activity)

        if turn_context.activity.text:
            try:
                if turn_context.activity.conversation:
                    conversation_type = turn_context.activity.conversation.conversation_type
            except AttributeError:
                conversation_type = None
            if conversation_type in ["groupChat", "channel"]:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        attachments=[CardFactory.adaptive_card(json.load(open("cards/gretting.json")))],
                        summary="Hi, to get a token, click this message.",
                    )
                )

            elif conversation_type == "personal":
                lower_text = turn_context.activity.text.lower()
                # Other keywords will come later
                if "help" in lower_text:
                    await turn_context.send_activity(
                        Activity(
                            type=ActivityTypes.message,
                            attachments=[
                                CardFactory.adaptive_card(json.load(open("cards/gretting-personal.json")))
                            ],
                            summary="Hi, to get a token, click this message.",
                        )
                    )
                    return

        elif isinstance(turn_context.activity.value, dict):
            self.log.info(
                f"Received a message with a value: {json.dumps(turn_context.activity.value)}",
                extra={"value": json.dumps(turn_context.activity.value)},
            )
            if "action" in turn_context.activity.value:
                if turn_context.activity.value.get("action") == "requestToken":
                    await self._on_request_token(turn_context)
        else:
            # probably an event from a card
            # To be handled later
            ...

    @tracer.start_as_current_span("on_request_token")
    async def _on_request_token(self, turn_context: TurnContext):
        conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
        # self.log.info("received request for token")

        # TODO: Complete logs with trace for better context
        if turn_context.activity.channel_data is None:
            self.log.warning("token request without channel data")
            return
        if turn_context.activity.conversation is None:
            self.log.warning("token request without conversation")
            return
        if conversation_reference.user is None:
            self.log.warning("token request without conversation reference user")
            return
        if conversation_reference.conversation is None:
            self.log.warning(
                "token request without conversation reference conversation",
            )
            return

        tenant_id = turn_context.activity.channel_data.get("tenant", {}).get("id")
        token = await self.helpers.db.get_token(
            tenant_id=tenant_id,
            conversation_teams_id=turn_context.activity.conversation.id.split(";")[0],
            requester_aadoid=conversation_reference.user.aad_object_id,
            conversation_reference=conversation_reference.as_dict(),
            activity_reference=turn_context.activity.as_dict(),
        )

        conv_type = conversation_reference.conversation.conversation_type
        conversation_description = conv_type

        if conv_type == "groupChat":
            if conversation_reference.conversation.name:
                conversation_description = f"group chat named '{conversation_reference.conversation.name}'"
            else:
                conversation_members_response = await self.helpers.graph._query(
                    f"chats/{turn_context.activity.conversation.id.split(';')[0]}/members",
                )
                member_list = [
                    member.get("displayName")
                    for member in conversation_members_response.get("value", [])
                    if member.get("userId") != conversation_reference.user.aad_object_id
                ]
                member_list.sort()

                max_part = 5
                participant_count = len(member_list)
                displayed_members = ", ".join(member_list[: min(max_part, participant_count)])
                continuation_marker = ""
                if participant_count > max_part:
                    continuation_marker = "..."

                conversation_description = (
                    f"the unnamed group chat with {participant_count+1} participants "
                    f"({displayed_members}{continuation_marker} and you)"
                )
        elif conv_type == "channel":
            teamsdetails = await TeamsInfo.get_team_details(turn_context)
            conversation_description = (
                f"channel '{teamsdetails.name} > {conversation_reference.conversation.name}'"
            )
        elif conv_type == "personal":
            conversation_description = "this conversation"
        message = f"Hi there, the token to publish to {conversation_description} is:\n`{token}`\n"

        await self.helpers.msg.send_private_message(
            tenant_id=tenant_id,
            user_teams_id=conversation_reference.user.id,
            activity_to_send=message,
        )

    async def save_message_for_deletion(self, turn_context: TurnContext, response: ResourceResponse | None):
        if response is None or turn_context.activity.conversation is None:
            return
        await self.helpers.db.save_message_for_deletion(
            turn_context.activity.conversation.id,
            response.id,
        )

    @tracer.start_as_current_span("add_conversation_reference")
    async def _add_conversation_reference(self, activity: Activity):
        conversation_reference = TurnContext.get_conversation_reference(activity)

        if activity.channel_data is None:
            return

        tenant_id = activity.channel_data.get("tenant").get("id")

        # Extract from ref the user key if it as an aad => save the link
        aadoid_to_tid = set()
        if conversation_reference.user and conversation_reference.user.aad_object_id is not None:
            aadoid_to_tid.add(
                AADOIDInfo(
                    aad_iod=conversation_reference.user.aad_object_id,
                    tenant_id=tenant_id,
                    teams_id=conversation_reference.user.id,
                    name=conversation_reference.user.name,
                )
            )

        if activity.members_added:
            for member in activity.members_added:
                if member.aad_object_id is not None:
                    aadoid_to_tid.add(
                        AADOIDInfo(
                            aad_iod=member.aad_object_id,
                            tenant_id=tenant_id,
                            teams_id=member.id,
                            name=member.name,
                        )
                    )

        if activity.members_removed:
            for member in activity.members_removed:
                if member.aad_object_id is not None:
                    aadoid_to_tid.add(
                        AADOIDInfo(
                            aad_iod=member.aad_object_id,
                            tenant_id=tenant_id,
                            teams_id=member.id,
                            name=member.name,
                        )
                    )

        if activity.from_property is not None and activity.from_property.aad_object_id is not None:
            aadoid_to_tid.add(
                AADOIDInfo(
                    aad_iod=activity.from_property.aad_object_id,
                    tenant_id=tenant_id,
                    teams_id=activity.from_property.id,
                    name=activity.from_property.name,
                )
            )

        for aadoid_ref in aadoid_to_tid:
            await self.helpers.db.save_aadoid_to_tid(aadoid_ref)
