from typing import Final
import os
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands
from pymongo import MongoClient
from discord.ui import Button, View
import time
import asyncio

load_dotenv()

# Connect to MongoDB
MONGO_URI: Final[str] = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["blackjack_db"]
balances = db["balances"]
vouchers = db["vouchers"]

TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
server = [1016060727053783040]
bot = discord.Bot()


@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")

async def load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with bot:
        await load()
        await bot.start(TOKEN)
        
asyncio.run(main())
