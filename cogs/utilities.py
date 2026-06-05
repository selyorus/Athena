import discord
from discord.ext import commands

class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def help(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        embed = embeds_cog.get_help_embed(ctx)
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):
        events_cog = self.bot.get_cog('Events')
        embeds_cog = self.bot.get_cog('Embeds')
        channel_id = ctx.channel.id
        if channel_id in events_cog.last_deleted_message:
            data = events_cog.last_deleted_message[channel_id]
            embed = embeds_cog.create_embed(
                title="Sniped Message",
                description=data["content"],
                color=discord.Color.red(),
                author_name=str(data["author"]),
                author_icon=data["author"].display_avatar.url,
                image=data.get("attachment")
            )
            embed.timestamp = data["time"]
            await ctx.send(embed=embed)
        else:
            await ctx.send("No recent deleted messages found.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def embed(self, ctx, *, content: str):
        embeds_cog = self.bot.get_cog('Embeds')
        parts = content.split('|', 1)
        if len(parts) == 2:
            title, desc = parts[0].strip(), parts[1].strip()
        else:
            title, desc = "Notification", parts[0].strip()
        custom_embed = embeds_cog.create_embed(title=title, description=desc, color=discord.Color.green(), timestamp=True)
        await ctx.send(embed=custom_embed)
        if ctx.guild:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
    
    @commands.command()
    async def say(self, ctx, channel_id: int, *, message: str):
        if ctx.guild:
            if not ctx.author.guild_permissions.manage_messages and ctx.author.id not in self.bot.owner_ids:
                return await ctx.send("You don't have permission.")
        elif ctx.author.id not in self.bot.owner_ids:
            return await ctx.send("Only the bot developer can use this command in DMs.")
        
        target_channel = self.bot.get_channel(channel_id)
        if not target_channel:
            return await ctx.send("Could not find that channel.")
        
        try:
            await target_channel.send(message)
            if ctx.guild:
                try:
                    await ctx.message.delete()
                except discord.Forbidden:
                    pass
            else:
                await ctx.send(f"Message sent to {target_channel.mention} in **{target_channel.guild.name}**.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to send messages there.")
    
    @commands.command()
    async def serverinfo(self, ctx):
        embeds_cog = self.bot.get_cog('Embeds')
        g = ctx.guild
        fields = [
            {"name": "Owner", "value": str(g.owner), "inline": True},
            {"name": "Members", "value": str(g.member_count), "inline": True},
            {"name": "Channels", "value": str(len(g.channels)), "inline": True},
            {"name": "Roles", "value": str(len(g.roles)), "inline": True},
            {"name": "Created", "value": g.created_at.strftime("%Y-%m-%d"), "inline": True}
        ]
        thumbnail = g.icon.url if g.icon else None
        embed = embeds_cog.create_embed(title=g.name, fields=fields, thumbnail=thumbnail)
        await ctx.send(embed=embed)
    
    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        embeds_cog = self.bot.get_cog('Embeds')
        member = member or ctx.author
        roles = [r.mention for r in member.roles[1:]]
        roles_str = " ".join(roles) if roles else "None"
        fields = [
            {"name": "ID", "value": str(member.id), "inline": True},
            {"name": "Nickname", "value": member.nick or "None", "inline": True},
            {"name": "Joined Server", "value": member.joined_at.strftime("%Y-%m-%d"), "inline": True},
            {"name": "Account Created", "value": member.created_at.strftime("%Y-%m-%d"), "inline": True},
            {"name": f"Roles ({len(roles)})", "value": roles_str, "inline": False}
        ]
        embed = embeds_cog.create_embed(title=str(member), color=member.color, fields=fields, thumbnail=member.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utilities(bot))
