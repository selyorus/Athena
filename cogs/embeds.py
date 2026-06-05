import discord
from discord.ext import commands
from datetime import datetime as dt, timedelta, timezone

class Embeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.PREFIX = ","
    
    def create_embed(self, title: str, description: str = None, color: discord.Color = discord.Color.blue(), 
                     fields: list = None, thumbnail: str = None, image: str = None, 
                     author_name: str = None, author_icon: str = None, 
                     footer_text: str = None, footer_icon: str = None, timestamp: bool = False):
        """Universal embed creator"""
        embed = discord.Embed(title=title, description=description, color=color)
        if timestamp:
            utc_plus_8 = timezone(timedelta(hours=8))
            embed.timestamp = dt.now(utc_plus_8)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if image:
            embed.set_image(url=image)
        if author_name:
            if author_icon:
                embed.set_author(name=author_name, icon_url=author_icon)
            else:
                embed.set_author(name=author_name)
        if fields:
            for field in fields:
                embed.add_field(name=field.get("name", "Field"), value=field.get("value", "Value"), 
                              inline=field.get("inline", True))
        if footer_text:
            if footer_icon:
                embed.set_footer(text=footer_text, icon_url=footer_icon)
            else:
                embed.set_footer(text=footer_text)
        return embed
    
    def get_help_embed(self, ctx):
        """Generate the help command embed"""
        fields = [
            {
                "name": "Moderation",
                "value": (
                    f"`{self.PREFIX}kick <member> [reason]` - Kick a member\n"
                    f"`{self.PREFIX}ban <user_id/member> [reason]` - Ban a user\n"
                    f"`{self.PREFIX}softban <member>` - Kick and wipe user's history\n"
                    f"`{self.PREFIX}unban <username>` - Unban a user\n"
                    f"`{self.PREFIX}mute <member> [mins] [reason]` - Timeout a member\n"
                    f"`{self.PREFIX}unmute <member>` - Remove timeout\n"
                    f"`{self.PREFIX}warn <member> [reason]` - Log warn & strike tracking\n"
                    f"`{self.PREFIX}warnings <member>` - Check total warnings\n"
                    f"`{self.PREFIX}clearwarnings <member>` - Erase strike history\n"
                    f"`{self.PREFIX}clear [amount]` - Purge messages\n"
                    f"`{self.PREFIX}purgeuser <member> [amount]` - Delete specific user's messages\n"
                    f"`{self.PREFIX}warnspam` - Configure spam auto-warn\n"
                ),
                "inline": False
            },
            {
                "name": "Utilities",
                "value": (
                    f"`{self.PREFIX}snipe` - View the last deleted message\n"
                    f"`{self.PREFIX}slowmode [seconds]` - Set channel slowmode\n"
                    f"`{self.PREFIX}lock` / `{self.PREFIX}unlock` - Lock/unlock channel\n"
                    f"`{self.PREFIX}role <member> <role>` - Add or remove role\n"
                    f"`{self.PREFIX}nick <member> <name>` - Change nickname\n"
                    f"`{self.PREFIX}serverinfo` - Display server stats\n"
                    f"`{self.PREFIX}userinfo [member]` - Display user details\n"
                    f"`{self.PREFIX}say <channel_id> <message>` - Speak through bot\n"
                    f"`{self.PREFIX}embed <title> | <desc>` - Generate embed\n"
                    f"`{self.PREFIX}setlogchannel <channel>` - Set logging channel\n"
                    f"`{self.PREFIX}barword <phrase>` - Add word filter\n"
                    f"`{self.PREFIX}unbarword <phrase>` - Remove word filter\n"
                    f"`{self.PREFIX}barredwords` - List filtered words\n"
                    f"`{self.PREFIX}barchar <char/emoji>` - Bar character/emoji\n"
                    f"`{self.PREFIX}unbarchar <char/emoji>` - Remove from barred\n"
                    f"`{self.PREFIX}barchars` - List barred characters\n"
                ),
                "inline": False
            }
        ]
        
        return self.create_embed(
            title="Athena's Commands",
            description=f"Use `{self.PREFIX}command` to execute. Arguments in `<>` are required, `[]` are optional.",
            fields=fields,
            footer_text=f"Requested by {ctx.author.display_name}",
            footer_icon=ctx.author.display_avatar.url
        )
    
    def get_dev_embed(self, ctx):
        """Generate the developer dashboard embed (,d)"""
        fields = [
            {
                "name": "Bot Controls",
                "value": (
                    f"`{self.PREFIX}giveadmin <member>` - Grant server admin role\n"
                    f"`{self.PREFIX}removeadmin <member>` - Revoke server admin role\n"
                    f"`{self.PREFIX}setstatus <type> <text>` - Change bot presence\n"
                    f"`{self.PREFIX}customstatus <text>` - Set a custom status bubble\n"
                    f"`{self.PREFIX}togglestatus` - Toggle hourly status reports\n"
                    f"`{self.PREFIX}checkstatus` - Force a manual status report\n"
                    f"`{self.PREFIX}sync` / `{self.PREFIX}sync guild` / `{self.PREFIX}sync clear` - Slash command sync\n"
                    f"`{self.PREFIX}areyouonline` - Quick ping check\n"
                    f"`{self.PREFIX}ping` - Gateway & REST latency\n"
                    f"`{self.PREFIX}uptime` - Time since last restart\n"
                    f"`{self.PREFIX}restart` - Gracefully restart the bot"
                ),
                "inline": False
            },
            {
                "name": "User Records",
                "value": (
                    f"`{self.PREFIX}bl` / `{self.PREFIX}blacklist <user_id>` - Block a user globally\n"
                    f"`{self.PREFIX}ubl` / `{self.PREFIX}unblacklist <user_id>` - Remove from blacklist\n"
                    f"`{self.PREFIX}bls` / `{self.PREFIX}blacklisted` - List all blacklisted users\n"
                    f"`{self.PREFIX}clearwarns_global <user_id>` - Clear all warnings globally\n"
                    f"`{self.PREFIX}lu` / `{self.PREFIX}lookup <user_id>` - Warnings, notes, blacklist summary\n"
                    f"`{self.PREFIX}n` / `{self.PREFIX}note <user_id> <text>` - Save a note about a user\n"
                    f"`{self.PREFIX}vn` / `{self.PREFIX}viewnotes <user_id>` - View all notes for a user\n"
                    f"`{self.PREFIX}dn` / `{self.PREFIX}delnote <note_id>` - Delete a note by ID"
                ),
                "inline": False
            },
            {
                "name": "Remote Dashboard (DM Suite - Private)",
                "value": (
                    f"`{self.PREFIX}dr` - Remote Dashboard reference\n"
                    f"`{self.PREFIX}ds` / `{self.PREFIX}devservers` - View all connected servers\n"
                    f"`{self.PREFIX}dc` / `{self.PREFIX}devchannels <guild_id>` - List all text channels\n"
                    f"`{self.PREFIX}di` / `{self.PREFIX}devinfo <guild_id>` - Server diagnostic\n"
                    f"`{self.PREFIX}de` / `{self.PREFIX}devembed <guild_id> <channel_id> Title | Desc` - Send remote embed\n"
                    f"`{self.PREFIX}dm` / `{self.PREFIX}devmute <guild_id> <user_id>` - Remote timeout\n"
                    f"`{self.PREFIX}dsa` / `{self.PREFIX}devsay <channel_id> <message>` - Remote broadcast\n"
                    f"`{self.PREFIX}dk` / `{self.PREFIX}devkick <guild_id> <user_id>` - Remote kick\n"
                    f"`{self.PREFIX}db` / `{self.PREFIX}devban <guild_id> <user_id>` - Remote ban\n"
                    f"`{self.PREFIX}dga` / `{self.PREFIX}devgiveadmin <guild_id> <user_id>` - Remote admin grant\n"
                    f"`{self.PREFIX}dra` / `{self.PREFIX}devremoveadmin <guild_id> <user_id>` - Remote admin revoke\n"
                    f"`{self.PREFIX}dl` / `{self.PREFIX}devleave <guild_id>` - Force Athena to leave\n"
                    f"`{self.PREFIX}dinv` / `{self.PREFIX}devinvites <guild_id>` - Generate temp invite\n"
                    f"`{self.PREFIX}dst` / `{self.PREFIX}devstats` - Full system diagnostic"
                ),
                "inline": False
            }
        ]
        
        return self.create_embed(
            title="Developer Dashboard",
            description="Private management tools for Athena.",
            color=discord.Color.purple(),
            fields=fields,
            footer_text=f"Session: {ctx.author.display_name}",
            footer_icon=ctx.author.display_avatar.url
        )
    
    def get_remote_dashboard_embed(self, ctx):
        """Generate the remote dashboard embed (,dr)"""
        fields = [
            {
                "name": "Reconnaissance",
                "value": (
                    f"`{self.PREFIX}ds` — List all connected servers and their IDs\n"
                    f"`{self.PREFIX}di <guild_id>` — Server diagnostic: name, members, owner\n"
                    f"`{self.PREFIX}dc <guild_id>` — List all text channels and their IDs\n"
                    f"`{self.PREFIX}dst` — Full system stats: RAM, CPU, ping, guild count"
                ),
                "inline": False
            },
            {
                "name": "Messaging",
                "value": (
                    f"`{self.PREFIX}dsa <channel_id> <message>` — Send a plain message to any channel\n"
                    f"`{self.PREFIX}de <guild_id> <channel_id> Title | Desc` — Send an embed to any channel\n"
                    f"`{self.PREFIX}dinv <guild_id>` — Generate a 5-min single-use invite (sent to your DMs)"
                ),
                "inline": False
            },
            {
                "name": "Moderation",
                "value": (
                    f"`{self.PREFIX}dm <guild_id> <user_id>` — Remote 1-hour timeout\n"
                    f"`{self.PREFIX}dk <guild_id> <user_id> [reason]` — Remote kick\n"
                    f"`{self.PREFIX}db <guild_id> <user_id> [reason]` — Remote ban\n"
                    f"`{self.PREFIX}dga <guild_id> <user_id>` — Grant Admin role remotely\n"
                    f"`{self.PREFIX}dra <guild_id> <user_id>` — Revoke Admin role remotely"
                ),
                "inline": False
            },
            {
                "name": "Bot Control",
                "value": f"`{self.PREFIX}dl <guild_id>` — Force Athena to leave a server",
                "inline": False
            }
        ]
        
        return self.create_embed(
            title="Remote Dashboard",
            description="All commands must be run in DMs with the bot.",
            color=discord.Color.dark_red(),
            fields=fields,
            footer_text=f"Session: {ctx.author.display_name}",
            footer_icon=ctx.author.display_avatar.url
        )

async def setup(bot):
    await bot.add_cog(Embeds(bot))
