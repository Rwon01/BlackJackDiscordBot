from typing import Final
import os
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands
from pymongo import MongoClient
from discord.ui import Button, View
from main import *
import time


@bot.slash_command(guilds_server = server, name = 'crash', description = "start a game of crash")
@commands.has_permissions(administrator=True)
async def crash(ctx, bet : discord.Option(int)):
    currentTime = time.time()

    while currentTime < currentTime + 5:
        await ctx.respond(time.time())

    return

