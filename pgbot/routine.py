"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines a "routine" function, that gets called on routine.
It gets called every 5 seconds or so.
"""

import asyncio
import datetime
import io
import os
import random
import sys

import discord
from discord.ext import tasks

from pgbot import common, db, emotion
from pgbot.utils import utils

num_increment = 1 / 20


async def handle_reminders(reminder_obj: db.DiscordDB):
    """
    Handle reminder routines
    """
    reminders = reminder_obj.get({})

    new_reminders = {}
    for mem_id, reminder_dict in reminders.items():
        for dt, (msg, chan_id, msg_id) in reminder_dict.items():
            if datetime.datetime.utcnow() >= dt:
                content = f"__**Reminder for you:**__\n>>> {msg}"

                channel = None
                if common.guild is not None:
                    channel = common.guild.get_channel(chan_id)
                if not isinstance(channel, discord.TextChannel):
                    # Channel does not exist in the guild, DM the user
                    try:
                        user = await common.bot.fetch_user(mem_id)
                        if user.dm_channel is None:
                            await user.create_dm()

                        await user.dm_channel.send(content=content)
                    except discord.HTTPException:
                        pass
                    continue

                allowed_mentions = discord.AllowedMentions.none()
                allowed_mentions.replied_user = True
                try:
                    message = await channel.fetch_message(msg_id)
                    await message.reply(
                        content=content, allowed_mentions=allowed_mentions
                    )
                except discord.HTTPException:
                    # The message probably got deleted, try to resend in channel
                    allowed_mentions.users = [discord.Object(mem_id)]
                    content = f"__**Reminder for <@!{mem_id}>:**__\n>>> {msg}"
                    try:
                        await channel.send(
                            content=content,
                            allowed_mentions=allowed_mentions,
                        )
                    except discord.HTTPException:
                        pass
            else:
                if mem_id not in new_reminders:
                    new_reminders[mem_id] = {}

                new_reminders[mem_id][dt] = (msg, chan_id, msg_id)

    if reminders != new_reminders:
        reminder_obj.write(new_reminders)


@tasks.loop(seconds=5)
async def handle_console():
    """
    Function for sending the console output to the bot-console channel.
    """
    if common.stdout is None:
        return

    contents = common.stdout.getvalue()
    sys.stdout = sys.stderr = common.stdout = io.StringIO()

    # hide path data
    contents = contents.replace(os.getcwd(), "PgBot")
    if os.name == "nt":
        contents = contents.replace(os.path.dirname(sys.executable), "Python")

    if common.GENERIC or common.console_channel is None:
        # just print error to shell if we cannot sent it on discord
        print(contents, file=sys.__stdout__)
        return

    # the actual message limit is 2000. But since the message is sent with
    # code ticks, we need room for those, so 1980
    for content in utils.split_long_message(contents, 1980):
        content = content.strip()
        if not content:
            continue

        await common.console_channel.send(
            content=utils.code_block(content, code_type="cmd")
        )


async def handle_depression():
    """
    Function to handle depression emotion
    """
    async with db.DiscordDB("emotions") as db_obj:
        all_emotions = db_obj.get({})

        # Gets the depression emotion dict
        depression = all_emotions.get("depression", {})

        happiness = all_emotions.get("happy", 0)
        if happiness > 0:
            # Bot is happy
            depression["min_of_sadness"] = None

            if depression.get("value", 0) > 0:
                # If depression is > 0 when bot is happy,
                # use happiness sigmoid inverse piecewise function
                try:
                    depression["min_of_happiness"] = (
                        emotion.depression_function_curve(
                            "happy", depression.get("value", 0), inverse=True
                        )
                        + num_increment
                    )
                except ValueError:
                    depression["min_of_happiness"] = num_increment
            else:
                # If depression is 0 when bot is happy,
                # start incrementing min of happiness
                depression["min_of_happiness"] = num_increment
        else:
            # Bot is sad
            depression["min_of_happiness"] = None

            if 0 < depression.get("value", 0) < 100:
                # If depression in range (0, 100),
                # Use depression sigmoid inverse piecewise function
                try:
                    depression["min_of_sadness"] = (
                        emotion.depression_function_curve(
                            "depression", depression.get("value", 0), inverse=True
                        )
                        + num_increment
                    )
                except ValueError:
                    depression["min_of_happiness"] += 0.1
            else:
                # Otherwise, increment min of sadness
                try:
                    depression["min_of_sadness"] = (
                        depression.get("min_of_sadness", 0) + num_increment
                    )
                except TypeError:
                    depression["min_of_sadness"] = num_increment

        try:
            # Sets the min value of happiness to num increment
            if depression.get("min_of_happiness", 0) < 0:
                depression["min_of_happiness"] = num_increment
        except TypeError:
            pass

        # If depression < 0.001, set it to 0
        # (it'd take 1431 minutes for python to not be able to store it and error out)
        if depression.get("value", 1) < 1e-3:
            depression["value"] = 0
            depression["min_of_happiness"] = None

        # Actually adjusts value based on minutes of sadness/happiness
        if depression["min_of_sadness"]:
            depression["value"] = emotion.depression_function_curve(
                "depression", depression["min_of_sadness"]
            )
        elif depression["min_of_happiness"]:
            depression["value"] = emotion.depression_function_curve(
                "happy", depression["min_of_happiness"]
            )

        # Updates all_emotion's depression to depression dict and writes it to db_obj
        all_emotions["depression"] = depression

        db_obj.write(all_emotions)


@tasks.loop(seconds=3)
async def routine():
    """
    Function that gets called routinely. This function inturn, calles other
    routine functions to handle stuff
    """
    async with db.DiscordDB("reminders") as db_obj:
        await handle_reminders(db_obj)

    if random.randint(0, 4) == 0:
        await emotion.update("bored", 1)
    await handle_depression()

    await common.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="discord.io/pygame_community",
        )
    )
    await asyncio.sleep(3)
    await common.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="in discord.io/pygame_community",
        )
    )
