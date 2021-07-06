"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the base class for the command handler classes and also
defines argument casting utilities
"""


from __future__ import annotations

import asyncio
import datetime
import inspect
import random
from typing import Any, Optional, Union

import discord
import pygame
from pgbot import common, db, emotion
from pgbot.commands.parser import (
    ArgError,
    BotException,
    CodeBlock,
    KwargError,
    String,
    get_anno_error,
    parse_args,
    split_tuple_anno,
    split_union_anno,
)
from pgbot.utils import embed_utils, utils


def fun_command(func):
    """
    A decorator to indicate a "fun command", one that the bot skips when it is
    'exhausted'
    """
    func.fun_cmd = True
    return func


def no_dm(func):
    """
    A decorator to indicate a command that cannot be run on DM
    """
    func.no_dm = True
    return func


def add_group(groupname: str, *subcmds: str):
    """
    Utility to add a function name to a group command
    """

    def inner(func):
        # patch in group name data and sub command data into the function itself
        if subcmds:
            func.groupname = groupname
            func.subcmds = subcmds
        return func

    return inner


class BaseCommand:
    """
    Base class for all commands. Defines the main utilities like argument
    parsers and command handlers
    """

    def __init__(
        self,
        invoke_msg: discord.Message,
        resp_msg: discord.Message,
    ):
        """
        Initialise UserCommand class
        """
        # Create a dictionary of command names and respective handler functions
        self.invoke_msg: discord.Message = invoke_msg
        self.response_msg: discord.Message = resp_msg
        self.is_priv = True
        self.cmd_str: str = self.invoke_msg.content[len(common.PREFIX) :]

        # Put a few attributes here for easy access
        self.author: Union[discord.Member, discord.User] = self.invoke_msg.author
        self.channel: common.Channel = self.invoke_msg.channel
        self.guild: Optional[discord.Guild] = self.invoke_msg.guild
        self.is_dm = self.guild is None

        # if someone is DMing, set guild to primary server (PGC server)
        if self.guild is None:
            self.guild = common.guild
            self.filesize_limit = common.BASIC_MAX_FILE_SIZE
        else:
            self.filesize_limit: int = self.guild.filesize_limit

        # build self.groups and self.cmds_and_functions from class functions
        self.cmds_and_funcs = {}  # this is a mapping from funtion name to funtion
        self.groups = {}  # This is a mapping from group name to list of sub functions
        for attr in dir(self):
            if attr.startswith(common.CMD_FUNC_PREFIX):
                func = self.__getattribute__(attr)
                name = attr[len(common.CMD_FUNC_PREFIX) :]
                self.cmds_and_funcs[name] = func

                if hasattr(func, "groupname"):
                    if func.groupname in self.groups:
                        self.groups[func.groupname].append(func)
                    else:
                        self.groups[func.groupname] = [func]

        # page number, useful for PagedEmbed commands. 0 by deafult, gets modified
        # in pg!refresh command when invoked
        self.page: int = 0

    def get_guild(self):
        """
        Utility to retrieve self.guild. This function will raise BotException
        if self.guild is not set
        """
        if self.guild is None:
            raise BotException(
                "Internal bot error!", "Primary guild for the bot was not set"
            )
        return self.guild

    async def cast_basic_arg(self, anno: str, arg: Any) -> Any:
        """
        Helper to cast an argument to the type mentioned by the parameter
        annotation. This casts an argument in its "basic" form, where both argument
        and typehint are "simple", that does not contain stuff like Union[...],
        tuple[...], etc.
        Raises ValueError on failure to cast arguments
        """
        if isinstance(arg, tuple):
            if len(arg) != 1:
                raise ValueError()

            # got a one element tuple where we expected an arg, handle that element
            arg = arg[0]

        if isinstance(arg, CodeBlock):
            if anno == "CodeBlock":
                return arg
            raise ValueError()

        elif isinstance(arg, String):
            if anno == "String":
                return arg

            elif anno in ["datetime.datetime", "datetime"]:
                arg2 = arg.string.strip()
                arg2 = arg2[:-1] if arg2.endswith("Z") else arg2
                return datetime.datetime.fromisoformat(arg2)

            raise ValueError()

        elif isinstance(arg, str):
            if anno in ["CodeBlock", "String", "datetime.datetime", "datetime"]:
                raise ValueError()

            elif anno == "str":
                return arg

            elif anno == "bool":
                return arg == "1" or arg.lower() == "true"

            elif anno == "int":
                return int(arg)

            elif anno == "float":
                return float(arg)

            elif anno == "range":
                if not arg.startswith("[") or not arg.endswith("]"):
                    raise ValueError()

                splits = [int(i.strip()) for i in arg[6:-1].split(":")]

                if splits and len(splits) <= 3:
                    return range(*splits)
                raise ValueError()

            elif anno == "pygame.Color":
                return pygame.Color(arg)

            elif anno == "discord.Object":
                # Generic discord API Object that has an ID
                return discord.Object(utils.filter_id(arg))

            elif anno == "discord.Role":
                role = self.get_guild().get_role(utils.filter_id(arg))
                if role is None:
                    raise ValueError()
                return role

            elif anno == "discord.Member":
                try:
                    return await self.get_guild().fetch_member(utils.filter_id(arg))
                except discord.errors.NotFound:
                    raise ValueError()

            elif anno == "discord.User":
                try:
                    return await common.bot.fetch_user(utils.filter_id(arg))
                except discord.errors.NotFound:
                    raise ValueError()

            elif anno in ("discord.TextChannel", "common.Channel"):
                formatted = utils.format_discord_link(arg, self.get_guild().id)

                chan = self.get_guild().get_channel(utils.filter_id(formatted))
                if chan is None:
                    raise ValueError()

                return chan

            elif anno == "discord.Guild":
                guild = common.bot.get_guild(utils.filter_id(arg))
                if guild is None:
                    try:
                        guild = await common.bot.fetch_guild(utils.filter_id(arg))
                    except discord.HTTPException:
                        raise ValueError()
                return guild

            elif anno == "discord.Message":
                formatted = utils.format_discord_link(arg, self.get_guild().id)

                a, b, c = formatted.partition("/")
                if b:
                    msg = int(c)
                    chan = self.get_guild().get_channel(utils.filter_id(a))

                    if not isinstance(chan, discord.TextChannel):
                        raise ValueError()
                else:
                    msg = int(a)
                    chan = self.channel

                try:
                    return await chan.fetch_message(msg)
                except discord.NotFound:
                    raise ValueError()

            elif anno == "discord.PartialMessage":
                formatted = utils.format_discord_link(arg, self.get_guild().id)

                a, b, c = formatted.partition("/")
                if b:
                    msg = int(c)
                    chan = self.get_guild().get_channel(utils.filter_id(a))

                    if not isinstance(chan, discord.TextChannel):
                        raise ValueError()
                else:
                    msg = int(a)
                    chan = self.channel

                if isinstance(chan, discord.GroupChannel):
                    raise ValueError()

                return chan.get_partial_message(msg)

            raise BotException(
                "Internal Bot error", f"Invalid type annotation `{anno}`"
            )

        raise BotException(
            "Internal Bot error", f"Invalid argument of type `{type(arg)}`"
        )

    async def cast_arg(
        self,
        param: Union[inspect.Parameter, str],
        arg: Any,
        cmd: str,
        key: Optional[str] = None,
        convert_error: bool = True,
    ) -> Any:
        """
        Cast an argument to the type mentioned by the paramenter annotation
        """
        if isinstance(param, str):
            anno = param

        elif param.annotation == param.empty:
            # no checking/converting, do a direct return
            return arg

        else:
            anno: str = param.annotation

        if anno == "Any":
            # no checking/converting, do a direct return
            return arg

        union_annos = list(split_union_anno(anno))
        last_anno = union_annos.pop()

        for union_anno in union_annos:
            # we are in a union argument type, try to cast to each element one
            # by one
            try:
                return await self.cast_arg(union_anno, arg, cmd, key, False)
            except ValueError:
                pass

        tupled = split_tuple_anno(last_anno)
        try:
            if tupled is None:
                # got a basic argument
                return await self.cast_basic_arg(last_anno, arg)

            if not isinstance(arg, tuple):
                if len(tupled) == 2 and tupled[1] == "...":
                    # specialcase where we expected variable length tuple and
                    # got single element
                    return (await self.cast_arg(tupled[0], arg, cmd, key, False),)

                raise ValueError()

            if len(tupled) == 2 and tupled[1] == "...":
                # variable length tuple
                return tuple(
                    await self.cast_arg(tupled[0], elem, cmd, key, False)
                    for elem in arg
                )

            # fixed length tuple
            if len(tupled) != len(arg):
                raise ValueError()

            return tuple(
                await self.cast_arg(i, j, cmd, key, False) for i, j in zip(tupled, arg)
            )

        except ValueError:
            if not convert_error:
                # Just forward value error in this case
                raise

            if key is None and not isinstance(param, str):
                if param.kind == param.VAR_POSITIONAL:
                    key = "Each of the variable arguments"
                else:
                    key = "Each of the variable keyword arguments"
            else:
                key = f"The argument `{key}`"

            raise ArgError(f"{key} must be {get_anno_error(anno)}.", cmd)

    async def call_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        This one takes in the parsed arguments from the parse_args function,
        and handles that according to the function being called, by using
        the inspect module, and verifying that all args and kwargs are accurate
        before calling the actual function. Relies on argument annotations to
        cast args/kwargs to the types required by the function
        """
        cmd, args, kwargs = parse_args(self.cmd_str)

        # command has been blacklisted from running
        async with db.DiscordDB("blacklist") as db_obj:
            if cmd in db_obj.get([]):
                raise BotException(
                    "Cannot execute comamand!",
                    f"The command '{cmd}' has been temporarily been blocked from "
                    "running, while wizards are casting their spells on it!\n"
                    "Please try running the command after the maintenance work "
                    "has been finished",
                )

        # First check if it is a group command, and handle it.
        # get the func object
        is_group = False
        func = None
        if cmd in self.groups:
            # iterate over group commands sorted in descending order, so that
            # we find the correct match
            for func in sorted(
                self.groups[cmd], key=lambda x: len(x.subcmds), reverse=True
            ):
                n = len(func.subcmds)
                if func.subcmds == tuple(args[:n]):
                    args = args[n:]
                    is_group = True
                    break

        if not is_group:
            if cmd not in self.cmds_and_funcs:
                if cmd in common.admin_commands:
                    raise BotException(
                        "Permissions Error!",
                        f"The command '{cmd}' is an admin command, and you do "
                        "not have access to that",
                    )

                raise BotException(
                    "Unrecognized command!",
                    f"The command '{cmd}' does not exist.\nFor help on bot "
                    "commands, do `pg!help`",
                )
            func = self.cmds_and_funcs[cmd]

        if hasattr(func, "no_dm") and self.is_dm:
            raise BotException(
                "Cannot run this commands on DM",
                "This command is not supported on DMs",
            )

        if hasattr(func, "fun_cmd"):
            if await utils.get_channel_feature("nofun", self.channel):
                raise BotException(
                    "Could not run command!",
                    "This command is a 'fun' command, and is not allowed "
                    "in this channel. Please try running the command in "
                    "some other channel.",
                )

            bored = await emotion.get("bored")
            if bored < -60 and -bored / 100 >= random.random():
                raise BotException(
                    "I am Exhausted!",
                    "I have been running a lot of commands lately, and now I am tired.\n"
                    "Give me a bit of a break, and I will be back to normal!",
                )

            confused = await emotion.get("confused")
            if confused > 60 and random.random() < confused / 400:
                await embed_utils.replace(
                    self.response_msg,
                    title="I am confused...",
                    description="Hang on, give me a sec...",
                )

                await asyncio.sleep(random.randint(3, 5))
                await embed_utils.replace(
                    self.response_msg,
                    title="Oh, never mind...",
                    description="Sorry, I was confused for a sec there",
                )
                await asyncio.sleep(0.5)

        if func is None:
            raise BotException("Internal bot error", "This should never happen kek")

        # If user has put an attachment, check whether it's a text file, and
        # handle as code block
        for attach in self.invoke_msg.attachments:
            if attach.content_type is not None and (
                attach.content_type.startswith("text")
                or attach.content_type.endswith(("json", "javascript"))
            ):
                contents = await attach.read()
                ext = ""
                if "." in attach.filename:
                    ext = attach.filename.split(".")[-1]

                args.append(CodeBlock(contents.decode(), ext))

        sig = inspect.signature(func)

        i = -1
        is_var_pos = is_var_key = False
        keyword_only_args = []
        all_keywords = []

        # iterate through function parameters, arrange the given args and
        # kwargs in the order and format the function wants
        for i, key in enumerate(sig.parameters):
            param = sig.parameters[key]
            iskw = False

            if param.kind not in [param.POSITIONAL_ONLY, param.VAR_POSITIONAL]:
                all_keywords.append(key)

            if (
                i == 0
                and isinstance(param.annotation, str)
                and self.invoke_msg.reference is not None
                and (
                    "discord.Message" in param.annotation
                    or "discord.PartialMessage" in param.annotation
                )
            ):
                # first arg is expected to be a Message object, handle reply into
                # the first argument
                msg = str(self.invoke_msg.reference.message_id)
                if self.invoke_msg.reference.channel_id != self.channel.id:
                    msg = str(self.invoke_msg.reference.channel_id) + "/" + msg

                args.insert(0, msg)

            if param.kind == param.VAR_POSITIONAL:
                is_var_pos = True
                for j in range(i, len(args)):
                    args[j] = await self.cast_arg(param, args[j], cmd)
                continue

            elif param.kind == param.VAR_KEYWORD:
                is_var_key = True
                for j in kwargs:
                    if j not in keyword_only_args:
                        kwargs[j] = await self.cast_arg(param, kwargs[j], cmd)
                continue

            elif param.kind == param.KEYWORD_ONLY:
                iskw = True
                keyword_only_args.append(key)
                if key not in kwargs:
                    if param.default == param.empty:
                        raise KwargError(
                            f"Missed required keyword argument `{key}`", cmd
                        )
                    kwargs[key] = param.default
                    continue

            elif i == len(args):
                # ran out of args, try to fill it with something
                if key in kwargs:
                    if param.kind == param.POSITIONAL_ONLY:
                        raise ArgError(
                            f"`{key}` cannot be passed as a keyword argument", cmd
                        )
                    args.append(kwargs.pop(key))

                elif param.default == param.empty:
                    raise ArgError(f"Missed required argument `{key}`", cmd)
                else:
                    args.append(param.default)
                    continue

            elif key in kwargs:
                raise ArgError(
                    "Positional cannot be passed again as a keyword argument", cmd
                )

            # cast the argument into the required type
            if iskw:
                kwargs[key] = await self.cast_arg(param, kwargs[key], cmd, key)
            else:
                args[i] = await self.cast_arg(param, args[i], cmd, key)

        i += 1
        # More arguments were given than required
        if not is_var_pos and i < len(args):
            raise ArgError(f"Too many args were given (`{len(args)}`)", cmd)

        # Iterate through kwargs to check if we received invalid ones
        if not is_var_key:
            for key in kwargs:
                if key not in all_keywords:
                    raise KwargError(f"Received invalid keyword argument `{key}`", cmd)

        await func(*args, **kwargs)

    async def handle_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        """
        try:
            await self.call_cmd()
            await emotion.update("confused", -random.randint(4, 8))
            return

        except ArgError as exc:
            await emotion.update("confused", random.randint(2, 6))
            title = "Invalid Arguments!"
            if len(exc.args) == 2:
                msg, cmd = exc.args
                msg += f"\nFor help on this bot command, do `pg!help {cmd}`"
            else:
                msg = exc.args[0]
            excname = "Argument Error"

        except KwargError as exc:
            await emotion.update("confused", random.randint(2, 6))
            title = "Invalid Keyword Arguments!"
            if len(exc.args) == 2:
                msg, cmd = exc.args
                msg += f"\nFor help on this bot command, do `pg!help {cmd}`"
            else:
                msg = exc.args[0]

            excname = "Keyword argument Error"

        except BotException as exc:
            await emotion.update("confused", random.randint(4, 8))
            title, msg = exc.args
            excname = "BotException"

        except discord.HTTPException as exc:
            await emotion.update("confused", random.randint(7, 13))
            title, msg = exc.__class__.__name__, exc.args[0]
            excname = "discord.HTTPException"

        except Exception:
            await emotion.update("confused", random.randint(10, 22))
            await embed_utils.replace(
                self.response_msg,
                title="Unknown Error!",
                description=(
                    "An unhandled exception occured while running the command!\n"
                    "This is most likely a bug in the bot itself, and wizards will "
                    "recast magical spells on it soon!"
                ),
                color=0xFF0000,
            )
            raise

        # display bot exception to user on discord
        try:
            await embed_utils.replace(
                self.response_msg,
                title=title,
                description=msg,
                color=0xFF0000,
                footer_text=excname,
            )
        except discord.NotFound:
            # response message was deleted, send a new message
            await embed_utils.send(
                self.channel,
                title=title,
                description=msg,
                color=0xFF0000,
                footer_text=excname,
            )
