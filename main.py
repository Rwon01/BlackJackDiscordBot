from typing import Final
import os
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
server = [1016060727053783040]
bot = discord.Bot()

suits = {'Hearts': '♥️', 'Diamonds': '♦️', 'Clubs': '♣️', 'Spades': '♠️'}
ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
values = {rank: min(i + 2, 10) if rank not in ['J', 'Q', 'K', 'A'] else (11 if rank == 'A' else 10) for i, rank in enumerate(ranks)}

user_database = {}  # Stores user balances
active_games = {}  # Stores ongoing games

def deal_card():
    rank = random.choice(ranks)
    suit = random.choice(list(suits.keys()))
    return rank, suits[suit]

def format_hand(hand):
    return ' '.join([f"{card[0]}{card[1]}" for card in hand])

def calculate_score(hand):
    score = sum(values[card[0]] for card in hand)
    aces = sum(1 for card in hand if card[0] == 'A')
    while score > 21 and aces:
        score -= 10
        aces -= 1
    return score

@bot.slash_command(guild_ids=server, name='play', description='Start a Blackjack game')
async def play(ctx, bet_amount: discord.Option(int)):
    user_id = ctx.author.id
    bal = user_database.get(user_id, 0)
    if bal < bet_amount:
        await ctx.respond("Insufficient balance.")
        return

    user_database[user_id] -= bet_amount
    player_hand = [deal_card(), deal_card()]
    dealer_hand = [deal_card(), deal_card()]
    
    active_games[user_id] = {'player_hand': player_hand, 'dealer_hand': dealer_hand, 'bet': bet_amount}
    
    await ctx.respond(f"Your hand: {format_hand(player_hand)} (Score: {calculate_score(player_hand)})\nDealer's visible card: {format_hand([dealer_hand[0]])}")

@bot.slash_command(guild_ids=server, name='hit', description='Draw another card')
async def hit(ctx):
    user_id = ctx.author.id
    if user_id not in active_games:
        await ctx.respond("No active game. Use /play to start.")
        return
    
    game = active_games[user_id]
    game['player_hand'].append(deal_card())
    score = calculate_score(game['player_hand'])
    
    if score > 21:
        del active_games[user_id]
        await ctx.respond(f"Bust! You lost. Your hand: {format_hand(game['player_hand'])} (Score: {score})")
    else:
        await ctx.respond(f"Your hand: {format_hand(game['player_hand'])} (Score: {score})")

@bot.slash_command(guild_ids=server, name='stand', description='End your turn')
async def stand(ctx):
    user_id = ctx.author.id
    if user_id not in active_games:
        await ctx.respond("No active game. Use /play to start.")
        return
    
    game = active_games.pop(user_id)
    player_score = calculate_score(game['player_hand'])
    dealer_score = calculate_score(game['dealer_hand'])
    
    while dealer_score < 17:
        game['dealer_hand'].append(deal_card())
        dealer_score = calculate_score(game['dealer_hand'])
    
    if dealer_score > 21 or player_score > dealer_score:
        user_database[user_id] += game['bet'] * 2
        result = "You won!"
    elif player_score < dealer_score:
        result = "You lost."
    else:
        user_database[user_id] += game['bet']
        result = "It's a tie!"
    
    await ctx.respond(f"{result}\nYour hand: {format_hand(game['player_hand'])} (Score: {player_score})\nDealer's hand: {format_hand(game['dealer_hand'])} (Score: {dealer_score})")

@bot.slash_command(guild_ids=server, name='deposit', description='Admins can deposit money to a user')
@commands.has_permissions(administrator=True)
async def deposit(ctx, user: discord.Member, deposit_amount: discord.Option(int)):
    user_id = user.id
    user_database[user_id] = user_database.get(user_id, 0) + deposit_amount
    await ctx.respond(f"{user.mention} has been credited with ${deposit_amount}. New balance: ${user_database[user_id]}")

@bot.slash_command(guild_ids=server, name='balance', description='Check your balance')
async def balance(ctx):
    bal = user_database.get(ctx.author.id, 0)
    await ctx.respond(f"Balance: ${bal}")

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")

def main():
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
