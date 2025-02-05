from typing import Final
import os
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands
from pymongo import MongoClient
from discord.ui import Button, View

load_dotenv()

MONGO_URI: Final[str] = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["blackjack_db"]
balances = db["balances"]

TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
server = [1016060727053783040]
bot = discord.Bot()

suits = {'Hearts': '♥️', 'Diamonds': '♦️', 'Clubs': '♣️', 'Spades': '♠️'}
ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
values = {rank: min(i + 2, 10) if rank not in ['J', 'Q', 'K', 'A'] else (11 if rank == 'A' else 10) for i, rank in enumerate(ranks)}

active_games = {}

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

def can_split(hand):
    return len(hand) == 2 and hand[0][0] == hand[1][0]

async def update_game_message(ctx, user_id, interaction=None):
    game = active_games[user_id]
    current_hand = game['current_hand']
    embed = discord.Embed(
        title="Blackjack Game",
        description=f"Your hand: {format_hand(game['player_hand'][current_hand])} (Score: {calculate_score(game['player_hand'][current_hand])})\n"
                    f"Dealer's visible card: {format_hand([game['dealer_hand'][0]])}",
        color=discord.Color.blue()
    )
    view = View()
    
    async def hit_callback(interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        game['player_hand'][current_hand].append(deal_card())
        if calculate_score(game['player_hand'][current_hand]) > 21:
            await move_to_next_hand(ctx, user_id, interaction)
        else:
            await update_game_message(ctx, user_id, interaction)
    
    async def stand_callback(interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        await move_to_next_hand(ctx, user_id, interaction)
    
    async def double_down_callback(interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        await double_down(ctx)
    
    async def split_callback(interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        await split(ctx)
    
    buttons = [
        ("Hit", discord.ButtonStyle.green, hit_callback),
        ("Stand", discord.ButtonStyle.red, stand_callback),
        ("Double Down", discord.ButtonStyle.blurple, double_down_callback),
        ("Split", discord.ButtonStyle.gray, split_callback)
    ]
    
    for label, style, callback in buttons:
        button = Button(label=label, style=style)
        button.callback = callback
        view.add_item(button)
    
    if interaction:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        message = await ctx.respond(embed=embed, view=view)
        active_games[user_id]['message'] = message
