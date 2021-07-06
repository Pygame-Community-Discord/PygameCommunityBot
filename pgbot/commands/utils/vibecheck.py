"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines several functions used to get the pie chart of the bot's emotions
"""

from __future__ import annotations

import math
import os

import pygame

from pgbot import emotion

EMOTIONS_PER_ROW = 2
NEGATIVE_EMOTIONS = {"bored": "exhausted", "happy": "sad"}
EMOTION_COLORS = {
    "happy": (230, 28, 226),
    "sad": (11, 117, 217),
    "anger": (230, 36, 18),
    "bored": (230, 181, 18),
    "exhausted": (235, 127, 19),
    "confused": (19, 235, 228),
    "depression": (28, 28, 230),
}


def get_emotion_desc_dict(emotions: dict[str, int]):
    """
    Get emotion description dict from emotion dict
    """
    return {
        "happy": {
            "msg": "I feel... happi!\n"
            "While I am happi, I'll make more dad jokes (Spot the dad joke in there?)\n"
            "However, don't bonk me or say 'ded chat', as that would make me sad.\n"
            f"*The snek's happiness level is `{emotions.get('happy', '0')}`, "
            "don't let it go to zero!*",
            "emoji_link": "https://cdn.discordapp.com/emojis/837389387024957440.png?v=1",
        },
        "sad": {
            "msg": "I'm sad...\n"
            "I don't feel like making any jokes. This is your fault, "
            "**don't make me sad.**\nPet me pls :3\n"
            f"*The snek's sadness level is `{-emotions.get('happy', 0)}`, play with "
            "it to cheer it up*",
            "emoji_link": "https://cdn.discordapp.com/emojis/824721451735056394.png?v=1",
        },
        "exhausted": {
            "msg": "I'm exhausted. \nI ran too many commands, "
            "so I'll be resting for a while..\n"
            "Don't try to make me run commands for now, I'll most likely "
            "just ignore it..\n"
            f"*The snek's exhaustion level is `{-emotions.get('bored', 0)}`. "
            "To make its exhaustion go down, let it rest for a bit.*",
            "emoji_link": None,
        },
        "bored": {
            "msg": "I'm booooooooored...\nNo one is spending time with me, "
            "and I feel lonely :pg_depressed:\n"
            f"*The snek's boredom level is `{emotions.get('bored', '0')}`, run "
            "more command(s) to improve its mood.*",
            "emoji_link": "https://cdn.discordapp.com/emojis/823502668500172811.png?v=1",
        },
        "confused": {
            "msg": "I'm confused!\nEither there were too many exceptions in my code, "
            "or too many commands were used wrongly!\n"
            f"*The snek's confusion level is `{emotions.get('confused', '0')}`, "
            "to lower its level of confusion, use proper command syntax.*",
            "emoji_link": "https://cdn.discordapp.com/emojis/837402289709907978.png?v=1",
        },
        "anger": {
            "msg": "I'm angry!\nI've been bonked too many times, you'd be "
            "angry too if someone bonked you 50+ times :unamused:\n"
            "No jokes, no quotes. :pg_angry:. Don't you dare pet me!\n"
            f"*The snek's anger level is `{emotions.get('anger', '0')}`, "
            "ask for its forgiveness to calm it down.*",
            "emoji_link": "https://cdn.discordapp.com/emojis/779775305224159232.gif?v=1",
            "override_emotion": "anger",
        },
        "depression": {
            f"msg": "I'm depressed...\nI've been sad too long, make me happy to "
            f"lift me out of depression...\n"
            f"*The snek's depression level is `{round(emotions.get('depression', 0), 3)}`, "
            f"make it happy for it to slowly become less depressed.*",
            "emoji_link": "https://cdn.discordapp.com/emojis/845321616094789712.png?v=1",
        },
    }


def generate_pie_slice(
    center_x: int, center_y: int, radius: int, start_angle: int, end_angle: int
):
    """
    Generate slice of the pie in the output
    """
    p = [(center_x, center_y)]

    # cover a bit more angle so that the boundaries are fully covered
    for angle in range(start_angle - 91, end_angle - 89):
        x = center_x + int(radius * math.cos(math.radians(angle)))
        y = center_y + int(radius * math.sin(math.radians(angle)))
        p.append((x, y))
    return p


def get_emotion_percentage(emotions: dict[str, int], round_by: int = 1):
    """
    Express emotions in terms of percentages, split complementary emotions into
    their own emotions
    """
    raw_emotion_percentage = {}
    for key, value in emotions.items():
        percentage = value / emotion.EMOTION_CAPS[key][1] * 100
        if percentage < 0:
            percentage = -percentage
            key = NEGATIVE_EMOTIONS[key]
        raw_emotion_percentage[key] = percentage

    sum_of_emotions = sum([i for i in raw_emotion_percentage.values()])
    emotion_percentage = {
        key: round(raw_emotion / sum_of_emotions * 100, round_by)
        if round_by != -1
        else raw_emotion / sum_of_emotions * 100
        for key, raw_emotion in sorted(
            raw_emotion_percentage.items(), key=lambda item: item[1], reverse=True
        )
    }

    return emotion_percentage


def emotion_pie_chart(emotions: dict[str, int], pie_radius: int):
    """
    Generates a pie chart, given emotions and pie radius
    Emotions must be in "raw form", like
    {"happy": 34, "bored": -35, "anger": 89, "confused": 499}
    """
    font = pygame.font.Font(os.path.join("assets", "tahoma.ttf"), 30)
    font.bold = True

    image = pygame.Surface((pie_radius * 2, pie_radius * 2 + 30 * len(emotions)), flags=pygame.SRCALPHA)
    image.fill((0, 0, 0, 0))

    emotion_percentage = get_emotion_percentage(emotions)
    emotion_pie_angle = {
        key: percentage / 100 * 360 for key, percentage in emotion_percentage.items()
    }

    start_angle = 0
    for key, angle in emotion_pie_angle.items():
        if round(angle) != 0:
            pygame.draw.polygon(
                image,
                EMOTION_COLORS[key],
                generate_pie_slice(
                    pie_radius,
                    pie_radius,
                    pie_radius,
                    start_angle,
                    start_angle + round(angle),
                ),
            )
            start_angle += round(angle)

    pygame.draw.circle(
        image, (255, 255, 255), (pie_radius, pie_radius), pie_radius, width=10
    )

    i = 0
    txt_x = 0
    txt_y = pie_radius * 2
    for bot_emotion, percentage in emotion_percentage.items():
        txt = font.render(
            f"{bot_emotion.title()} - {percentage}%", True, EMOTION_COLORS[bot_emotion]
        )
        txt_rect = txt.get_rect(topleft=(txt_x, txt_y))
        image.blit(txt, txt_rect)

        pygame.draw.rect(
            image,
            EMOTION_COLORS[bot_emotion],
            (int(txt_x + pie_radius * 1.8 / EMOTIONS_PER_ROW), txt_y, 20, 40),
        )

        if i % EMOTIONS_PER_ROW != EMOTIONS_PER_ROW - 1:
            txt_x += pie_radius * 2 / EMOTIONS_PER_ROW
        else:
            txt_x = 0
            txt_y += 40
        i += 1

    return image
