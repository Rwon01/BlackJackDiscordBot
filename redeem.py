from main import bot, server, client, db
import discord

db = client["blackjack_db"]
vouchers = db["vouchers"]

@bot.slash_command(guild_ids=server, name='redeem', description='Redeem a money voucher')
async def redeem(ctx, code: discord.Option(str)):

    user_data = vouchers.find_one({"text": code})

    if user_data:
        value = user_data[value]
        print(value)


