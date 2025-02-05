from typing import Final
import os
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ui import Button, View

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

def is_blackjack(hand):
    return len(hand) == 2 and any(card[0] == 'A' for card in hand) and any(card[0] in ['10', 'J', 'Q', 'K'] for card in hand)

def can_split(hand):
    return len(hand) == 2 and hand[0][0] == hand[1][0]

@bot.slash_command(guild_ids=server, name='play', description='Start a Blackjack game')
async def play(ctx, bet_amount: discord.Option(int)):
    user_id = ctx.author.id
    bal = user_database.get(user_id, 0)
    if bal < bet_amount:
        await ctx.respond("Insufficient balance.")
        return

@bot.slash_command(guild_ids=server, name='deposit', description='Deposit money into a user\'s account')
async def deposit(ctx, user: discord.Option(discord.User), amount: discord.Option(int)):
    # Check if the user is an admin
    if not any(role.permissions.administrator for role in ctx.author.roles):
        await ctx.respond("You do not have permission to perform this action.")
        return

    # Get the user's balance and update it
    user_id = user.id
    current_balance = user_database.get(user_id, 0)
    new_balance = current_balance + amount
    user_database[user_id] = new_balance

    # Confirm the deposit
    await ctx.respond(f"Successfully deposited {amount} into {user.name}'s account. New balance: {new_balance}")


    user_database[user_id] -= bet_amount
    player_hand = [deal_card(), deal_card()]
    dealer_hand = [deal_card(), deal_card()]
    
    if is_blackjack(player_hand):
        user_database[user_id] += int(bet_amount * 2.5)
        embed = discord.Embed(title="Blackjack!", description=f"You win 1.5x your bet!\nYour hand: {format_hand(player_hand)}", color=discord.Color.green())
        await ctx.respond(embed=embed)
        return
    
    active_games[user_id] = {'player_hand': [player_hand], 'dealer_hand': dealer_hand, 'bet': bet_amount}
    
    embed = discord.Embed(title="Blackjack Game", description=f"Your hand: {format_hand(player_hand)} (Score: {calculate_score(player_hand)})\nDealer's visible card: {format_hand([dealer_hand[0]])}", color=discord.Color.blue())
    
    view = View()
    hit_button = Button(label="Hit", style=discord.ButtonStyle.green)
    stand_button = Button(label="Stand", style=discord.ButtonStyle.red)
    split_button = Button(label="Split", style=discord.ButtonStyle.blurple, disabled=not can_split(player_hand))
    
    async def hit_callback(interaction: discord.Interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        new_card = deal_card()
        active_games[user_id]['player_hand'][0].append(new_card)
        score = calculate_score(active_games[user_id]['player_hand'][0])
        if score > 21:
            embed.color = discord.Color.red()
            embed.description += f"\nBusted! You lose."
            view.clear_items()
        else:
            embed.description = f"Your hand: {format_hand(active_games[user_id]['player_hand'][0])} (Score: {score})\nDealer's visible card: {format_hand([dealer_hand[0]])}"
        await interaction.response.edit_message(embed=embed, view=view)
    
    hit_button.callback = hit_callback
    view.add_item(hit_button)
    view.add_item(stand_button)
    view.add_item(split_button)
    
    message = await ctx.respond(embed=embed, view=view)
    active_games[user_id]['message'] = message


@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")

if __name__ == "__main__":
    bot.run(TOKEN)