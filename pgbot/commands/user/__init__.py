"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the user commands of the bot
"""

from __future__ import annotations

import copy
import datetime
import io
import os
import re
import time
from typing import Any, Optional, Union

import discord
import pygame

from pgbot import common, db
from pgbot.commands.base import (
    BotException,
    CodeBlock,
    String,
    add_group,
    no_dm,
)
from pgbot.commands.utils import sandbox
from pgbot.utils import embed_utils, utils

from .fun_commands import FunCommand
from .help_commands import HelpCommand


class UserCommand(FunCommand, HelpCommand):
    """Base class to handle user commands."""

    @add_group("reminders", "add")
    async def cmd_reminders_add(
        self,
        msg: String,
        on: datetime.datetime,
        *,
        _delta: Optional[datetime.timedelta] = None,
    ):
        """
        ->type Reminders
        ->signature pg!reminders add <message> <datetime in iso format>
        ->description Set a reminder to yourself
        ->extended description
        Allows you to set a reminder to yourself
        The date-time must be an ISO time formatted string, in UTC time
        string
        ->example command pg!reminders add "do the thing" "2034-10-26 11:19:36"
        -----
        Implement pg!reminders_add, for users to set reminders for themselves
        """

        if _delta is None:
            now = datetime.datetime.utcnow()
            _delta = on - now
        else:
            now = on
            on = now + _delta

        if on < now:
            raise BotException(
                "Failed to set reminder!",
                "Time cannot go backwards, negative time does not make sense..."
                "\n Or does it? \\*vsauce music plays in the background\\*",
            )

        elif _delta <= datetime.timedelta(seconds=10):
            raise BotException(
                "Failed to set reminder!",
                "Why do you want me to set a reminder for such a small duration?\n"
                "Pretty sure you can remember that one yourself :wink:",
            )

        # remove microsecond precision of the 'on' variable
        on -= datetime.timedelta(microseconds=on.microsecond)

        async with db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.get({})
            if self.author.id not in db_data:
                db_data[self.author.id] = {}

            # user is editing old reminder message, discard the old reminder
            for key, (_, chan_id, msg_id) in tuple(db_data[self.author.id].items()):
                if chan_id == self.channel.id and msg_id == self.invoke_msg.id:
                    db_data[self.author.id].pop(key)

            limit = 25 if self.is_priv else 10
            if len(db_data[self.author.id]) >= limit:
                raise BotException(
                    "Failed to set reminder!",
                    f"I cannot set more than {limit} reminders for you",
                )

            db_data[self.author.id][on] = (
                msg.string.strip(),
                self.channel.id,
                self.invoke_msg.id,
            )
            db_obj.write(db_data)

        await embed_utils.replace(
            self.response_msg,
            title="Reminder set!",
            description=(
                f"Gonna remind {self.author.name} in {utils.format_timedelta(_delta)}\n"
                f"And that is on {utils.format_datetime(on)}"
            ),
        )

    @add_group("reminders", "set")
    async def cmd_reminders_set(
        self,
        msg: String,
        timestr: Union[String, str] = "",
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
    ):
        """
        ->type Reminders
        ->signature pg!reminders set <message> [time string] [weeks] [days] [hours] [minutes] [seconds]
        ->description Set a reminder to yourself
        ->extended description
        There are two ways you can pass the time duration, one is via a "time string"
        and the other is via keyword arguments
        `weeks`, `days`, `hours`, `minutes` and `seconds` are optional arguments you can
        specify to describe the time duration you want to set the reminder for
        ->example command pg!reminders set "Become pygame expert" weeks=9 days=12 hours=23 minutes=16 seconds=35
        -----
        Implement pg!reminders_set, for users to set reminders for themselves
        """
        timestr = (
            timestr.string.strip() if isinstance(timestr, String) else timestr.strip()
        )

        if timestr:
            time_formats = {
                "w": 7 * 24 * 60 * 60,
                "d": 24 * 60 * 60,
                "h": 60 * 60,
                "m": 60,
                "s": 1,
            }
            sec = 0

            for time_format, dt in time_formats.items():
                try:
                    results = re.search(rf"\d+{time_format}", timestr).group()
                    parsed_time = int(results.replace(time_format, ""))
                    sec += parsed_time * dt
                except AttributeError:
                    pass

            if "mo" in timestr:
                month_results = re.search(r"\d+mo", timestr).group()
                parsed_month_time = int(month_results.replace("mo", ""))
                sec += (
                    self.invoke_msg.created_at.replace(
                        month=self.invoke_msg.created_at.month + parsed_month_time
                    )
                    - self.invoke_msg.created_at
                ).total_seconds()

            if sec == 0:
                raise BotException(
                    "Failed to set reminder!",
                    "There is something wrong with your time parameter.\n"
                    "Please check that it is correct and try again",
                )

            delta = datetime.timedelta(seconds=sec)
        else:
            delta = datetime.timedelta(
                weeks=weeks,
                days=days,
                hours=hours,
                minutes=minutes,
                seconds=seconds,
            )

        await self.cmd_reminders_add(msg, datetime.datetime.utcnow(), _delta=delta)

    @add_group("reminders")
    async def cmd_reminders(self):
        """
        ->type Reminders
        ->signature pg!reminders
        ->description View all the reminders you have set
        -----
        Implement pg!reminders, for users to view their reminders
        """
        async with db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.get({})

        desc = "You have no reminders set"
        if self.author.id in db_data:
            desc = ""
            cnt = 0
            for on, (reminder, chan_id, _) in db_data[self.author.id].items():
                channel = None
                if common.guild is not None:
                    channel = common.guild.get_channel(chan_id)

                cin = channel.mention if channel is not None else "DM"
                desc += (
                    f"Reminder ID: `{cnt}`\n"
                    f"**On {utils.format_datetime(on)} in {cin}:**\n> {reminder}\n\n"
                )
                cnt += 1

        await embed_utils.replace(
            self.response_msg,
            title=f"Reminders for {self.author.display_name}:",
            description=desc,
        )

    @add_group("reminders", "remove")
    async def cmd_reminders_remove(self, *reminder_ids: int):
        """
        ->type Reminders
        ->signature pg!reminders remove [*ids]
        ->description Remove reminders
        ->extended description
        Remove variable number of reminders, corresponding to each datetime argument
        The reminder id argument must be an integer
        If no arguments are passed, the command clears all reminders
        ->example command pg!reminders remove 1
        -----
        Implement pg!reminders_remove, for users to remove their reminders
        """
        async with db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.get({})
            db_data_copy = copy.deepcopy(db_data)
            cnt = 0
            if reminder_ids:
                for reminder_id in sorted(set(reminder_ids), reverse=True):
                    if self.author.id in db_data:
                        for i, dt in enumerate(db_data_copy[self.author.id]):
                            if i == reminder_id:
                                db_data[self.author.id].pop(dt)
                                cnt += 1
                                break
                    if (
                        reminder_id >= len(db_data_copy[self.author.id])
                        or reminder_id < 0
                    ):
                        raise BotException(
                            "Invalid Reminder ID!",
                            "Reminder ID was not an existing reminder ID",
                        )

                if self.author.id in db_data and not db_data[self.author.id]:
                    db_data.pop(self.author.id)

            elif self.author.id in db_data:
                cnt = len(db_data.pop(self.author.id))

            db_obj.write(db_data)

        await embed_utils.replace(
            self.response_msg,
            title="Reminders removed!",
            description=f"Successfully removed {cnt} reminder(s)",
        )

    async def cmd_exec(self, code: CodeBlock):
        """
        ->type Play With Me :snake:
        ->signature pg!exec <python code block>
        ->description Run python code in an isolated environment.
        ->extended description
        Import is not available. Various methods of builtin objects have been disabled for security reasons.
        The available preimported modules are:
        `math, cmath, random, re, time, string, itertools, pygame`
        To show an image, overwrite `output.img` to a surface (see example command).
        To make it easier to read and write code use code blocks (see [HERE](https://discord.com/channels/772505616680878080/774217896971730974/785510505728311306)).
        ->example command pg!exec \\`\\`\\`py ```py
        # Draw a red rectangle on a transparent surface
        output.img = pygame.Surface((200, 200)).convert_alpha()
        output.img.fill((0, 0, 0, 0))
        pygame.draw.rect(output.img, (200, 0, 0), (50, 50, 100, 100))```
        \\`\\`\\`
        -----
        Implement pg!exec, for execution of python code
        """
        async with self.channel.typing():
            tstamp = time.perf_counter_ns()

            returned = await sandbox.exec_sandbox(
                code.code, tstamp, 10 if self.is_priv else 5
            )
            dur = returned.duration  # the execution time of the script alone
            embed_dict = {
                "color": embed_utils.DEFAULT_EMBED_COLOR,
                "description": "",
                "author": {
                    "name": f"Code executed in {utils.format_time(dur)}",
                    "url": self.invoke_msg.jump_url,
                },
            }

            file = None
            if returned.exc:
                embed_dict["description"] += "**Exception output:**\n"
                embed_dict["description"] += utils.code_block(returned.exc, 500)
                embed_dict["description"] += "\n"

            if returned.text:
                embed_dict["description"] += "**Text output:**\n"
                embed_dict["description"] += utils.code_block(returned.text, 1500)

            if returned.img:
                embed_dict["description"] += "\n**Image output:**"
                if os.path.getsize(f"temp{tstamp}.png") < 2 ** 22:
                    embed_dict["image_url"] = f"attachment://temp{tstamp}.png"
                    file = discord.File(f"temp{tstamp}.png")
                else:
                    embed_dict["description"] += (
                        "\n```\nGIF could not be sent.\n"
                        "The GIF file size is above 4MiB```"
                    )

            elif returned._imgs:
                embed_dict["description"] += "\n**GIF output:**"
                if os.path.getsize(f"temp{tstamp}.gif") < 2 ** 22:
                    embed_dict["image_url"] = f"attachment://temp{tstamp}.gif"
                    file = discord.File(f"temp{tstamp}.gif")
                else:
                    embed_dict["description"] += (
                        "\n```GIF could not be sent.\n"
                        "The GIF file size is above 4MiB```"
                    )

        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass

        embed = embed_utils.create_from_dict(embed_dict)
        await self.invoke_msg.reply(file=file, embed=embed, mention_author=False)

        if len(returned.text) > 1500:
            with io.StringIO(
                returned.text
                if len(returned.text) - 40 < self.filesize_limit
                else returned.text[: self.filesize_limit - 40]
            ) as fobj:
                await self.channel.send(file=discord.File(fobj, filename="output.txt"))

        if file:
            file.close()

        for extension in ("gif", "png"):
            if os.path.isfile(f"temp{tstamp}.{extension}"):
                os.remove(f"temp{tstamp}.{extension}")

    @no_dm
    async def cmd_refresh(self, msg: discord.Message):
        """
        ->type Other commands
        ->signature pg!refresh <message>
        ->description Refresh a message which support pages.
        -----
        Implement pg!refresh, to refresh a message which supports pages
        """

        if (
            not msg.embeds
            or not msg.embeds[0].footer
            or not isinstance(msg.embeds[0].footer.text, str)
        ):
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure you "
                "have replied to the correct message",
            )

        data = msg.embeds[0].footer.text.splitlines()

        if len(data) != 3 and not data[2].startswith("Command: "):
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct.",
            )

        page = re.search(r"\d+", data[0]).group()
        cmd_str = data[2].replace("Command: ", "")

        if not page.isdigit() or not cmd_str:
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct.",
            )

        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            pass

        # Handle the new command, the one that pg!refresh is trying to refresh
        self.response_msg = msg
        self.cmd_str = cmd_str
        self.page = int(page) - 1
        await self.handle_cmd()

    @no_dm
    @add_group("poll")
    async def cmd_poll(
        self,
        desc: String,
        *emojis: tuple[str, String],
        multi_votes: bool = False,
        _destination: Optional[common.Channel] = None,
        _admin_embed_dict: dict = {},
    ):
        """
        ->type Other commands
        ->signature pg!poll <description> [*emojis] [multi_votes=True]
        ->description Start a poll.
        ->extended description
        `pg!poll description *args`
        The args must series of two element tuples, first element being emoji,
        and second being the description (see example command).
        The emoji must be a default emoji or one from this server. To close the poll see 'pg!poll close'.
        A `multi_votes` arg can also be passed indicating if the user can cast multiple votes in a poll or not
        ->example command pg!poll "Which apple is better?" ( 🍎 "Red apple") ( 🍏 "Green apple")
        """

        destination = self.channel if _destination is None else _destination

        base_embed_dict = {
            "title": "Voting in progress",
            "fields": [
                {
                    "name": "🔺",
                    "value": "Agree",
                    "inline": True,
                },
                {
                    "name": "🔻",
                    "value": "Disagree",
                    "inline": True,
                },
            ],
            "author": {
                "name": self.author.name,
            },
            "color": 0x34A832,
            "footer": {
                "text": f"By {self.author.display_name}\n({self.author.id})\n"
                f"{'' if multi_votes else common.UNIQUE_POLL_MSG}Started"
            },
            "timestamp": self.response_msg.created_at.isoformat(),
            "description": desc.string,
        }
        base_embed_dict.update(_admin_embed_dict)

        # Make into dict because we want to get rid of emoji repetitions
        emojis_dict = {k.strip(): v.string.strip() for k, v in emojis}
        if emojis_dict:
            if len(emojis_dict) == 1:
                raise BotException(
                    "Invalid arguments for emojis",
                    "Please add at least 2 options in the poll\n"
                    "For more information, see `pg!help poll`",
                )

            base_embed_dict["fields"] = [
                {"name": k, "value": v, "inline": True} for k, v in emojis_dict.items()
            ]

        final_embed = discord.Embed.from_dict(base_embed_dict)
        poll_msg = await destination.send(embed=final_embed)
        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            pass

        for field in base_embed_dict["fields"]:
            try:
                emoji_id = utils.filter_emoji_id(field["name"].strip())
                emoji = common.bot.get_emoji(emoji_id)
                if emoji is None:
                    raise ValueError()
            except ValueError:
                emoji = field["name"]

            try:
                await poll_msg.add_reaction(emoji)
            except (discord.errors.HTTPException, discord.errors.NotFound):
                # Either a custom emoji was used (which could not be added by
                # our beloved snek) or some other error happened. Clear the
                # reactions and prompt the user to make sure it is the currect
                # emoji.
                await poll_msg.clear_reactions()
                raise BotException(
                    "Invalid emoji",
                    "The emoji could not be added as a reaction. Make sure it is"
                    " the correct emoji and that it is not from another server",
                )

    @no_dm
    @add_group("poll", "close")
    async def cmd_poll_close(
        self,
        msg: discord.Message,
        *,
        _color: Optional[pygame.Color] = None,
    ):
        """
        ->type Other commands
        ->signature pg!poll close <message>
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """
        # needed for typecheckers to know that self.author is a member
        if isinstance(self.author, discord.User):
            return

        if not utils.check_channel_permissions(
            self.author, msg.channel, permissions=("view_channel",)
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        if not msg.embeds:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongoing vote."
                " Please double-check the id.",
            )

        embed = msg.embeds[0]
        if not isinstance(embed.footer.text, str):
            raise BotException(
                "Invalid message",
                "The message specified is not an ongoing vote."
                " Please double-check the id.",
            )

        # Take the second line remove the parenthesies
        if embed.footer.text and embed.footer.text.count("\n"):
            poll_owner = int(
                embed.footer.text.split("\n")[1].replace("(", "").replace(")", "")
            )
        else:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongiong vote."
                " Please double-check the id.",
            )

        if _color is None and self.author.id != poll_owner:
            raise BotException(
                "You can't stop this vote",
                "The vote was not started by you."
                " Ask the person who started it to close it.",
            )

        title = "Voting has ended"
        reactions = {}
        for reaction in msg.reactions:
            if isinstance(reaction.emoji, str):
                reactions[reaction.emoji] = reaction.count
            else:
                reactions[reaction.emoji.id] = reaction.count

        top: list[tuple[int, Any]] = [(0, None)]
        for reaction in msg.reactions:
            if getattr(reaction.emoji, "id", reaction.emoji) not in reactions:
                continue

            if reaction.count - 1 > top[0][0]:
                top = [
                    (reaction.count - 1, getattr(reaction.emoji, "id", reaction.emoji))
                ]
                continue

            if reaction.count - 1 == top[0][0]:
                top.append((reaction.count - 1, reaction.emoji))

        fields = []
        for field in embed.fields:
            if not isinstance(field.name, str):
                continue

            try:
                r_count = reactions[utils.filter_emoji_id(field.name)] - 1
            except KeyError:
                # The reactions and the embed fields dont match up.
                # Someone is abusing their mod powers if this happens probably.
                continue

            fields.append([field.name, f"{field.value} ({r_count} votes)", True])

            if utils.filter_emoji_id(field.name) == top[0][1]:
                title += (
                    f"\n{field.value}({field.name}) has won with {top[0][0]} votes!"
                )

        if len(top) >= 2:
            title = title.split("\n")[0]
            title += "\nIt's a draw!"

        await embed_utils.edit(
            msg,
            embed,
            color=0xA83232 if not _color else utils.color_to_rgb_int(_color),
            title=title,
            fields=fields,
            footer_text="Ended",
            timestamp=self.response_msg.created_at,
        )
        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            pass

    @add_group("stream")
    async def cmd_stream(self):
        """
        ->type Reminders
        ->signature pg!stream
        ->description Show the ping-stream-list
        Send an embed with all the users currently in the ping-stream-list
        """
        async with db.DiscordDB("stream") as db_obj:
            data = db_obj.get([])

        if not data:
            await embed_utils.replace(
                self.response_msg,
                title="Memento ping list",
                description="Ping list is empty!",
            )
            return

        await embed_utils.replace(
            self.response_msg,
            title="Memento ping list",
            description=(
                "Here is a list of people who want to be pinged when stream starts"
                "\nUse 'pg!stream ping' to ping them if you start streaming\n"
                + "\n".join((f"<@{user}>" for user in data))
            ),
        )

    @add_group("stream", "add")
    async def cmd_stream_add(
        self, *, _members: Optional[tuple[discord.Member, ...]] = None
    ):
        """
        ->type Reminders
        ->signature pg!stream add
        ->description Add yourself to the stream-ping-list
        ->extended description
        Add yourself to the stream-ping-list. You can always delete you later
        with `pg!stream del`
        """
        async with db.DiscordDB("stream") as ping_db:
            data: list = ping_db.get([])

            if _members:
                for mem in _members:
                    if mem.id not in data:
                        data.append(mem.id)
            elif self.author.id not in data:
                data.append(self.author.id)

            ping_db.write(data)

        await self.cmd_stream()

    @add_group("stream", "del")
    async def cmd_stream_del(
        self, *, _members: Optional[tuple[discord.Member, ...]] = None
    ):
        """
        ->type Reminders
        ->signature pg!stream del
        ->description Remove yourself from the stream-ping-list
        ->extended description
        Remove yourself from the stream-ping-list. You can always add you later
        with `pg!stream add`
        """
        async with db.DiscordDB("stream") as ping_db:
            data: list = ping_db.get([])

            try:
                if _members:
                    for mem in _members:
                        data.remove(mem.id)
                else:
                    data.remove(self.author.id)
            except ValueError:
                raise BotException(
                    "Could not remove member",
                    "Member was not previously added to the ping list",
                )

            ping_db.write(data)

        await self.cmd_stream()

    @add_group("stream", "ping")
    async def cmd_stream_ping(self, message: Optional[String] = None):
        """
        ->type Reminders
        ->signature pg!stream ping [message]
        ->description Ping users in stream-list with an optional message.
        ->extended description
        Ping all users in the ping list to announce a stream.
        You can pass an optional stream message (like the stream topic).
        The streamer name will be included and many people will be pinged so \
        don't make pranks with this command.
        """
        async with db.DiscordDB("stream") as ping_db:
            data: list = ping_db.get([])

        msg = message.string if message else "Enjoy the stream!"
        ping = (
            "Pinging everyone on ping list:\n"
            + "\n".join((f"<@!{user}>" for user in data))
            if data
            else "No one is registered on the ping momento :/"
        )

        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            pass
        await self.channel.send(f"<@!{self.author.id}> is gonna stream!\n{msg}\n{ping}")
