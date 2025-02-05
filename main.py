from typing import Final
import os
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands
from pymongo import MongoClient
from discord.ui import Button, View

load_dotenv()

# Connect to MongoDB
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

def is_blackjack(hand):
    return len(hand) == 2 and any(card[0] == 'A' for card in hand) and any(card[0] in ['10', 'J', 'Q', 'K'] for card in hand)

def can_split(hand):
    return len(hand) == 2 and hand[0][0] == hand[1][0]

@bot.slash_command(guild_ids=server, name='play', description='Start a Blackjack game')
async def play(ctx, bet_amount: discord.Option(int)):
    user_id = ctx.author.id
    user_data = balances.find_one({"_id": user_id}) or {"balance": 0}
    bal = user_data["balance"]
    
    if bal < bet_amount:
        await ctx.respond("Insufficient balance.")
        return

    balances.update_one({"_id": user_id}, {"$inc": {"balance": -bet_amount}}, upsert=True)
    player_hand = [deal_card(), deal_card()]
    dealer_hand = [deal_card(), deal_card()]

    if is_blackjack(player_hand):
        winnings = int(bet_amount * 2.5)
        balances.update_one({"_id": user_id}, {"$inc": {"balance": winnings}})
        embed = discord.Embed(title="Blackjack!", description=f"You win 1.5x your bet!\nYour hand: {format_hand(player_hand)}", color=discord.Color.green())
        await ctx.respond(embed=embed)
        return

    active_games[user_id] = {'player_hand': [player_hand], 'dealer_hand': dealer_hand, 'bet': bet_amount, 'current_hand': 0}
    await update_game_message(ctx, user_id)

@bot.slash_command(guild_ids=server, name='deposit', description='Admins can deposit money to a user')
@commands.has_permissions(administrator=True)
async def deposit(ctx, user: discord.Member, deposit_amount: discord.Option(int)):
    user_id = user.id
    balances.update_one({"_id": user_id}, {"$inc": {"balance": deposit_amount}}, upsert=True)
    new_balance = balances.find_one({"_id": user_id})["balance"]
    await ctx.respond(f"{user.mention} has been credited with ${deposit_amount}. New balance: ${new_balance}")

@bot.slash_command(guild_ids=server, name='balance', description='Check your balance')
async def balance(ctx):
    user_id = ctx.author.id
    user_data = balances.find_one({"_id": user_id}) or {"balance": 0}
    await ctx.respond(f"Balance: ${user_data['balance']}")

async def update_game_message(ctx, user_id, interaction=None):
    game = active_games[user_id]
    player_hands = game['player_hand']
    dealer_hand = game['dealer_hand']
    current_hand = game['current_hand']
    
    embed = discord.Embed(
        title="Blackjack Game",
        description=f"Hand {current_hand + 1}/{len(player_hands)}\n"
                    f"Your hand: {format_hand(player_hands[current_hand])} (Score: {calculate_score(player_hands[current_hand])})\n"
                    f"Dealer's visible card: {format_hand([dealer_hand[0]])}",
        color=discord.Color.blue()
    )

    view = View()

    async def hit_callback(interaction: discord.Interaction):
        game['player_hand'][current_hand].append(deal_card())
        score = calculate_score(game['player_hand'][current_hand])
        if score > 21:
            embed.color = discord.Color.red()
            embed.description += f"\nBusted!"
            await move_to_next_hand(ctx, user_id, interaction)
        else:
            await update_game_message(ctx, user_id, interaction)

    async def stand_callback(interaction: discord.Interaction):
        await move_to_next_hand(ctx, user_id, interaction)

    async def double_down_callback(interaction: discord.Interaction):
        await double_down(ctx)

    async def split_callback(interaction: discord.Interaction):
        await split(ctx)

    hit_button = Button(label="Hit", style=discord.ButtonStyle.green)
    hit_button.callback = hit_callback
    view.add_item(hit_button)

    stand_button = Button(label="Stand", style=discord.ButtonStyle.red)
    stand_button.callback = stand_callback
    view.add_item(stand_button)

    double_down_button = Button(label="Double Down", style=discord.ButtonStyle.blurple)
    double_down_button.callback = double_down_callback
    view.add_item(double_down_button)

    split_button = Button(label="Split", style=discord.ButtonStyle.gray)
    split_button.callback = split_callback
    view.add_item(split_button)

    if interaction:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await ctx.respond(embed=embed, view=view)

async def move_to_next_hand(ctx, user_id, interaction):
    game = active_games[user_id]
    if game['current_hand'] + 1 < len(game['player_hand']):
        game['current_hand'] += 1
        await update_game_message(ctx, user_id, interaction)
    else:
        await dealer_play(ctx, user_id, interaction)

async def dealer_play(ctx, user_id, interaction):
    game = active_games[user_id]
    dealer_hand = game['dealer_hand']

    while calculate_score(dealer_hand) < 17:
        dealer_hand.append(deal_card())

    dealer_score = calculate_score(dealer_hand)
    embed = discord.Embed(title="Game Over", color=discord.Color.orange())

    results = []
    for i, hand in enumerate(game['player_hand']):
        player_score = calculate_score(hand)
        if player_score > 21:
            results.append(f"Hand {i+1}: **Busted** ❌")
        elif dealer_score > 21 or player_score > dealer_score:
            winnings = game['bet'] * 2
            balances.update_one({"_id": user_id}, {"$inc": {"balance": winnings}})
            results.append(f"Hand {i+1}: **You win!** ✅")
        elif player_score < dealer_score:
            results.append(f"Hand {i+1}: **Dealer wins** ❌")
        else:
            balances.update_one({"_id": user_id}, {"$inc": {"balance": game['bet']}})
            results.append(f"Hand {i+1}: **Push (Tie)** 🤝")

    embed.description = f"Dealer's hand: {format_hand(dealer_hand)} (Score: {dealer_score})\n\n" + "\n".join(results)
    await interaction.response.edit_message(embed=embed, view=View())
    del active_games[user_id]

@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")

if __name__ == "__main__":
    bot.run(TOKEN)
