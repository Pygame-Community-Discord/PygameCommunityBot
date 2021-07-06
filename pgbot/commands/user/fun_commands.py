"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the "fun" commands of the bot
"""

from __future__ import annotations

import os
import random
import time

import discord
import pygame
import unidecode

from pgbot import common, db, emotion
from pgbot.commands.base import (
    BaseCommand,
    BotException,
    String,
    add_group,
    fun_command,
)
from pgbot.commands.utils import vibecheck
from pgbot.utils import embed_utils, utils


class FunCommand(BaseCommand):
    """
    Command class to handle "fun" commands.
    """

    @fun_command
    async def cmd_version(self):
        """
        ->type Other commands
        ->signature pg!version
        ->description Get the version of <@&822580851241123860>
        -----
        Implement pg!version, to report bot version
        """
        await embed_utils.replace(
            self.response_msg,
            title="Current bot's version",
            description=f"`{common.__version__}`",
        )

    @fun_command
    async def cmd_ping(self):
        """
        ->type Other commands
        ->signature pg!ping
        ->description Get the ping of the bot
        -----
        Implement pg!ping, to get ping
        """
        timedelta = self.response_msg.created_at - self.invoke_msg.created_at
        sec = timedelta.total_seconds()
        sec2 = common.bot.latency  # This does not refresh that often
        if sec < sec2:
            sec2 = sec

        await embed_utils.replace(
            self.response_msg,
            title=random.choice(("Pingy Pongy", "Pong!")),
            description=f"The bot's ping is `{utils.format_time(sec, 0)}`\n"
            f"The Discord API latency is `{utils.format_time(sec2, 0)}`",
        )

    @fun_command
    @add_group("fontify")
    async def cmd_fontify(self, msg: String):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify <msg>
        ->description Display message in pygame font
        """
        fontified = ""

        emojis = ()
        if common.guild is not None:
            emojis = tuple(sorted(common.guild.emojis, key=lambda x: x.name))

        for char in unidecode.unidecode(msg.string):
            if char.isalnum():
                for emoji in emojis:
                    if (
                        emoji.name == f"pg_char_{char}"
                        or emoji.name == f"pg_char_{char}".lower()
                    ):
                        fontified += str(emoji)
                        break
                else:
                    fontified += ":heavy_multiplication_x:"

            elif char.isspace():
                fontified += " " * 5

            else:
                fontified += ":heavy_multiplication_x:"

        if len(fontified) > 2000:
            raise BotException(
                "Could not execute comamnd",
                "Input text width exceeded maximum limit (2KB)",
            )

        if not fontified:
            raise BotException(
                "Could not execute comamnd",
                "Text cannot be empty",
            )

        await embed_utils.replace(
            self.response_msg,
            description=self.author.mention,
            color=0x40E32D,
        )

        await self.response_msg.edit(content=fontified)

    @fun_command
    @add_group("fontify", "remove")
    async def cmd_fontify_remove(self, reply: discord.Message):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify remove
        ->description Delete your fontified message by replying to it
        """

        # make typecheckers happy
        if common.bot.user is None:
            return

        if (
            reply.author.id != common.bot.user.id
            or not reply.embeds
            or reply.embeds[0].description != self.author.mention
        ):
            raise BotException(
                "Could not execute comamnd", "Please reply to a fontified message"
            )

        await reply.delete()
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @fun_command
    async def cmd_pet(self):
        """
        ->type Play With Me :snake:
        ->signature pg!pet
        ->description Pet me :3
        -----
        Implement pg!pet, to pet the bot
        """
        fname = "die.gif" if await emotion.get("anger") > 60 else "pet.gif"
        await embed_utils.replace(
            self.response_msg,
            color=embed_utils.DEFAULT_EMBED_COLOR,
            image_url="https://raw.githubusercontent.com/PygameCommunityDiscord/"
            + f"PygameCommunityBot/main/assets/images/{fname}",
        )

        await emotion.update("happy", random.randint(10, 15))

    async def cmd_vibecheck(self):
        """
        ->type Play With Me :snake:
        ->signature pg!vibecheck
        ->description Check my mood.
        -----
        Implement pg!vibecheck, to check the snek's emotion
        """
        async with db.DiscordDB("emotions") as db_obj:
            all_emotions = db_obj.get({})

        if "depression" in all_emotions:
            value = all_emotions["depression"]["value"]
            all_emotions["depression"] = value

        emotion_percentage = vibecheck.get_emotion_percentage(all_emotions, round_by=-1)
        all_emotion_response = vibecheck.get_emotion_desc_dict(all_emotions)

        bot_emotion = max(
            emotion_percentage.keys(), key=lambda key: emotion_percentage[key]
        )
        msg = all_emotion_response[bot_emotion]["msg"]
        emoji_link = all_emotion_response[bot_emotion]["emoji_link"]

        if all_emotion_response[bot_emotion].get("override_emotion", None):
            bot_emotion = all_emotion_response[bot_emotion]["override_emotion"]

        color = pygame.Color(vibecheck.EMOTION_COLORS[bot_emotion])

        t = time.time()
        pygame.image.save(
            vibecheck.emotion_pie_chart(all_emotions, 400), f"temp{t}.png"
        )
        file = discord.File(f"temp{t}.png")

        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass

        embed_dict = {
            "title": f"The snek is {bot_emotion} right now!",
            "description": msg,
            "thumbnail_url": emoji_link,
            "footer_text": "This is currently in beta version, so the end product may look different",
            "footer_icon_url": "https://cdn.discordapp.com/emojis/844513909158969374.png?v=1",
            "image_url": f"attachment://temp{t}.png",
            "color": utils.color_to_rgb_int(color),
        }
        embed = embed_utils.create(**embed_dict)
        await self.invoke_msg.reply(file=file, embed=embed, mention_author=False)

        os.remove(f"temp{t}.png")

    @fun_command
    async def cmd_sorry(self):
        """
        ->type Play With Me :snake:
        ->signature pg!sorry
        ->description You were hitting me <:pg_bonk:780423317718302781> and you're now trying to apologize?
        Let's see what I'll say :unamused:
        -----
        Implement pg!sorry, to ask forgiveness from the bot after bonccing it
        """
        anger = await emotion.get("anger")
        if not anger:
            await embed_utils.replace(
                self.response_msg,
                title="Ask forgiveness from snek?",
                description="Snek is not angry. Awww, don't be sorry.",
            )
            return

        num = random.randint(0, 20)
        if num:
            await embed_utils.replace(
                self.response_msg,
                title="Ask forgiveness from snek?",
                description="Your pythonic lord accepts your apology.\n"
                + f"Now go to code again.\nAnger level is {max(anger - num, 0)}",
            )
            await emotion.update("anger", -num)
        else:
            await embed_utils.replace(
                self.response_msg,
                title="Ask forgiveness from snek?",
                description="How did you dare to boncc a snake?\nBold of you to"
                + " assume I would apologize to you, two-feet-standing being!\n"
                + f"The anger level is {anger}",
            )
