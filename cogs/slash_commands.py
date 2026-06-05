import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from typing import Optional

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def get_mod_cog(self):
        return self.bot.get_cog('Moderation')
    
    async def get_events_cog(self):
        return self.bot.get_cog('Events')
    
    async def get_embeds_cog(self):
        return self.bot.get_cog('Embeds')
    
    # Moderation Slash Commands
    @app_commands.command(name="warn", description="Warn a member and add a strike.")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.default_permissions(manage_messages=True)
    async def slash_warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
        mod_cog = await self.get_mod_cog()
        row = await mod_cog.db_fetchone("SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, member.id))
        count = (row[0] + 1) if row and row[0] else 1
        
        if row and row[0]:
            await mod_cog.db_execute("UPDATE warnings SET count = ? WHERE guild_id = ? AND user_id = ?", (count, interaction.guild.id, member.id))
        else:
            await mod_cog.db_execute("INSERT INTO warnings (guild_id, user_id, count) VALUES (?, ?, ?)", (interaction.guild.id, member.id, count))
        
        try:
            await member.send(f"You have been warned in **{interaction.guild.name}**. Reason: {reason} (Strike Count: {count})")
        except discord.Forbidden:
            pass
        
        await interaction.response.send_message(f"{member.mention} has been warned. Total strikes: **{count}**")
        await mod_cog.log_moderation_action(interaction.guild, "Strike Warning Dispatched", member, interaction.user, reason, 
                                          [{"name": "Cumulative Strikes", "value": str(count), "inline": True}])
        
        if count >= 3:
            try:
                await member.timeout(timedelta(hours=1), reason="3 accumulated strikes.")
                await interaction.followup.send(f"{member.mention} has been automatically muted for 1 hour.")
            except discord.Forbidden:
                pass
    
    @app_commands.command(name="warnings", description="Check how many warnings a member has.")
    @app_commands.describe(member="Member to check")
    @app_commands.default_permissions(manage_messages=True)
    async def slash_warnings(self, interaction: discord.Interaction, member: discord.Member):
        mod_cog = await self.get_mod_cog()
        row = await mod_cog.db_fetchone("SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, member.id))
        count = row[0] if row and row[0] else 0
        await interaction.response.send_message(f"{member.mention} has **{count}** warning strike(s).")
    
    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @app_commands.default_permissions(kick_members=True)
    async def slash_kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
        mod_cog = await self.get_mod_cog()
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f"{member} kicked. Reason: {reason}")
            await mod_cog.log_moderation_action(interaction.guild, "Member Kicked", member, interaction.user, reason)
        except discord.Forbidden:
            await interaction.response.send_message("Error: Insufficient permissions.", ephemeral=True)
    
    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.describe(user="User to ban", reason="Reason for the ban")
    @app_commands.default_permissions(ban_members=True)
    async def slash_ban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason given"):
        mod_cog = await self.get_mod_cog()
        try:
            await interaction.guild.ban(user, reason=reason)
            await interaction.response.send_message(f"{user} banned. Reason: {reason}")
            await mod_cog.log_moderation_action(interaction.guild, "Member Banned", user, interaction.user, reason)
        except discord.Forbidden:
            await interaction.response.send_message("Error: Insufficient permissions.", ephemeral=True)
    
    @app_commands.command(name="mute", description="Timeout a member.")
    @app_commands.describe(member="Member to mute", minutes="Duration in minutes", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def slash_mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason given"):
        mod_cog = await self.get_mod_cog()
        if minutes > 40320 or minutes <= 0:
            return await interaction.response.send_message("Invalid duration.", ephemeral=True)
        try:
            await member.timeout(timedelta(minutes=minutes), reason=reason)
            await interaction.response.send_message(f"{member} muted for {minutes} minute(s).")
            await mod_cog.log_moderation_action(interaction.guild, "Timeout Applied", member, interaction.user, reason,
                                              [{"name": "Duration", "value": f"{minutes} minute(s)", "inline": True}])
        except discord.Forbidden:
            await interaction.response.send_message("Error: Insufficient permissions.", ephemeral=True)
    
    @app_commands.command(name="unmute", description="Remove timeout from a member.")
    @app_commands.describe(member="Member to unmute")
    @app_commands.default_permissions(moderate_members=True)
    async def slash_unmute(self, interaction: discord.Interaction, member: discord.Member):
        mod_cog = await self.get_mod_cog()
        try:
            await member.timeout(None)
            await interaction.response.send_message(f"{member} unmuted.")
            await mod_cog.log_moderation_action(interaction.guild, "Timeout Revoked", member, interaction.user, "Manual override")
        except discord.Forbidden:
            await interaction.response.send_message("Error: Insufficient permissions.", ephemeral=True)
    
    @app_commands.command(name="clear", description="Purge recent messages.")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.default_permissions(manage_messages=True)
    async def slash_clear(self, interaction: discord.Interaction, amount: int = 10):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message("Amount must be between 1 and 100.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Cleared {len(deleted)} message(s).", ephemeral=True)
    
    @app_commands.command(name="lock", description="Lock the channel.")
    @app_commands.default_permissions(manage_channels=True)
    async def slash_lock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message("Channel locked.")
    
    @app_commands.command(name="unlock", description="Unlock the channel.")
    @app_commands.default_permissions(manage_channels=True)
    async def slash_unlock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.response.send_message("Channel unlocked.")
    
    @app_commands.command(name="slowmode", description="Set slowmode delay.")
    @app_commands.describe(seconds="Delay in seconds (0-21600)")
    @app_commands.default_permissions(manage_channels=True)
    async def slash_slowmode(self, interaction: discord.Interaction, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message("Slowmode must be 0-21600 seconds.", ephemeral=True)
        await interaction.channel.edit(slowmode_delay=seconds)
        await interaction.response.send_message("Slowmode disabled." if seconds == 0 else f"Slowmode set to {seconds} seconds.")
    
    @app_commands.command(name="snipe", description="Show the last deleted message.")
    @app_commands.default_permissions(manage_messages=True)
    async def slash_snipe(self, interaction: discord.Interaction):
        events_cog = await self.get_events_cog()
        embeds_cog = await self.get_embeds_cog()
        data = events_cog.last_deleted_message.get(interaction.channel.id)
        if not data:
            return await interaction.response.send_message("No recent deleted messages.", ephemeral=True)
        embed = embeds_cog.create_embed(title="Sniped Message", description=data["content"], color=discord.Color.red(),
                                      author_name=str(data["author"]), author_icon=data["author"].display_avatar.url,
                                      image=data.get("attachment"))
        embed.timestamp = data["time"]
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="Show server information.")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        embeds_cog = await self.get_embeds_cog()
        g = interaction.guild
        fields = [
            {"name": "Owner", "value": str(g.owner), "inline": True},
            {"name": "Members", "value": str(g.member_count), "inline": True},
            {"name": "Channels", "value": str(len(g.channels)), "inline": True},
            {"name": "Roles", "value": str(len(g.roles)), "inline": True},
            {"name": "Created", "value": g.created_at.strftime("%Y-%m-%d"), "inline": True},
        ]
        embed = embeds_cog.create_embed(title=g.name, fields=fields, thumbnail=g.icon.url if g.icon else None)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="Show user information.")
    @app_commands.describe(member="Member to inspect")
    async def slash_userinfo(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        embeds_cog = await self.get_embeds_cog()
        member = member or interaction.user
        roles = [r.mention for r in member.roles[1:]]
        roles_str = " ".join(roles) if roles else "None"
        fields = [
            {"name": "ID", "value": str(member.id), "inline": True},
            {"name": "Nickname", "value": member.nick or "None", "inline": True},
            {"name": "Joined", "value": member.joined_at.strftime("%Y-%m-%d"), "inline": True},
            {"name": "Created", "value": member.created_at.strftime("%Y-%m-%d"), "inline": True},
            {"name": f"Roles ({len(roles)})", "value": roles_str, "inline": False},
        ]
        embed = embeds_cog.create_embed(title=str(member), color=member.color, fields=fields, thumbnail=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))
