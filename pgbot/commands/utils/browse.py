import discord

from pgbot import common
from pgbot.commands.base import BotException
from pgbot.utils import embed_utils


class MessageBrowser(embed_utils.PagedEmbed):
    def __init__(self, message, caller=None, command=None, start_page=0):
        super().__init__(
            message,
            [discord.embeds.EmptyEmbed] * 3,
            caller=caller,
            command=command,
            start_page=start_page,
        )

    async def setup(self, channel, quantity, before=None, after=None, around=None):
        if isinstance(before, discord.Message) and before.channel.id != channel.id:
            raise BotException(
                "Invalid `before` argument",
                "`before` has to be an ID to a message from the origin channel",
            )

        if isinstance(after, discord.Message) and after.channel.id != channel.id:
            raise BotException(
                "Invalid `after` argument",
                "`after` has to be an ID to a message from the origin channel",
            )

        if isinstance(around, discord.Message) and around.channel.id != channel.id:
            raise BotException(
                "Invalid `around` argument",
                "`around` has to be an ID to a message from the origin channel",
            )

        if quantity <= 0:
            if quantity == 0 and not after:
                raise BotException(
                    "Invalid `quantity` argument",
                    "`quantity` must be above 0 when `after=` is not specified.",
                )
            elif quantity != 0:
                raise BotException(
                    "Invalid `quantity` argument",
                    "Quantity has to be a positive integer (or `0` when `after=` is specified).",
                )

        messages = await channel.history(
            limit=quantity if quantity != 0 else None,
            before=before,
            after=after,
            around=around,
        ).flatten()

        if not messages:
            raise BotException(
                "Invalid time range",
                "No messages were found for the specified timestamps.",
            )

        if not after:
            messages.reverse()

        self.pages = []
        for message in messages:
            desc = message.system_content
            if desc is None:
                desc = message.content

            if message.embeds:
                if desc:
                    desc += f"\n{common.ZERO_SPACE}\n"
                desc += "*Message contains an embed*"

            if message.attachments:
                if desc:
                    desc += f"\n{common.ZERO_SPACE}\n"
                desc += "*Message has one or more attachments*"

            desc += "\n**━━━━━━━━━━━━**"

            timestamp = message.edited_at if message.edited_at else message.created_at

            embed = embed_utils.create(
                author_icon_url=message.author.avatar,
                author_name=message.author.display_name,
                description=desc,
                timestamp=timestamp,
                title="Original message",
                url=message.jump_url,
                footer_text=self.get_footer_text(self.current_page),
            )
            self.pages.append(embed)

        if len(self.pages) < 3:
            del self.control_emojis["first"]
            del self.control_emojis["last"]

    def get_footer_text(self, page_num: int):
        return super().get_footer_text(page_num) + "\nOriginal message sent"
