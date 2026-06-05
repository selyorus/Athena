import discord
from discord.ext import commands
from datetime import timedelta
import sqlite3
import asyncio
from pathlib import Path

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = Path(__file__).parent.parent / "athena_moderation.db"
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                guild_id INTEGER,
                user_id INTEGER,
                count INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS barred_phrases (
                guild_id INTEGER,
                phrase TEXT,
                PRIMARY KEY (guild_id, phrase)
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                note TEXT,
                created_at TEXT
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_settings (
                guild_id INTEGER PRIMARY KEY,
                max_lines INTEGER,
                max_chars INTEGER,
                rl_max_messages INTEGER,
                rl_window_seconds INTEGER
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS spam_exempt_channels (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS barred_chars (
                guild_id INTEGER,
                char TEXT,
                PRIMARY KEY (guild_id, char)
            )
            """)
            conn.commit()
    
    def _sync_execute(self, query, params):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.fetchall()
    
    def _sync_fetchone(self, query, params):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
    
    async def db_execute(self, query: str, params: tuple = ()):
        return await asyncio.to_thread(self._sync_execute, query, params)
    
    async def db_fetchone(self, query: str, params: tuple = ()):
        return await asyncio.to_thread(self._sync_fetchone, query, params)
    
    async def log_moderation_action(self, guild, action_title, target, moderator, reason, extra_fields=None):
        row = await self.db_fetchone("SELECT channel_id FROM log_channels WHERE guild_id = ?", (guild.id,))
        if not row or not row[0]:
            return
        channel = guild.get_channel(row[0])
        if not channel:
            return
        
        embeds_cog = self.bot.get_cog('Embeds')
        fields = [
            {"name": "Target User", "value": f"{target} (`{target.id}`)", "inline": True},
            {"name": "Responsible Mod", "value": f"{moderator.mention}", "inline": True},
            {"name": "Reason", "value": reason, "inline": False}
        ]
        if extra_fields:
            fields.extend(extra_fields)
            
        log_embed = embeds_cog.create_embed(
            title=f"Log Incident: {action_title}",
            color=discord.Color.red(), fields=fields, timestamp=True
        )
        try:
            await channel.send(embed=log_embed)
        except discord.Forbidden:
            pass
    
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason given"):
        try:
            await member.kick(reason=reason)
            await ctx.send(f"{member} kicked. Reason: {reason}")
            await self.log_moderation_action(ctx.guild, "Member Kicked", member, ctx.author, reason)
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to kick this user.")
    
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, target: discord.User, *, reason="No reason given"):
        try:
            await ctx.guild.ban(target, reason=reason)
            await ctx.send(f"{target} banned. Reason: {reason}")
            await self.log_moderation_action(ctx.guild, "Member Banned", target, ctx.author, reason)
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to ban this user.")
    
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx, member: discord.Member, *, reason="Softban (Messages wiped)"):
        try:
            await ctx.guild.ban(member, delete_message_seconds=604800, reason=reason)
            await ctx.guild.unban(member, reason="Softban restoration loop context")
            await ctx.send(f"Softbanned {member.mention}. Recent histories have been purged.")
            await self.log_moderation_action(ctx.guild, "Softban (History Wiped)", member, ctx.author, reason)
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to execute this operation.")
    
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, username: str):
        try:
            async for entry in ctx.guild.bans():
                user = entry.user
                if user.name.lower() == username.lower() or str(user).lower() == username.lower():
                    await ctx.guild.unban(user)
                    await ctx.send(f"{user} unbanned.")
                    await self.log_moderation_action(ctx.guild, "Member Unbanned", user, ctx.author, "Manual command trigger")
                    return
            await ctx.send(f"User {username} not found in the ban list.")
        except discord.Forbidden:
            await ctx.send("Error: Bot lacks permission to access or adjust the server ban collection data.")
    
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, minutes: int = 10, *, reason="No reason given"):
        if minutes > 40320:
            await ctx.send("Cannot mute for more than 28 days (40320 minutes).")
            return
        if minutes <= 0:
            await ctx.send("Duration must be at least 1 minute.")
            return
        try:
            duration = timedelta(minutes=minutes)
            await member.timeout(duration, reason=reason)
            await ctx.send(f"{member} muted for {minutes} minute(s). Reason: {reason}")
            await self.log_moderation_action(ctx.guild, "Timeout Applied", member, ctx.author, reason, 
                                           [{"name": "Duration", "value": f"{minutes} minute(s)", "inline": True}])
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to mute this user.")
    
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        try:
            await member.timeout(None)
            await ctx.send(f"{member} unmuted.")
            await self.log_moderation_action(ctx.guild, "Timeout Revoked", member, ctx.author, "Manual override execution")
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to remove mute properties.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10):
        if amount < 1 or amount > 100:
            await ctx.send("Amount must be between 1 and 100.")
            return
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"Cleared {len(deleted) - 1} messages.", delete_after=5)
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason="No reason given"):
        row = await self.db_fetchone("SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
        count = (row[0] + 1) if row and row[0] else 1
        
        if row and row[0]:
            await self.db_execute("UPDATE warnings SET count = ? WHERE guild_id = ? AND user_id = ?", (count, ctx.guild.id, member.id))
        else:
            await self.db_execute("INSERT INTO warnings (guild_id, user_id, count) VALUES (?, ?, ?)", (ctx.guild.id, member.id, count))
        
        try:
            await member.send(f"You have been warned in **{ctx.guild.name}**. Reason: {reason} (Strike Count: {count})")
        except discord.Forbidden:
            pass
        
        await ctx.send(f"{member.mention} has been warned. Total strikes recorded: **{count}**")
        await self.log_moderation_action(ctx.guild, "Strike Warning Dispatched", member, ctx.author, reason, 
                                       [{"name": "Cumulative Strikes", "value": str(count), "inline": True}])
        
        if count >= 3:
            try:
                await member.timeout(timedelta(hours=1), reason="Automatic system response: 3 active accumulated strikes.")
                await ctx.send(f"{member.mention} has been automatically muted for 1 hour for reaching 3 warning strikes.")
                await self.log_moderation_action(ctx.guild, "Auto-Mute Escalation", member, self.bot.user, "Target reached 3 active warnings.")
            except discord.Forbidden:
                await ctx.send("Auto-mute failed: bot role hierarchy prevents timing out this user.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        row = await self.db_fetchone("SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
        count = row[0] if row and row[0] else 0
        await ctx.send(f"{member.mention} has **{count}** warning strike(s) on record.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        await self.db_execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
        await ctx.send(f"Cleared all recorded warnings for {member.mention}.")
        await self.log_moderation_action(ctx.guild, "Warning Strikes Cleared", member, ctx.author, "Manual warning log reset executed.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purgeuser(self, ctx, member: discord.Member, amount: int = 100):
        def check(m):
            return m.author == member
        deleted = await ctx.channel.purge(limit=amount, check=check)
        await ctx.send(f"Deleted {len(deleted)} messages from {member.mention}.", delete_after=5)
    
    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            await ctx.send("Slowmode limit is 0 to 21600 seconds.")
            return
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send("Slowmode disabled." if seconds == 0 else f"Slowmode set to {seconds} second(s).")
    
    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send("Channel locked. Members can no longer send messages.")
    
    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send("Channel unlocked.")
    
    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx, member: discord.Member, role: discord.Role):
        try:
            if role in member.roles:
                await member.remove_roles(role)
                await ctx.send(f"Removed {role.name} from {member.display_name}.")
            else:
                await member.add_roles(role)
                await ctx.send(f"Assigned {role.name} to {member.display_name}.")
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to adjust this role type.")
    
    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, name: str):
        try:
            await member.edit(nick=name)
            await ctx.send(f"Nickname for {member.mention} set to **{name}**.")
        except discord.Forbidden:
            await ctx.send("Error: Bot has insufficient permission hierarchy levels to modify this user's nickname.")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        await self.db_execute("INSERT OR REPLACE INTO log_channels (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel.id))
        await ctx.send(f"Log channel set. Moderation actions will be recorded in {channel.mention}.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
