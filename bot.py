# bot.py - COMPLETE FIXED VERSION with Playtime Bug Resolved
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
import random

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('DISCORD_GUILD')

# Initialize bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

# File for game data storage
DATA_FILE = "game_data.json"

# ============================================
# UTILITY FUNCTIONS
# ============================================

def load_data():
    """Load game data from JSON file"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    """Save game data to JSON file"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def init_user(user_id, data):
    """Initialize user if they don't exist"""
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {
            "balance": 1000,
            "bank": 0,
            "level": 1,
            "experience": 0,
            "items": {},
            "daily_claimed": None,
            "playtime_sessions": [],
            "current_game": None,
            "game_start_time": None
        }
    return data

# ============================================
# BOT EVENTS
# ============================================

@bot.event
async def on_ready():
    """Bot is ready and syncing commands"""
    print(f'✅ {bot.user} is now online!')
    print(f'📊 Serving {len(bot.guilds)} guild(s)')
    
    try:
        # Sync slash commands
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    # Set bot activity
    activity = discord.Activity(
        type=discord.ActivityType.watching, 
        name="/help for commands"
    )
    await bot.change_presence(activity=activity)

@bot.event
async def on_presence_update(before, after):
    """Track when users start/stop gaming"""
    if after.bot:
        return
    
    try:
        data = load_data()
        user_id = str(after.id)
        
        # Initialize user if needed
        data = init_user(user_id, data)
        
        # Get current activity
        before_activity = before.activity if before.activity else None
        after_activity = after.activity if after.activity else None
        
        # Check if user started playing a game
        if after_activity and after_activity.type == discord.ActivityType.playing:
            # Check if it's a new game session
            game_name = after_activity.name
            current_stored_game = data[user_id].get("current_game")
            
            # Only record if it's a new game or no game was being tracked
            if current_stored_game != game_name:
                # If there was a previous game, close that session first
                if current_stored_game and data[user_id].get("game_start_time"):
                    old_session = {
                        "game": current_stored_game,
                        "start": data[user_id]["game_start_time"],
                        "end": datetime.now().isoformat()
                    }
                    data[user_id]["playtime_sessions"].append(old_session)
                    print(f"📊 Saved session: {current_stored_game} for user {after.name}")
                
                # Start new game session
                data[user_id]["current_game"] = game_name
                data[user_id]["game_start_time"] = datetime.now().isoformat()
                print(f"🎮 {after.name} started playing: {game_name}")
        
        # Check if user stopped playing
        elif before_activity and before_activity.type == discord.ActivityType.playing:
            # User stopped playing
            if data[user_id].get("game_start_time") and data[user_id].get("current_game"):
                session = {
                    "game": data[user_id]["current_game"],
                    "start": data[user_id]["game_start_time"],
                    "end": datetime.now().isoformat()
                }
                data[user_id]["playtime_sessions"].append(session)
                
                # Calculate duration for log
                try:
                    start_dt = datetime.fromisoformat(session["start"])
                    end_dt = datetime.fromisoformat(session["end"])
                    duration_minutes = (end_dt - start_dt).total_seconds() / 60
                    print(f"📊 {after.name} stopped playing {session['game']} - Duration: {duration_minutes:.1f} minutes")
                except:
                    print(f"📊 Saved session for {after.name}")
                
                # Clear current game
                data[user_id]["current_game"] = None
                data[user_id]["game_start_time"] = None
        
        save_data(data)
    except Exception as e:
        print(f"Error in on_presence_update: {e}")

# ============================================
# ECONOMY COMMANDS
# ============================================

@bot.tree.command(name="balance", description="Check your balance")
async def balance(interaction: discord.Interaction):
    """Show user's balance"""
    data = load_data()
    user_id = str(interaction.user.id)
    data = init_user(user_id, data)
    save_data(data)
    
    user_data = data[user_id]
    balance = user_data["balance"]
    bank = user_data["bank"]
    level = user_data["level"]
    
    embed = discord.Embed(
        title=f"💰 {interaction.user.name}'s Balance",
        color=discord.Color.gold()
    )
    embed.add_field(name="Wallet", value=f"`{balance}` coins", inline=True)
    embed.add_field(name="Bank", value=f"`{bank}` coins", inline=True)
    embed.add_field(name="Level", value=f"`{level}`", inline=True)
    embed.add_field(name="Net Worth", value=f"`{balance + bank}` coins", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily reward")
async def daily(interaction: discord.Interaction):
    """Daily reward system"""
    data = load_data()
    user_id = str(interaction.user.id)
    data = init_user(user_id, data)
    
    last_claimed = data[user_id]["daily_claimed"]
    today = datetime.now().strftime("%Y-%m-%d")
    
    if last_claimed == today:
        await interaction.response.send_message("❌ Already claimed today! Come back tomorrow.", ephemeral=True)
        return
    
    reward = 500  # Daily reward
    data[user_id]["balance"] += reward
    data[user_id]["daily_claimed"] = today
    save_data(data)
    
    embed = discord.Embed(
        title="🎁 Daily Reward",
        description=f"You claimed your daily reward!",
        color=discord.Color.green()
    )
    embed.add_field(name="Reward", value=f"+{reward} coins", inline=True)
    embed.add_field(name="New Balance", value=f"`{data[user_id]['balance']}`", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Global leaderboard")
async def leaderboard(interaction: discord.Interaction):
    """Show top richest players"""
    data = load_data()
    
    # Sort users by net worth
    sorted_users = sorted(
        data.items(),
        key=lambda x: x[1]["balance"] + x[1]["bank"],
        reverse=True
    )[:10]
    
    embed = discord.Embed(
        title="💎 Server Leaderboard",
        color=discord.Color.gold()
    )
    
    if not sorted_users:
        embed.description = "No players yet!"
        await interaction.response.send_message(embed=embed)
        return
    
    for idx, (user_id, user_data) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            net_worth = user_data["balance"] + user_data["bank"]
            embed.add_field(
                name=f"#{idx} {user.name}",
                value=f"`{net_worth}` coins (Lvl {user_data['level']})",
                inline=False
            )
        except:
            pass
    
    await interaction.response.send_message(embed=embed)

# ============================================
# GAMING COMMANDS
# ============================================

@bot.tree.command(name="active_players", description="See who's gaming right now")
async def active_players(interaction: discord.Interaction):
    """List members currently gaming"""
    guild = interaction.guild
    gaming_members = []
    
    if not guild:
        await interaction.response.send_message("This command can only be used in a server.")
        return

    for member in guild.members:
        if member.activity and member.activity.type == discord.ActivityType.playing:
            gaming_members.append((member.name, member.activity.name))
    
    embed = discord.Embed(
        title="🎮 Currently Gaming",
        color=discord.Color.blurple()
    )
    
    if not gaming_members:
        embed.description = "Nobody's gaming right now! 😴"
    else:
        for name, game in gaming_members:
            embed.add_field(name=name, value=f"`{game}`", inline=False)
    
    embed.set_footer(text=f"Total: {len(gaming_members)} players")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="playtime", description="See someone's playtime stats")
async def playtime(interaction: discord.Interaction, member: discord.Member = None):
    """Show playtime statistics - FIXED VERSION"""
    if member is None:
        member = interaction.user
    
    data = load_data()
    user_id = str(member.id)
    data = init_user(user_id, data)
    
    sessions = data[user_id]["playtime_sessions"]
    
    # Calculate total playtime from COMPLETED sessions
    total_seconds = 0
    games_played = {}
    completed_sessions = 0
    
    print(f"📊 Calculating playtime for {member.name}")
    print(f"📊 Total stored sessions: {len(sessions)}")
    
    for session in sessions:
        try:
            start_str = session.get("start")
            end_str = session.get("end")
            game = session.get("game", "Unknown")
            
            if not start_str or not end_str:
                print(f"⚠️ Skipping incomplete session: {session}")
                continue
            
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            duration = (end - start).total_seconds()
            
            # Skip invalid durations
            if duration < 0 or duration > 86400:  # Skip if negative or > 24 hours
                print(f"⚠️ Skipping invalid duration: {duration}s for game {game}")
                continue
            
            total_seconds += duration
            completed_sessions += 1
            
            if game not in games_played:
                games_played[game] = 0
            games_played[game] += duration
            
            print(f"✅ Session: {game} - {duration/60:.1f} minutes")
            
        except Exception as e:
            print(f"❌ Error processing session: {e} - Session: {session}")
            continue
    
    # ADD ONGOING SESSION TIME (if currently playing)
    current_game = data[user_id].get("current_game")
    game_start_time = data[user_id].get("game_start_time")
    ongoing_duration = 0
    
    if current_game and game_start_time:
        try:
            start = datetime.fromisoformat(game_start_time)
            ongoing_duration = (datetime.now() - start).total_seconds()
            
            if ongoing_duration > 0 and ongoing_duration < 86400:  # Valid ongoing session
                total_seconds += ongoing_duration
                
                if current_game not in games_played:
                    games_played[current_game] = 0
                games_played[current_game] += ongoing_duration
                
                print(f"🎮 Ongoing session: {current_game} - {ongoing_duration/60:.1f} minutes")
        except Exception as e:
            print(f"❌ Error processing ongoing session: {e}")
    
    print(f"📊 Total playtime: {total_seconds/3600:.2f} hours")
    
    # Check if user has any playtime at all
    if total_seconds == 0 and completed_sessions == 0:
        await interaction.response.send_message(
            f"❌ {member.name} has no playtime data yet.\n"
            f"💡 Make sure Discord is showing your game activity!",
            ephemeral=True
        )
        return
    
    total_hours = total_seconds / 3600
    total_minutes = total_seconds / 60
    
    embed = discord.Embed(
        title=f"🕹️ {member.name}'s Playtime",
        color=discord.Color.purple()
    )
    
    # Show in hours if > 1 hour, otherwise minutes
    if total_hours >= 1:
        embed.add_field(name="Total Playtime", value=f"`{total_hours:.1f}` hours", inline=False)
    else:
        embed.add_field(name="Total Playtime", value=f"`{total_minutes:.1f}` minutes", inline=False)
    
    embed.add_field(name="Completed Sessions", value=f"`{completed_sessions}`", inline=True)
    
    # Show if currently playing
    if current_game and ongoing_duration > 0:
        ongoing_minutes = ongoing_duration / 60
        embed.add_field(
            name="🎮 Currently Playing", 
            value=f"`{current_game}`\n({ongoing_minutes:.1f} min)", 
            inline=True
        )
    
    # Top games
    if games_played:
        top_game = max(games_played, key=games_played.get)
        top_hours = games_played[top_game] / 3600
        top_minutes = games_played[top_game] / 60
        
        if top_hours >= 1:
            embed.add_field(name="Most Played Game", value=f"`{top_game}`\n({top_hours:.1f}h)", inline=False)
        else:
            embed.add_field(name="Most Played Game", value=f"`{top_game}`\n({top_minutes:.1f} min)", inline=False)
    
    embed.set_footer(text=f"Total sessions tracked: {len(sessions)}")
    
    await interaction.response.send_message(embed=embed)

# ============================================
# MINI GAMES
# ============================================

@bot.tree.command(name="coinflip", description="Flip a coin to gamble")
@app_commands.describe(amount="Amount to bet", choice="heads or tails")
async def coinflip(interaction: discord.Interaction, amount: int, choice: str):
    """Gamble coins on a coin flip (heads/tails)"""
    data = load_data()
    user_id = str(interaction.user.id)
    data = init_user(user_id, data)
    
    # Validate input
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return
    
    if data[user_id]["balance"] < amount:
        await interaction.response.send_message("❌ Insufficient balance!", ephemeral=True)
        return
    
    if choice.lower() not in ["heads", "tails", "h", "t"]:
        await interaction.response.send_message("❌ Choose 'heads' or 'tails'!", ephemeral=True)
        return
    
    # Normalize choice
    user_choice = "heads" if choice.lower() in ["heads", "h"] else "tails"
    result = random.choice(["heads", "tails"])
    won = result == user_choice
    
    # Update balance
    if won:
        data[user_id]["balance"] += amount
        msg = f"🎉 **You won!** {result.title()} came up!\n+{amount} coins"
        color = discord.Color.green()
    else:
        data[user_id]["balance"] -= amount
        msg = f"😢 **You lost!** {result.title()} came up.\n-{amount} coins"
        color = discord.Color.red()
    
    save_data(data)
    
    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=msg,
        color=color
    )
    embed.add_field(name="Your Choice", value=f"`{user_choice.title()}`", inline=True)
    embed.add_field(name="Result", value=f"`{result.title()}`", inline=True)
    embed.add_field(name="New Balance", value=f"`{data[user_id]['balance']}`", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dice", description="Roll dice")
@app_commands.describe(sides="Number of sides on the dice")
async def dice(interaction: discord.Interaction, sides: int = 6):
    """Roll a dice"""
    if sides < 2:
        await interaction.response.send_message("❌ Dice must have at least 2 sides!", ephemeral=True)
        return
    
    result = random.randint(1, sides)
    
    embed = discord.Embed(
        title="🎲 Dice Roll",
        description=f"You rolled a **{result}**!",
        color=discord.Color.blue()
    )
    embed.add_field(name="Sides", value=f"`{sides}`", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ============================================
# UTILITY COMMANDS
# ============================================

@bot.tree.command(name="help", description="Bot info and commands")
async def help(interaction: discord.Interaction):
    """Help menu"""
    embed = discord.Embed(
        title="🤖 Bot Commands",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="💰 Economy",
        value="""
`/balance` - Check your balance
`/daily` - Claim daily reward
`/leaderboard` - Top richest players
        """,
        inline=False
    )
    
    embed.add_field(
        name="🎮 Gaming",
        value="""
`/active_players` - Who's gaming now
`/playtime` - See playtime stats (optional: @member)
        """,
        inline=False
    )
    
    embed.add_field(
        name="🎲 Games",
        value="""
`/coinflip <amount> <heads|tails>` - Gamble coins
`/dice <sides>` - Roll dice
        """,
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Server stats")
async def stats(interaction: discord.Interaction):
    """Show server statistics"""
    data = load_data()
    
    total_balance = sum(u["balance"] + u["bank"] for u in data.values())
    total_users = len(data)
    
    embed = discord.Embed(
        title="📊 Server Statistics",
        color=discord.Color.gold()
    )
    if interaction.guild:
        embed.add_field(name="Members", value=f"`{interaction.guild.member_count}`", inline=True)
    embed.add_field(name="Tracked Players", value=f"`{total_users}`", inline=True)
    embed.add_field(name="Total Coins", value=f"`{total_balance}`", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ============================================
# RUN BOT
# ============================================

if __name__ == "__main__":
    bot.run(TOKEN)
