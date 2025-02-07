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
    if len(hand) != 2:
        return False
    value_map = {'K': 10, 'Q': 10, 'J': 10, '10': 10}  # Face cards and 10s are equivalent
    rank1 = hand[0][0]
    rank2 = hand[1][0]

    return (rank1 == rank2) or (value_map.get(rank1, rank1) == value_map.get(rank2, rank2))

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
        balances.update_one({"_id": user_id}, {"$inc": {"hands_won": 1}}, upsert=True)

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
    user_bal = balances.find_one({"_id": ctx.author.id}) or {"balance": 0}
    
    embed = discord.Embed(
        title="Blackjack Game",
        description=(
            f"Hand {current_hand + 1}/{len(player_hands)}\n"
            f"Your hand: {format_hand(player_hands[current_hand])} "
            f"(Score: {calculate_score(player_hands[current_hand])})\n"
            f"Dealer's visible card: {format_hand([dealer_hand[0]])}\n"
            f"Your current balance: ${user_bal['balance']}"
        ),
        color=discord.Color.blue()
    )

    view = View()

    # HIT Button
    hit_button = Button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        game['player_hand'][current_hand].append(deal_card())
        score = calculate_score(game['player_hand'][current_hand])
        if score > 21:
            await move_to_next_hand(ctx, user_id, interaction)
        else:
            await update_game_message(ctx, user_id, interaction)
    hit_button.callback = hit_callback
    view.add_item(hit_button)

    # STAND Button
    stand_button = Button(label="Stand", style=discord.ButtonStyle.red)
    async def stand_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        await move_to_next_hand(ctx, user_id, interaction)
    stand_button.callback = stand_callback
    view.add_item(stand_button)

    # DOUBLE DOWN Button
    double_down_button = Button(label="Double Down", style=discord.ButtonStyle.blurple)
    async def double_down_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        await double_down(ctx, interaction)  # Pass interaction correctly
    double_down_button.callback = double_down_callback
    view.add_item(double_down_button)

    # SPLIT Button
    split_button = Button(label="Split", style=discord.ButtonStyle.gray)
    async def split_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("You can't use this button!", ephemeral=True)
            return
        await split(ctx, interaction)
    split_button.callback = split_callback
    view.add_item(split_button)

    # If interaction is not None and hasn't been responded to yet
    if interaction and not interaction.response.is_done():
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

    # Defer the interaction to prevent InteractionResponded error
    await interaction.response.defer()

    while calculate_score(dealer_hand) < 17:
        dealer_hand.append(deal_card())

    dealer_score = calculate_score(dealer_hand)
    embed = discord.Embed(title="Game Over", color=discord.Color.orange())

    results = []
    for i, hand in enumerate(game['player_hand']):
        player_score = calculate_score(hand)
        if player_score > 21:
            results.append(f"Hand {i+1}: **Busted** ❌")
            balances.update_one({"_id": user_id}, {"$inc": {"hands_lost": 1}}, upsert=True)
        elif dealer_score > 21 or player_score > dealer_score:
            balances.update_one({"_id": user_id}, {"$inc": {"balance": game['bet'] * 2}})
            balances.update_one({"_id": user_id}, {"$inc": {"hands_won": 1}}, upsert=True)
            results.append(f"Hand {i+1}: **You win!** ✅")
        elif player_score < dealer_score:
            results.append(f"Hand {i+1}: **Dealer wins** ❌")
            balances.update_one({"_id": user_id}, {"$inc": {"hands_lost": 1}}, upsert=True)
        else:
            # In case of a tie, return the bet to the player
            balances.update_one({"_id": user_id}, {"$inc": {"balance": game['bet']}})
            results.append(f"Hand {i+1}: **Push (Tie)** 🤝")

    embed.description = f"Dealer's hand: {format_hand(dealer_hand)} (Score: {dealer_score})\n\n" + "\n".join(results)
    
    # Edit the original message with the final game result
    await interaction.edit_original_response(embed=embed, view=View())
    del active_games[user_id]

async def double_down(ctx, interaction: discord.Interaction):

    if interaction.user.id != ctx.author.id:
        await interaction.response.send_message("You can't use this button!", ephemeral=True)
        return
    
    user_id = ctx.author.id
    game = active_games.get(user_id)

    if not game:
        await interaction.response.send_message("No active game found.", ephemeral=True)
        return

    current_hand = game['current_hand']
    hand = game['player_hand'][current_hand]

    # Ensure that the player can only double down if they have exactly 2 cards
    if len(hand) != 2:
        await interaction.response.send_message("You can only double down with exactly 2 cards.", ephemeral=True)
        return

    bet_amount = game['bet']
    user_data = balances.find_one({"_id": user_id}) or {"balance": 0}

    if user_data["balance"] < bet_amount:
        await interaction.response.send_message("Not enough balance to double down!", ephemeral=True)
        return

    # Deduct extra bet amount (to double the bet)
    balances.update_one({"_id": user_id}, {"$inc": {"balance": -bet_amount}})

    # Add one card and update the hand
    hand.append(deal_card())

    # Update the bet amount for the current hand (double the bet)
    game['bet'] *= 2

    # After doubling down, automatically move to the next hand
    await move_to_next_hand(ctx, user_id, interaction)

async def split(ctx, interaction: discord.Interaction):
    if interaction.user.id != ctx.author.id:
        await interaction.response.send_message("You can't use this button!", ephemeral=True)
        return
    
    user_id = ctx.author.id
    game = active_games.get(user_id)

    if not game:
        await interaction.response.send_message("No active game found.", ephemeral=True)
        return

    current_hand = game['current_hand']
    hand = game['player_hand'][current_hand]

    if not can_split(hand):
        await interaction.response.send_message("You can't split this hand!", ephemeral=True)
        return

    bet_amount = game['bet']
    user_data = balances.find_one({"_id": user_id}) or {"balance": 0}

    if user_data["balance"] < bet_amount:
        await interaction.response.send_message("Not enough balance to split!", ephemeral=True)
        return

    # Deduct extra bet amount
    balances.update_one({"_id": user_id}, {"$inc": {"balance": -bet_amount}})

    # Create two hands
    new_hand1 = [hand[0], deal_card()]
    new_hand2 = [hand[1], deal_card()]

    # Replace current hand and add new one
    game['player_hand'][current_hand] = new_hand1
    game['player_hand'].append(new_hand2)

    # Update the game message
    await update_game_message(ctx, user_id, interaction)

#######################################################################


vouchers = db["vouchers"]
@bot.slash_command(guild_ids=server, name='redeem', description='Redeem a money voucher')
async def redeem(ctx, code: discord.Option(str)):
    user_id = ctx.author.id
    user_data = vouchers.find_one({"text": code})

    if user_data:
        value = user_data["value"]  # Fix: Access 'value' as a string key
        
        # Credit user balance
        balances.update_one({"_id": user_id}, {"$inc": {"balance": value}}, upsert=True)
        
        # Remove the redeemed voucher from the database
        vouchers.delete_one({"text": code})

        await ctx.respond(f"Voucher redeemed! You received ${value}.")
    else:
        await ctx.respond("Invalid or already redeemed voucher.")


@bot.slash_command(guild_ids=server, name='transfer', description='Transfer your balance to another user')
async def transfer(ctx,  transfer_user : discord.Member, transfer_amount: discord.Option(int)):
    user_id = ctx.author.id
    user_data = balances.find_one({"_id": user_id}) or {"balance": 0}
    bal = user_data["balance"]
    
    if bal < transfer_amount:
        await ctx.respond("Insufficient balance.")
        return
    

    balances.update_one({"_id": user_id}, {"$inc": {"balance": -transfer_amount}}, upsert=True)
    balances.update_one({"_id": transfer_user.id}, {"$inc": {"balance": transfer_amount}}, upsert=True)

    new_balance = balances.find_one({"_id": transfer_user.id})["balance"]
    await ctx.respond(f"[Transfer] {transfer_user.mention} has been credited with ${transfer_amount}. New balance: ${new_balance}")

@bot.slash_command(guild_ids=server, name="stats", description="Show your Blackjack stats")
async def stats(ctx):
    user_id = ctx.author.id
    user_data = balances.find_one({"_id": user_id})
    
    if user_data:
        hands_won = user_data.get("hands_won", 0)
        hands_lost = user_data.get("hands_lost", 0)
        win_ratio = hands_won / hands_lost if hands_lost > 0 else hands_won  # Avoid division by zero
        
        await ctx.respond(
            f""" **{ctx.author.name}'s Stats**
            🃏 Hands won: {hands_won}
            ❌ Hands lost: {hands_lost}
            🏆 Win ratio: {win_ratio:.2f} """
        )
    else:
        await ctx.respond("No stats found.")

@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")

if __name__ == "__main__":
    bot.run(TOKEN)
