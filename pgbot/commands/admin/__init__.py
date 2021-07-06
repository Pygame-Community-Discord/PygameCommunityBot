"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file exports the main AdminCommand class
"""

from __future__ import annotations

import asyncio
import datetime
import io
import os
import time
from typing import Optional, Union

import black
import discord
import psutil
import pygame

from pgbot import common, db
from pgbot.commands.admin.emsudo import EmsudoCommand
from pgbot.commands.admin.sudo import SudoCommand
from pgbot.commands.base import BotException, CodeBlock, String, add_group, no_dm
from pgbot.commands.user import UserCommand
from pgbot.utils import embed_utils, utils

process = psutil.Process(os.getpid())


class AdminCommand(UserCommand, SudoCommand, EmsudoCommand):
    """
    Base class for all admin commands
    """

    async def cmd_test_parser(self, *args, **kwargs):
        """
        ->skip
        """
        out = ""
        if args:
            out += "__**Args:**__\n"

        for cnt, arg in enumerate(args):
            if isinstance(arg, CodeBlock):
                out += f"{cnt} - Codeblock\n" + utils.code_block(
                    arg.code, code_type=arg.lang
                )
            elif isinstance(arg, String):
                out += (
                    f"{cnt} - String\n> " + "\n> ".join(arg.string.splitlines()) + "\n"
                )
            elif isinstance(arg, tuple):
                out += (
                    f"{cnt} - tuple\n {utils.code_block(repr(arg), code_type='py')}\n"
                )
            else:
                out += f"{cnt} - arg\n> {arg}\n"

        out += "\n"
        if kwargs:
            out += "__**Kwargs:**__\n\n"

        for name, arg in kwargs.items():
            if isinstance(arg, CodeBlock):
                out += f"{name} - Codeblock\n" + utils.code_block(
                    arg.code, code_type=arg.lang
                )
            elif isinstance(arg, String):
                out += (
                    f"{name} - String\n> " + "\n>".join(arg.string.splitlines()) + "\n"
                )
            elif isinstance(arg, tuple):
                out += (
                    f"{name} - tuple\n {utils.code_block(repr(arg), code_type='py')}\n"
                )
            else:
                out += f"{name} - arg\n> {arg}\n"

        out += "\n"
        await embed_utils.replace(
            self.response_msg,
            title="Here are the args and kwargs you passed",
            description=out,
        )

    @add_group("db")
    async def cmd_db(self):
        """
        ->type Admin commands
        ->signature pg!db
        ->description List contents of DB (table names)
        -----
        Implement pg!db, list contents of DB
        """

        await embed_utils.replace(
            self.response_msg, title="Tables:", description="\n".join(db.db_obj_cache)
        )

    @add_group("db", "read")
    async def cmd_db_read(self, name: str):
        """
        ->type Admin commands
        ->signature pg!db read <name>
        ->description Visualize DB
        -----
        Implement pg!db_read, to visualise DB messages
        """
        async with db.DiscordDB(name) as db_obj:
            str_obj = black.format_str(
                repr(db_obj.get()),
                mode=black.FileMode(),
            )

        with io.StringIO(str_obj) as fobj:
            await self.channel.send(
                f"Here are the contents of the table `{name}`:",
                file=discord.File(fobj, filename=f"{name}_db.py"),
            )

        try:
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @no_dm
    @add_group("db", "write")
    async def cmd_db_write(self, name: str, data: Union[discord.Message, CodeBlock]):
        """
        ->type Admin commands
        ->signature pg!db write <name> <data>
        ->description Overwrite DB. Do not use unless you know what you are doing
        -----
        Implement pg!db_write, to overwrite DB messages
        """
        # make typecheckers happy
        if not isinstance(self.author, discord.Member):
            return

        evalable = False
        for role in self.author.roles:
            if role.id in common.ServerConstants.EVAL_ROLES:
                evalable = True

        if common.TEST_MODE and self.author.id in common.TEST_USER_IDS:
            evalable = True

        if not evalable:
            raise BotException(
                "Insufficient permissions",
                "You do not have enough permissions to run this command.",
            )

        if isinstance(data, CodeBlock):
            obj_str = data.code
        elif data.attachments:
            obj_str = (await data.attachments[0].read()).decode()
        else:
            raise BotException(
                "Failed to overwrite DB", "File attachment was not found"
            )

        async with db.DiscordDB(name) as db_obj:
            db_obj.write(eval(obj_str))  # pylint: disable = eval-used

        await embed_utils.replace(
            self.response_msg,
            title="DB overwritten!",
            description="DB contents have been overwritten successfully",
        )

    @add_group("db", "del")
    async def cmd_db_del(self, name: str):
        """
        ->type Admin commands
        ->signature pg!db del <name>
        ->description Delete DB. Do not use unless you know what you are doing
        -----
        Implement pg!db_del, to delete DB messages
        """

        async with db.DiscordDB(name) as db_obj:
            if not db_obj.delete():
                raise BotException("Could not delete DB", "No such DB exists")

        await embed_utils.replace(
            self.response_msg,
            title="DB has been deleted!",
            description="DB contents have been deleted successfully",
        )

    async def cmd_whitelist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!whitelist_cmd [*cmds]
        ->description Whitelist commands
        -----
        Implement pg!whitelist_cmd, to whitelist commands
        """
        async with db.DiscordDB("blacklist") as db_obj:
            commands = db_obj.get([])
            cnt = 0
            for cmd in cmds:
                if cmd in commands:
                    cnt += 1
                    commands.remove(cmd)

            db_obj.write(commands)

        await embed_utils.replace(
            self.response_msg,
            title="Whitelisted!",
            description=f"Successfully whitelisted {cnt} command(s)",
        )

    async def cmd_blacklist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!blacklist_cmd [*cmds]
        ->description Blacklist commands
        -----
        Implement pg!blacklist_cmd, to blacklist commands
        """
        async with db.DiscordDB("blacklist") as db_obj:
            commands = db_obj.get([])

            cnt = 0
            for cmd in cmds:
                if cmd not in commands and cmd != "whitelist_cmd":
                    cnt += 1
                    commands.append(cmd)

            db_obj.write(commands)

        await embed_utils.replace(
            self.response_msg,
            title="Blacklisted!",
            description=f"Successfully blacklisted {cnt} command(s)",
        )

    async def cmd_clock(
        self,
        action: str = "",
        timezone: float = 0,
        color: Optional[pygame.Color] = None,
        member: Optional[discord.Member] = None,
    ):
        """
        ->type Get help
        ->signature pg!clock [action=""] [timezone=] [color=] [member=]
        ->description 24 Hour Clock showing <@&778205389942030377> s who are available to help
        ->extended description
        Admins can run clock with more arguments, to add/update/remove other members.
        `pg!clock update [timezone in hours] [color as hex string] [mention member]`
        `pg!clock remove [mention member]`
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        return await super().cmd_clock(action, timezone, color, _member=member)

    @no_dm
    async def cmd_eval(self, code: CodeBlock):
        """
        ->type Admin commands
        ->signature pg!eval <command>
        ->description Execute a line of command without restrictions
        -----
        Implement pg!eval, for admins to run arbitrary code on the bot
        """
        # make typecheckers happy
        if not isinstance(self.author, discord.Member):
            return

        evalable = False
        for role in self.author.roles:
            if role.id in common.ServerConstants.EVAL_ROLES:
                evalable = True

        if common.TEST_MODE and self.author.id in common.TEST_USER_IDS:
            evalable = True

        if not evalable:
            raise BotException(
                "Insufficient permissions",
                "You do not have enough permissions to run this command.",
            )

        try:
            script = compile(code.code, "<string>", "eval")  # compile script

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            total = time.perf_counter() - script_start

        except Exception as ex:
            raise BotException(
                "An exception occured:",
                utils.code_block(
                    type(ex).__name__ + ": " + ", ".join(map(str, ex.args))
                ),
            )

        await embed_utils.replace(
            self.response_msg,
            title=f"Return output (code executed in {utils.format_time(total)}):",
            description=utils.code_block(repr(eval_output)),
        )

    async def cmd_heap(self):
        """
        ->type Admin commands
        ->signature pg!heap
        ->description Show the memory usage of the bot
        -----
        Implement pg!heap, for admins to check memory taken up by the bot
        """
        mem = process.memory_info().rss
        await embed_utils.replace(
            self.response_msg,
            title="Total memory used:",
            description=f"**{utils.format_byte(mem, 4)}**\n({mem} B)",
        )

    async def cmd_stop(self):
        """
        ->type Admin commands
        ->signature pg!stop [*ids]
        ->description Stop the bot
        ->extended description
        Any additional arguments are IDs of members running test bots, to stop
        the test bots of particular wizards
        -----
        The actual pg!stop function is implemented elsewhere, this is just
        a stub for the docs
        """

    async def cmd_archive(
        self,
        origin: discord.TextChannel,
        quantity: int,
        mode: int = 0,
        destination: Optional[common.Channel] = None,
        before: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        after: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        around: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        raw: bool = False,
        show_header: bool = True,
        show_author: bool = True,
        divider: String = String("-" * 56),
        group_by_author: bool = True,
        oldest_first: bool = True,
        same_channel: bool = False,
    ):
        """
        ->type Admin commands
        ->signature pg!archive <origin> <quantity> [mode=0] [destination=]
        [before=] [after=] [around=] [raw=False] [show_header=True] [show_author=True]
        [divider=("-"*56)] [group_by_author=True] [oldest_first=True] [same_channel=False]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """
        if destination is None:
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author,
            origin,
            permissions=("view_channel",),
        ) or not utils.check_channel_permissions(
            self.author,
            destination,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel(s).",
            )

        archive_header_msg = None
        archive_header_msg_embed = None

        if origin.id == destination.id and not same_channel:
            raise BotException(
                "Cannot execute command:", "Origin and destination channels are same"
            )

        datetime_format_str = "%a, %d %b %Y - %H:%M:%S (UTC)"
        divider_str = divider.string

        if (
            isinstance(before, discord.PartialMessage)
            and before.channel.id != origin.id
        ):
            raise BotException(
                "Invalid `before` argument",
                "`before` has to be an ID to a message from the origin channel",
            )

        if isinstance(after, discord.PartialMessage) and after.channel.id != origin.id:
            raise BotException(
                "Invalid `after` argument",
                "`after` has to be an ID to a message from the origin channel",
            )

        if (
            isinstance(around, discord.PartialMessage)
            and around.channel.id != origin.id
        ):
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

        await destination.trigger_typing()
        messages = await origin.history(
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

        if not after and oldest_first:
            messages.reverse()

        if show_header and not raw:
            start_date = messages[0].created_at
            end_date = messages[-1].created_at

            if start_date == end_date:
                msg = f"On {utils.format_datetime(start_date)}"
            else:
                msg = (
                    f"From\n> {utils.format_datetime(start_date)}\n"
                    f"To\n> {utils.format_datetime(end_date)}"
                )

            archive_header_msg_embed = embed_utils.create(
                title=f"__Archive of `#{origin.name}`__",
                description=f"\nAn archive of **{origin.mention}** "
                f"({len(messages)} message(s))\n\n" + msg,
                color=0xFFFFFF,
                footer_text="Status: Incomplete",
            )

            archive_header_msg = await destination.send(embed=archive_header_msg_embed)

        no_mentions = discord.AllowedMentions.none()

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )
        msg_count = len(messages)
        with io.StringIO("This file was too large to be archived.") as fobj:
            for i, msg in enumerate(
                reversed(messages) if not oldest_first else messages
            ):
                if msg_count > 2 and not i % 2:
                    await embed_utils.edit_field_from_dict(
                        self.response_msg,
                        load_embed,
                        dict(
                            name="Archiving Messages",
                            value=f"`{i}/{msg_count}` messages archived\n"
                            f"{(i / msg_count) * 100:.01f}% | "
                            + utils.progress_bar(i / msg_count, divisions=30),
                        ),
                        0,
                    )
                author = msg.author
                await destination.trigger_typing()

                fobj.seek(0)
                attached_files = [
                    (
                        await a.to_file(spoiler=a.is_spoiler())
                        if a.size <= self.filesize_limit
                        else discord.File(fobj, f"filetoolarge - {a.filename}.txt")
                    )
                    for a in msg.attachments
                ]

                if not raw:
                    author_embed = None
                    current_divider_str = divider_str
                    if show_author or divider_str:
                        if (
                            group_by_author
                            and i > 0
                            and messages[i - 1].author == author
                        ):
                            # no author info or divider for mesmages next to each other sharing an author
                            current_divider_str = None
                        else:
                            author_embed = embed_utils.create(
                                description=f"{author.mention}"
                                f" (`{author.name}#{author.discriminator}`)\n"
                                f"ID: `{author.id}`\u2800|\u2800**[View Original]({msg.jump_url})**",
                                color=0x36393F,
                                footer_text="\nISO Time: "
                                f"{msg.created_at.replace(tzinfo=None).isoformat()}",
                                timestamp=msg.created_at.replace(
                                    tzinfo=datetime.timezone.utc
                                ),
                                footer_icon_url=str(author.avatar_url),
                            )

                        if author_embed or current_divider_str:
                            await destination.send(
                                content=current_divider_str,
                                embed=author_embed,
                                allowed_mentions=no_mentions,
                            )

                if not mode:
                    if msg.content or msg.embeds or attached_files:
                        msg_embed = msg.embeds[0] if msg.embeds else None
                        msg_embed_dict = (
                            msg_embed.to_dict() if msg_embed is not None else None
                        )

                        if (
                            msg_embed_dict
                            and "type" in msg_embed_dict
                            and msg_embed_dict["type"] == "gifv"
                        ):
                            msg_embed = None

                        if len(msg.content) > 2000:
                            start_idx = 0
                            stop_idx = 0
                            for i in range(len(msg.content) // 2000):
                                start_idx = 2000 * i
                                stop_idx = 2000 + 2000 * i

                                if not i:
                                    await destination.send(
                                        content=msg.content[start_idx:stop_idx],
                                        allowed_mentions=no_mentions,
                                    )
                                else:
                                    await destination.send(
                                        content=msg.content[start_idx:stop_idx],
                                        allowed_mentions=no_mentions,
                                    )

                            with io.StringIO(msg.content) as fobj:
                                await destination.send(
                                    content=msg.content[stop_idx:],
                                    embed=embed_utils.create(
                                        footer_text="Full message data"
                                    ),
                                    file=discord.File(fobj, filename="messagedata.txt"),
                                    allowed_mentions=no_mentions,
                                )

                            await destination.send(
                                embed=msg_embed,
                                file=attached_files[0] if attached_files else None,
                            )
                        else:
                            await destination.send(
                                content=msg.content,
                                embed=msg_embed,
                                file=attached_files[0] if attached_files else None,
                                allowed_mentions=no_mentions,
                            )

                    elif msg.type == discord.MessageType.pins_add:
                        await destination.send(
                            content=f"{msg.author.name}#{msg.author.discriminator} pinned a message in #{origin.name}"
                        )

                    elif msg.type == discord.MessageType.premium_guild_subscription:
                        await destination.send(
                            content=f"{msg.author.name}#{msg.author.discriminator} just boosted this server!"
                        )

                    if len(attached_files) > 1:
                        for i in range(1, len(attached_files)):
                            await destination.send(
                                content=f"**Message attachment** ({i + 1}):",
                                file=attached_files[i],
                            )

                    for i in range(1, len(msg.embeds)):
                        if not i % 3:
                            await destination.trigger_typing()
                        await destination.send(embed=msg.embeds[i])

                elif mode == 1:
                    if msg.content:
                        escaped_msg_content = msg.content.replace("```", "\\`\\`\\`")
                        if len(msg.content) > 2000 or len(escaped_msg_content) > 2000:
                            with io.StringIO(msg.content) as fobj:
                                await destination.send(
                                    file=discord.File(fobj, "messagedata.txt"),
                                )
                        else:
                            await embed_utils.send(
                                self.channel,
                                description="```\n{0}```".format(escaped_msg_content),
                            )

                    if attached_files:
                        for i in range(len(attached_files)):
                            await destination.send(
                                content=f"**Message attachment** ({i + 1}):",
                                file=attached_files[i],
                            )

                    if msg.embeds:
                        embed_data_fobjs = []
                        for embed in msg.embeds:
                            embed_data_fobj = io.StringIO()
                            embed_utils.export_embed_data(
                                embed.to_dict(),
                                fp=embed_data_fobj,
                                indent=4,
                                as_json=True,
                            )
                            embed_data_fobj.seek(0)
                            embed_data_fobjs.append(embed_data_fobj)

                        for i in range(len(embed_data_fobjs)):
                            await destination.send(
                                content=f"**Message embed** ({i + 1}):",
                                file=discord.File(
                                    embed_data_fobjs[i], filename="embeddata.json"
                                ),
                            )

                        for embed_data_fobj in embed_data_fobjs:
                            embed_data_fobj.close()

                elif mode == 2:
                    if msg.content:
                        with io.StringIO(msg.content) as fobj2:
                            await destination.send(
                                file=discord.File(fobj2, filename="messagedata.txt"),
                                allowed_mentions=no_mentions,
                            )

                    if attached_files:
                        for i in range(len(attached_files)):
                            await destination.send(
                                content=f"**Message attachment** ({i + 1}):",
                                file=attached_files[i],
                            )

                    if msg.embeds:
                        embed_data_fobjs = []
                        for embed in msg.embeds:
                            embed_data_fobj = io.StringIO()
                            embed_utils.export_embed_data(
                                embed.to_dict(),
                                fp=embed_data_fobj,
                                indent=4,
                                as_json=True,
                            )
                            embed_data_fobj.seek(0)
                            embed_data_fobjs.append(embed_data_fobj)

                        for i in range(len(embed_data_fobjs)):
                            await destination.send(
                                content=f"**Message embed** ({i + 1}):",
                                file=discord.File(
                                    embed_data_fobjs[i], filename="embeddata.json"
                                ),
                            )

                        for embed_data_fobj in embed_data_fobjs:
                            embed_data_fobj.close()

                await asyncio.sleep(0)

        if divider_str and not raw:
            await destination.send(content=divider_str)

        if show_header and not raw:
            archive_header_msg_embed.set_footer(text="Status: Complete")
            if archive_header_msg is not None:
                await embed_utils.replace_from_dict(
                    archive_header_msg, archive_header_msg_embed.to_dict()
                )

        await embed_utils.edit_field_from_dict(
            self.response_msg,
            load_embed,
            dict(
                name=f"Successfully archived {msg_count} message(s)",
                value=f"`{msg_count}/{msg_count}` messages archived\n"
                "100% | " + utils.progress_bar(1.0, divisions=30),
            ),
            0,
        )

        try:
            await self.response_msg.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("pin")
    async def cmd_pin(
        self,
        channel: discord.TextChannel,
        *msgs: discord.PartialMessage,
        delete_system_messages: bool = True,
        flush_bottom: bool = True,
    ):
        """
        ->type Admin commands
        ->signature pg!pin <channel> <message> <message>... [pin_info=False] [flush_bottom=True]
        ->description Pin a message in the specified channel.
        ->example command pg!pin 123412345567891 23456234567834567 3456734523456734567...
        """

        if not utils.check_channel_permissions(
            self.author,
            channel,
            permissions=("view_channel", "manage_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No message IDs given as input.",
            )
        elif len(msgs) > 50:
            raise BotException(
                "Too many arguments!",
                "Cannot pin more than 50 messages in a channel.",
            )

        elif not all(msg.channel.id == channel.id for msg in msgs):
            raise BotException(
                "Invalid message ID(s) given as input",
                "Each ID must be from a message in the given target channel",
            )

        pinned_msgs = await channel.pins()

        unpin_count = max((len(pinned_msgs) + len(msgs)) - 50, 0)
        if unpin_count > 0:
            for i in range(unpin_count):
                try:
                    await pinned_msgs[i].unpin()
                except discord.HTTPException as e:
                    raise BotException(f"Cannot unpin message at index {i}!", e.args[0])

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )
        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i / msg_count) * 100:.01f}% | "
                        + utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )
            try:
                await msg.pin()
            except discord.HTTPException as e:
                raise BotException(f"Cannot pin input message {i}!", e.args[0])

            if delete_system_messages:
                try:
                    await (
                        await channel.fetch_message(channel.last_message_id)
                    ).delete()
                except (discord.HTTPException, discord.NotFound):
                    pass

            await asyncio.sleep(0)

        await embed_utils.edit_field_from_dict(
            self.response_msg,
            load_embed,
            dict(
                name=f"Sucessfully pinned {msg_count} message(s) ({unpin_count} removed)!",
                value=f"`{msg_count}/{msg_count}` messages pinned\n"
                "100% | " + utils.progress_bar(1.0, divisions=30),
            ),
            0,
        )

        try:
            if not delete_system_messages:
                await self.invoke_msg.delete()
            await self.response_msg.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("pin", "remove")
    async def cmd_pin_remove(
        self,
        channel: discord.TextChannel,
        *msgs: discord.PartialMessage,
    ):
        """
        ->type Admin commands
        ->signature pg!pin remove <channel> <message> <message>...
        ->description Unpin a message in the specified channel.
        ->example command pg!unpin #general 23456234567834567 3456734523456734567...
        """

        if not utils.check_channel_permissions(
            self.author,
            channel,
            permissions=("view_channel", "manage_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No message IDs given as input.",
            )
        elif len(msgs) > 50:
            raise BotException(
                "Too many arguments!",
                "No more than 50 messages can be pinned in a channel.",
            )
        elif not all(msg.channel.id == channel.id for msg in msgs):
            raise BotException(
                "Invalid message ID(s) given as input",
                "Each ID must be from a message in the given target channel",
            )

        pinned_msgs = await channel.pins()
        pinned_msg_id_set = set(msg.id for msg in pinned_msgs)

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i / msg_count) * 100:.01f}% | "
                        + utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )

            if msg.id in pinned_msg_id_set:
                try:
                    await msg.unpin()
                except discord.HTTPException as e:
                    raise BotException(f"Cannot unpin input message {i}!", e.args[0])

            await asyncio.sleep(0)

        await embed_utils.edit_field_from_dict(
            self.response_msg,
            load_embed,
            dict(
                name=f"Succesfully unpinned {msg_count} message(s)!",
                value=f"`{msg_count}/{msg_count}` messages processed\n"
                "100% | " + utils.progress_bar(1.0, divisions=30),
            ),
            0,
        )

        try:
            await self.response_msg.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("pin", "remove", "at")
    async def cmd_pin_remove_at(
        self,
        channel: discord.TextChannel,
        *indices: Union[int, range],
    ):
        """
        ->type Admin commands
        ->signature pg!pin remove at <channel> <index/range> ...
        ->description Unpin a message in the specified channel.
        ->example command pg!pin remove at #general 3.. range(9, 15)..
        """

        if not utils.check_channel_permissions(
            self.author,
            channel,
            permissions=("view_channel", "manage_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not indices:
            raise BotException(
                "Invalid arguments!",
                "No channel pin list indices given as input.",
            )

        pinned_msgs = await channel.pins()

        pinned_msg_count = len(pinned_msgs)

        if not pinned_msgs:
            raise BotException(
                "No messages to unpin!",
                "No messages are currently pinned on the specified channel.",
            )

        unpinned_msg_id_set = set()

        indices_list = []

        for index in indices:
            if isinstance(index, range):
                if len(index) > 50:
                    raise BotException(
                        "Invalid range object!",
                        "The given range object must not contain more than 50 integers.",
                    )
                else:
                    indices_list.extend(index)

            else:
                indices_list.append(index)

        indices_list = sorted(set(indices_list))
        indices_list.reverse()

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )

        idx_count = len(indices_list)
        for i, unpin_index in enumerate(indices_list):
            if unpin_index < 0:
                unpin_index = pinned_msg_count + unpin_index

            if idx_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{idx_count}` messages processed\n"
                        f"{(i / idx_count) * 100:.01f}% | "
                        + utils.progress_bar(i / idx_count, divisions=30),
                    ),
                    0,
                )

            if 0 <= unpin_index < pinned_msg_count:
                msg = pinned_msgs[unpin_index]

                if msg.id not in unpinned_msg_id_set:
                    try:
                        await msg.unpin()
                        unpinned_msg_id_set.add(msg.id)
                    except discord.HTTPException as e:
                        raise BotException(
                            f"Cannot unpin input message {i}!", e.args[0]
                        )

            await asyncio.sleep(0)

        await embed_utils.edit_field_from_dict(
            self.response_msg,
            load_embed,
            dict(
                name=f"Succesfully unpinned {idx_count} message(s)!",
                value=f"`{idx_count}/{idx_count}` messages processed\n"
                "100% | " + utils.progress_bar(1.0, divisions=30),
            ),
            0,
        )

        try:
            await self.response_msg.delete(delay=10.0 if idx_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @no_dm
    @add_group("poll")
    async def cmd_poll(
        self,
        desc: String,
        *emojis: tuple[str, String],
        destination: Optional[common.Channel] = None,
        author: Optional[String] = None,
        color: Optional[pygame.Color] = None,
        url: Optional[String] = None,
        img_url: Optional[String] = None,
        thumbnail: Optional[String] = None,
        multi_votes: bool = False,
    ):
        """
        ->type Other commands
        ->signature pg!poll <description> [*emojis] [author] [color] [url] [image_url] [thumbnail] [multi_votes=True]
        ->description Start a poll.
        ->extended description
        The args must series of two element tuples, first element being emoji,
        and second being the description (see example command).
        The emoji must be a default emoji or one from this server. To close the poll see pg!close_poll.
        Additionally admins can specify some keyword arguments to improve the appearance of the poll
        A `multi_votes` arg can also be passed indicating if the user can cast multiple votes in a poll or not
        ->example command pg!poll "Which apple is better?" ( 🍎 "Red apple") ( 🍏 "Green apple")
        """

        if not isinstance(destination, discord.TextChannel):
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author,
            destination,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        embed_dict = {}
        if author:
            embed_dict["author"] = {"name": author.string}

        if color:
            embed_dict["color"] = utils.color_to_rgb_int(color)

        if url:
            embed_dict["url"] = url.string

        if img_url:
            embed_dict["image"] = {"url": img_url.string}

        if thumbnail:
            embed_dict["thumbnail"] = {"url": thumbnail.string}

        return await super().cmd_poll(
            desc,
            *emojis,
            _destination=destination,
            _admin_embed_dict=embed_dict,
            multi_votes=multi_votes,
        )

    @no_dm
    @add_group("poll", "close")
    async def cmd_poll_close(
        self,
        msg: discord.Message,
        color: pygame.Color = pygame.Color("#A83232"),
    ):
        """
        ->type Other commands
        ->signature pg!poll close <msg> [color]
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        The color is the color of the closed poll embed
        """
        return await super().cmd_poll_close(msg, _color=color)

    @add_group("stream", "add")
    async def cmd_stream_add(self, *members: discord.Member):
        """
        ->type Reminders
        ->signature pg!stream add [*members]
        ->description Add user(s) to the ping list for stream
        ->extended description
        The command give mods the chance to add users to the ping list manually.
        Without arguments, equivalent to the "user" version of this command
        """
        await super().cmd_stream_add(_members=members if members else None)

    @add_group("stream", "del")
    async def cmd_stream_del(self, *members: discord.Member):
        """
        ->type Reminders
        ->signature pg!stream del [*members]
        ->description Remove user(s) to the ping list for stream
        ->extended description
        The command give mods the chance to remove users from the ping list manually.
        Without arguments, equivalent to the "user" version of this command
        """
        await super().cmd_stream_del(_members=members if members else None)

    @add_group("info")
    async def cmd_info(
        self,
        *objs: Union[discord.Message, discord.Member, discord.User],
        author: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!info <*objects> [author=True]
        ->description Get information about a Discord message/user/member

        ->extended description
        Return an information embed for the given Discord objects.

        __Args__:
            `*objects: (Message|User|Member)`
            > A sequence of Discord ojbects whose info
            > should be retrieved. If no input is given,
            > an information embed on the

            `author_info: (bool) = True`
            > If set to `True`, extra information about
            > the authors of any message given as input
            > will be added to their info embeds.

        __Returns__:
            > One or more embeds containing information about
            > the given inputs.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """

        checked_channels = set()
        for i, obj in enumerate(objs):
            if isinstance(obj, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    obj.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command on the specified channel.",
                    )
                else:
                    checked_channels.add(obj.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not objs:
            obj = self.author
            embed = embed_utils.get_member_info_embed(obj)
            await self.channel.send(embed=embed)

        load_embed = embed_utils.create(
            title="Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )
        obj_count = len(objs)
        for i, obj in enumerate(objs):
            if obj_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{obj_count}` inputs processed\n"
                        f"{(i / obj_count) * 100:.01f}% | "
                        + utils.progress_bar(i / obj_count, divisions=30),
                    ),
                    0,
                )
            await self.channel.trigger_typing()
            embed = None
            if isinstance(obj, discord.Message):
                embed = embed_utils.get_msg_info_embed(obj, author=author)

            elif isinstance(obj, (discord.Member, discord.User)):
                embed = embed_utils.get_member_info_embed(obj)

            if embed is not None:
                await self.channel.send(embed=embed)

            await asyncio.sleep(0)

        if obj_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Complete",
                    value=f"`{obj_count}/{obj_count}` inputs processed\n"
                    "100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        try:
            await self.response_msg.delete(delay=10.0 if obj_count > 1 else 0.0)
        except discord.NotFound:
            pass

    @add_group("info", "server")
    async def cmd_info_server(self, guild: Optional[discord.Guild] = None):
        """
        ->type More admin commands
        ->signature pg!info server [guild_id=None]
        ->description Get information about a Discord server

        ->extended description
        Return an information embed for the Discord server ID given

        __Args__:
            `guild_id: (int) = None`
            > An integer that should represent
            > a server's ID. If no input is given,
            > the server would be set to the server
            > where the command was invoked

        __Returns__:
            > An embed with the given server's information

        __Raises__:
            > `BotException`: The guild either doesn't exist or is private
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """
        if guild is None:
            guild = self.get_guild()

        description = (
            f"Server Name: `{guild.name}`\n"
            f"Server ID: `{guild.id}`\n"
            f"Created At: {utils.format_datetime(guild.created_at)}\n"
        )

        description += f"Number of Members: `{guild.member_count}`\n"

        number_of_bots = len([i for i in guild.members if i.bot])
        number_of_members = len(guild.members) - number_of_bots
        description += f"> - `{number_of_members}` humans\n"
        description += f"> - `{number_of_bots}` bots\n"

        description += f"Number of Channels: `{len(guild.channels)}`\n"

        description += f"Number of Roles: `{len(guild.roles)}`\n"

        if guild.premium_subscription_count != 0:
            description += (
                f"Number of Server Boosts: `{guild.premium_subscription_count}`\n"
            )

        if guild.owner is not None:
            description += (
                f"Owner of Server: `{guild.owner.name}#{guild.owner.discriminator}`\n"
            )

        kwargs = {
            "title": f"Server information for {guild.name}:",
            "thumbnail_url": guild.icon_url,
            "description": description,
        }

        await embed_utils.replace(self.response_msg, **kwargs)

    async def cmd_react(self, message: discord.PartialMessage, *emojis: str):
        """
        ->type More admin commands
        ->signature pg!react <message> <emojis>
        ->description Reacts to a Discord message

        ->extended description
        Reacts to a Discord message with the given emojis.

        __Args__:
            `*objects: Message`
            > A Discord message that reactions should be added to.

            `emojis: str`
            > The emojis to react with, separated by spaces.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException as e:
                e.args = (
                    e.args[0]
                    + "\n\nYou gave me some invalid emojis or I am unable to use them here. "
                    "Remember the emojis have to be separated by spaces. Find help in "
                    "`pg!help react`",
                )
                raise
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    async def cmd_feature(
        self, name: str, *channels: common.Channel, disable: bool = True
    ):
        """
        ->type More admin commands
        ->signature pg!feature <name> [*channels] [enable=True]
        ->description Per channel finer control on bot features

        ->extended description

        __Args__:
            `name: (str)`
            > The name of the feature

            `*channels: (common.Channel)`
            > Series of channel mentions to apply the
            > settings to. If empty, applies the feature
            > to the current channel

            `disable: bool = True`
            > Bool that controls whether to disable the
            > feature or not (enable). `True` by default
        -----
        """
        if not channels:
            channels = (self.channel,)

        async with db.DiscordDB("feature") as db_obj:
            db_dict = db_obj.get({})
            if name not in db_dict:
                db_dict[name] = {}

            for chan in channels:
                db_dict[name][chan.id] = disable

            db_obj.write(db_dict)

        await embed_utils.replace(
            self.response_msg,
            title="Successfully executed command!",
            description=f"Changed settings on {len(channels)} channel(s)",
        )


# monkey-patch admin command names into tuple
common.admin_commands = tuple(
    (
        i[len(common.CMD_FUNC_PREFIX) :]
        for i in dir(AdminCommand)
        if i.startswith(common.CMD_FUNC_PREFIX)
    )
)
