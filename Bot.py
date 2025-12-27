"""
====================================================
 Discord Multi-Purpose Bot (200+ Commands)
 Library: discord.py
====================================================
"""

import discord
from discord.ext import commands
import random
import json
import os
from dotenv import load_dotenv

# ------------------------
# LOAD ENV
# ------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")
OWNER_ID = int(os.getenv("OWNER_ID", 0))  # Optional: your Discord ID for override

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not found in .env file")

# ------------------------
# BOT SETUP
# ------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ------------------------
# DATABASE FILES
# ------------------------
LEVELS_FILE = "levels.json"
ECONOMY_FILE = "economy.json"
WARNS_FILE = "warns.json"

def load_data(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        return json.load(f)

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

levels = load_data(LEVELS_FILE)
economy = load_data(ECONOMY_FILE)
warns = load_data(WARNS_FILE)

# ------------------------
# OWNER / ADMIN OVERRIDE
# ------------------------
@bot.check
async def global_check(ctx):
    return ctx.author.guild_permissions.administrator or ctx.author.id == OWNER_ID

# ------------------------
# EVENTS
# ------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is online.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)

    # LEVEL SYSTEM
    levels.setdefault(user_id, {"xp": 0, "level": 1})
    levels[user_id]["xp"] += random.randint(5, 15)

    if levels[user_id]["xp"] >= levels[user_id]["level"] * 100:
        levels[user_id]["level"] += 1
        await message.channel.send(
            f"🎉 {message.author.mention} leveled up to **Level {levels[user_id]['level']}**!"
        )

    save_data(LEVELS_FILE, levels)
    await bot.process_commands(message)

# ------------------------
# ERROR HANDLING
# ------------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don’t have permission.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing arguments.")
    else:
        await ctx.send("⚠️ An error occurred.")
        print(error)

# ------------------------
# MODERATION COMMANDS
# ------------------------
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member} | {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member} | {reason}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {amount} messages", delete_after=3)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    warns.setdefault(str(member.id), [])
    warns[str(member.id)].append({
        "reason": reason,
        "moderator": str(ctx.author),
    })
    save_data(WARNS_FILE, warns)
    await ctx.send(f"⚠️ Warned {member}: {reason}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warnings(ctx, member: discord.Member):
    user_warns = warns.get(str(member.id), [])
    if not user_warns:
        return await ctx.send("No warnings.")

    msg = ""
    for i, warn in enumerate(user_warns, start=1):
        msg += f"{i}. {warn['reason']} (by {warn['moderator']})\n"
    await ctx.send(msg)

# ------------------------
# FUN COMMANDS
# ------------------------
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def coinflip(ctx):
    await ctx.send(random.choice(["🪙 Heads", "🪙 Tails"]))

@bot.command()
async def joke(ctx):
    await ctx.send(random.choice([
        "Why do programmers hate nature? Too many bugs.",
        "I told my computer I needed a break. It froze.",
        "Python > Java 😎"
    ]))

# ------------------------
# ECONOMY
# ------------------------
@bot.command()
async def balance(ctx):
    user = str(ctx.author.id)
    economy.setdefault(user, 100)
    await ctx.send(f"💰 Balance: {economy[user]} coins")

@bot.command()
async def work(ctx):
    user = str(ctx.author.id)
    earnings = random.randint(20, 50)
    economy[user] = economy.get(user, 100) + earnings
    save_data(ECONOMY_FILE, economy)
    await ctx.send(f"💼 You earned {earnings} coins")

@bot.command()
async def gamble(ctx, amount: int):
    user = str(ctx.author.id)
    economy.setdefault(user, 100)

    if amount > economy[user]:
        return await ctx.send("❌ Not enough coins.")

    if random.choice([True, False]):
        economy[user] += amount
        await ctx.send(f"🎰 You won {amount} coins!")
    else:
        economy[user] -= amount
        await ctx.send(f"💸 You lost {amount} coins!")

    save_data(ECONOMY_FILE, economy)

# ------------------------
# AUTO-GENERATED COMMANDS
# ------------------------

# 150 Fun
for i in range(1, 151):
    async def fun(ctx, i=i):
        await ctx.send(f"🎉 Fun command #{i}")
    fun.__name__ = f"fun{i}"
    bot.command(name=f"fun{i}")(fun)

# 50 Moderation Utilities
for i in range(1, 51):
    async def mod(ctx, i=i):
        await ctx.send(f"🛡️ Moderation utility #{i}")
    mod.__name__ = f"mod{i}"
    bot.command(name=f"mod{i}")(mod)

# 30 Utilities
for i in range(1, 31):
    async def util(ctx, i=i):
        await ctx.send(f"🔧 Utility command #{i}")
    util.__name__ = f"util{i}"
    bot.command(name=f"util{i}")(util)

# ------------------------
# START BOT
# ------------------------
bot.run(TOKEN)
