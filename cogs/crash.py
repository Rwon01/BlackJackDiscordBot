import discord
from discord.ext import commands
import asyncio
import time
import random
from main import server


class Crash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@commands.Cog.Listener()
async def on_ready(self):
    print(f"{__name__} is online and loaded")

#CRASH

# Store player bets and states
players = {}
crash_active = False
betting_active = False
multiplier = 1.0

def reset_game():
    global players, crash_active, betting_active, multiplier
    players = {}
    crash_active = False
    betting_active = False
    multiplier = 1.0

class CrashView(discord.ui.View):
    def __init__(self, ctx, start_time):
        super().__init__()
        self.ctx = ctx
        self.start_time = start_time
        self.crashed = False
        self.task = asyncio.create_task(self.run_crash())

    async def run_crash(self):
        global crash_active, betting_active, multiplier
        betting_active = True
        msg = await self.ctx.send("Game starting in 10 seconds! Use `/joincrash <bet>` to place your bet!")
        await asyncio.sleep(10)
        betting_active = False

        crash_active = True
        await msg.edit(content=f"Game started! Crash point: ???")
        start_time = time.time()

        while True:
            elapsed_time = time.time() - start_time
            multiplier = round(1.0 + elapsed_time * 0.1, 2)
            await msg.edit(content=f"Multiplier: x{multiplier:.2f}")
            await asyncio.sleep(0.1)
            
            # Probability of crashing increases with multiplier
            crash_chance = min(1, (multiplier / 5.0))
            if random.random() < crash_chance:
                break
        
        self.crashed = True
        await msg.edit(content=f"CRASHED at x{multiplier:.2f}! 🎲")
        
        # Check player withdrawals
        for user_id, data in players.items():
            if data['active']:
                players[user_id]['bet'] = 0  # They lost their bet
        
        crash_active = False
        await asyncio.sleep(60)  # Restart game in 1 minute
        reset_game()

    @discord.ui.button(label="Withdraw", style=discord.ButtonStyle.green)
    async def withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in players and players[interaction.user.id]['active']:
            winnings = round(players[interaction.user.id]['bet'] * multiplier, 2)
            players[interaction.user.id]['active'] = False
            await interaction.response.send_message(f"{interaction.user.mention} withdrew at x{multiplier:.2f} and won {winnings} coins! 💰", ephemeral=True)
        else:
            await interaction.response.send_message("You have no active bet!", ephemeral=True)

@commands.slash_command(guild_ids=server, name="crash", description="Start a game of Crash!")
@commands.has_permissions(administrator=True)
async def crash(ctx):
    if crash_active or betting_active:
        await ctx.respond("A game is already running! Wait for the next round.", ephemeral=True)
        return
    
    await ctx.send("A new crash game has started! Use `/joincrash <bet>` to place your bet.")
    view = CrashView(ctx, time.time())
    await ctx.send("Game starting...", view=view)

@commands.slash_command(guild_ids=server, name="joincrash", description="Join an active game of Crash!")
async def joincrash(ctx, bet: int):
    if not betting_active:
        await ctx.respond("Betting is currently closed. Wait for the next round.", ephemeral=True)
        return
    
    if bet <= 0:
        await ctx.respond("Bet must be greater than 0!", ephemeral=True)
        return
    
    players[ctx.author.id] = {'bet': bet, 'active': True}
    await ctx.respond(f"{ctx.author} joined the game with a bet of {bet} coins!")


async def setup(bot):
    await bot.add_cog(Crash(bot))