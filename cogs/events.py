import discord
from discord.ext import commands, tasks
from datetime import datetime as dt, timedelta, timezone, time
import os
from collections import defaultdict

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_deleted_message = {}
        self.status_reports_enabled = True
        self.clean_hours = [time(hour=h, minute=0, second=0) for h in range(24)]
        self.bot.start_time = None
        
    async def cog_load(self):
        self.periodic_status_check.start()
    
    async def send_status_embed(self):
        status_channel_id = int(os.getenv("STATUS_CHANNEL_ID", "1508549867948085298"))
        channel = self.bot.get_channel(status_channel_id)
        if channel:
            embeds_cog = self.bot.get_cog('Embeds')
            latency = round(self.bot.latency * 1000) if self.bot.latency != float('inf') else -1
            utc_plus_8 = timezone(timedelta(hours=8))
            current_time = dt.now(utc_plus_8).strftime('%Y-%m-%d %H:%M:%S')
            fields = [
                {"name": "Status", "value": "Online / Running Smoothly", "inline": False},
                {"name": "Gateway Latency", "value": f"{latency}ms", "inline": True},
                {"name": "Time (UTC+8)", "value": current_time, "inline": True}
            ]
            embed = embeds_cog.create_embed(title="Status Check", fields=fields)
            await channel.send(embed=embed)
    
    @tasks.loop(time=clean_hours)
    async def periodic_status_check(self):
        await self.bot.wait_until_ready()
        if not self.status_reports_enabled:
            return
        await self.send_status_embed()
    
    @commands.Cog.listener()
    async def on_ready(self):
        import time
        self.bot.start_time = time.time()
        print(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")
        await self.bot.change_presence(status=discord.Status.online)
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.id in self.bot.owner_ids or message.author.bot:
            return
        if message.content or message.attachments:
            attachment_url = message.attachments[0].url if message.attachments else None
            content = message.content if message.content else "[No text, attachment only]"
            self.last_deleted_message[message.channel.id] = {
                "content": content,
                "author": message.author,
                "time": message.created_at,
                "attachment": attachment_url
            }
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        print(f"Athena joined: {guild.name} (ID: {guild.id}) | Members: {guild.member_count}")
        status_channel_id = int(os.getenv("STATUS_CHANNEL_ID", "1508549867948085298"))
        channel = self.bot.get_channel(status_channel_id)
        if channel:
            embeds_cog = self.bot.get_cog('Embeds')
            embed = embeds_cog.create_embed(
                title="Bot Connection: Joined Guild",
                description=f"**Server Name:** {guild.name}\n**Guild ID:** `{guild.id}`\n**Members:** {guild.member_count}",
                color=discord.Color.green(), timestamp=True
            )
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        print(f"Athena left: {guild.name} (ID: {guild.id})")
        status_channel_id = int(os.getenv("STATUS_CHANNEL_ID", "1508549867948085298"))
        channel = self.bot.get_channel(status_channel_id)
        if channel:
            embeds_cog = self.bot.get_cog('Embeds')
            embed = embeds_cog.create_embed(
                title="Bot Connection: Left Guild",
                description=f"**Server Name:** {guild.name}\n**Guild ID:** `{guild.id}`",
                color=discord.Color.red(), timestamp=True
            )
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

async def setup(bot):
    await bot.add_cog(Events(bot))
