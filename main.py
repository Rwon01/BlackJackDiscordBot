from typing import Final
import os
from dotenv import load_dotenv
import discord
from response import get_response

import random as r

global user_database
user_database = dict()


load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
server = [1016060727053783040]
bot = discord.Bot()

@bot.slash_command(guild_ids = server, name = 'play', description = 'Play BJ')
async def play(ctx, bet_amount : discord.Option(int)):
    user_id = ctx.author.id
    bal = user_database.get(ctx.author.id, 0)
    if bal >= bet_amount and bal > 0:
        if user_id not in user_database:
            user_database[user_id] = 0
        user_database[user_id] -= bet_amount
        coinflip = r.choice([True,False])
        if coinflip:
            user_database[user_id] += bet_amount * 2
            await ctx.respond(f"You won! Bet: {bet_amount}")
        else:
            await ctx.respond(f"You lost! Bet: {bet_amount}")

    else: await  ctx.respond(f"Insufficient balance" )

 

@bot.slash_command(guild_ids = server, name = 'deposit', description = 'Deposit money')
async def deposit(ctx, deposit_amount : discord.Option(int)):
    user_id = ctx.author.id
    if user_id not in user_database:
        user_database[user_id] = 0
    user_database[user_id] += deposit_amount
    await ctx.respond(f"New balance : ${user_database.get(user_id)}")

@bot.slash_command(guild_ids = server, name = 'balance', description = 'Check your balance')
async def balance(ctx):
    balance = user_database.get(ctx.author.id, 0)
    await ctx.respond(f"${balance}")

@bot.event
async def on_ready():
    print(f"{bot.user} now logged in")


def main() -> None:
    bot.run(token=TOKEN)

if __name__ == '__main__':
    main()