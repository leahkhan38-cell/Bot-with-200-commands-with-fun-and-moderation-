import os
import sys
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize the bot
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
bot = commands.Bot(command_prefix='!', intents=intents)

# Load extensions (commands, games, moderation, music)
initial_extensions = [
    'cogs.commands',
    'cogs.games',
    'cogs.moderation',
    'cogs.music'
]

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

    @bot.event
    async def on_ready():
        logging.info(f'{bot.user.name} has connected to Discord!')

    bot.run(TOKEN)
