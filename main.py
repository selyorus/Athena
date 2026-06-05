import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
script_dir = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_dir / '.env')

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = ","
OWNER_IDS = {1282966278717444182, 1124274518748315738}

if not TOKEN:
    raise ValueError("ERROR: Token Might be invalid or you didn't set up .env, idiot.")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None, owner_ids=OWNER_IDS)

# Load all cogs
async def load_extensions():
    await bot.load_extension('cogs.events')
    await bot.load_extension('cogs.embeds')
    await bot.load_extension('cogs.moderation')
    await bot.load_extension('cogs.automod')
    await bot.load_extension('cogs.utilities')
    await bot.load_extension('cogs.developer')
    await bot.load_extension('cogs.slash_commands')

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Prefix: {PREFIX}")
    await bot.change_presence(status=discord.Status.online)

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
