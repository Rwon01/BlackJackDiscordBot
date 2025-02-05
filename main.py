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

    user_database[user_id] -= bet_amount
    player_hand = [deal_card(), deal_card()]
    dealer_hand = [deal_card(), deal_card()]

    if is_blackjack(player_hand):
        user_database[user_id] += int(bet_amount * 2.5)
        embed = discord.Embed(title="Blackjack!", description=f"You win 1.5x your bet!\nYour hand: {format_hand(player_hand)}", color=discord.Color.green())
        await ctx.respond(embed=embed)
        return

    active_games[user_id] = {'player_hand': [player_hand], 'dealer_hand': dealer_hand, 'bet': bet_amount}

    embed = discord.Embed(
        title="Blackjack Game",
        description=f"Your hand: {format_hand(player_hand)} (Score: {calculate_score(player_hand)})\nDealer's visible card: {format_hand([dealer_hand[0]])}",
        color=discord.Color.blue()
    )

    view = View()

    # HIT Button
    hit_button = Button(label="Hit", style=discord.ButtonStyle.green)

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

    # STAND Button
    stand_button = Button(label="Stand", style=discord.ButtonStyle.red)

    async def stand_callback(interaction: discord.Interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        # Dealer plays
        dealer_hand = active_games[user_id]['dealer_hand']
        while calculate_score(dealer_hand) < 17:
            dealer_hand.append(deal_card())

        dealer_score = calculate_score(dealer_hand)
        player_score = calculate_score(active_games[user_id]['player_hand'][0])

        if dealer_score > 21 or player_score > dealer_score:
            user_database[user_id] += bet_amount * 2
            result = "You win!"
            color = discord.Color.green()
        elif player_score < dealer_score:
            result = "Dealer wins!"
            color = discord.Color.red()
        else:
            user_database[user_id] += bet_amount  # Refund bet
            result = "It's a tie!"
            color = discord.Color.orange()

        embed.color = color
        embed.description = f"Your hand: {format_hand(active_games[user_id]['player_hand'][0])} (Score: {player_score})\n" \
                            f"Dealer's hand: {format_hand(dealer_hand)} (Score: {dealer_score})\n\n{result}"
        view.clear_items()
        await interaction.response.edit_message(embed=embed, view=view)

    stand_button.callback = stand_callback
    view.add_item(stand_button)

    # SPLIT Button (if allowed)
    split_button = Button(label="Split", style=discord.ButtonStyle.blurple, disabled=not can_split(player_hand))

    async def split_callback(interaction: discord.Interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        user_database[user_id] -= bet_amount  # Deduct additional bet
        hand1 = [player_hand[0], deal_card()]
        hand2 = [player_hand[1], deal_card()]
        active_games[user_id]['player_hand'] = [hand1, hand2]

        embed.description = f"Split your hand!\nHand 1: {format_hand(hand1)} (Score: {calculate_score(hand1)})\n" \
                            f"Hand 2: {format_hand(hand2)} (Score: {calculate_score(hand2)})\n" \
                            f"Dealer's visible card: {format_hand([dealer_hand[0]])}"
        split_button.disabled = True  # Prevent multiple splits
        await interaction.response.edit_message(embed=embed, view=view)

    split_button.callback = split_callback
    view.add_item(split_button)

    message = await ctx.respond(embed=embed, view=view)
    active_games[user_id]['message'] = message


@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")

if __name__ == "__main__":
    bot.run(TOKEN)