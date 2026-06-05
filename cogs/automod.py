import discord
from discord.ext import commands
from datetime import timedelta
from collections import defaultdict
import time as _time

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ratelimit_tracker = defaultdict(list)
    
    async def get_mod_cog(self):
        return self.bot.get_cog('Moderation')
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or message.author.id in self.bot.owner_ids:
            await self.bot.process_commands(message)
            return
        
        if message.author.guild_permissions.manage_messages:
            await self.bot.process_commands(message)
            return
        
        mod_cog = await self.get_mod_cog()
        if not mod_cog:
            await self.bot.process_commands(message)
            return
        
        try:
            # Barred phrases check
            rows = await mod_cog.db_execute("SELECT phrase FROM barred_phrases WHERE guild_id = ?", (message.guild.id,))
            if rows:
                message_content_lower = message.content.lower()
                for (phrase,) in rows:
                    if phrase.lower() in message_content_lower:
                        await self.handle_automod_violation(message, mod_cog, "barred phrase", phrase)
                        return
            
            # Barred characters check
            char_rows = await mod_cog.db_execute("SELECT char FROM barred_chars WHERE guild_id = ?", (message.guild.id,))
            if char_rows:
                for (bc,) in char_rows:
                    if bc in message.content:
                        await self.handle_automod_violation(message, mod_cog, "barred character", bc)
                        return
            
            # Spam checks
            spam = await mod_cog.db_fetchone("SELECT max_lines, max_chars, rl_max_messages, rl_window_seconds FROM spam_settings WHERE guild_id = ?", (message.guild.id,))
            if spam and spam[0]:
                exempt = await mod_cog.db_fetchone("SELECT 1 FROM spam_exempt_channels WHERE guild_id = ? AND channel_id = ?", (message.guild.id, message.channel.id))
                if not exempt or not exempt[0]:
                    content = message.content
                    is_spam = False
                    if spam[0] and (content.count('\n') + 1) > spam[0]:
                        is_spam = True
                    if spam[1] and len(content) > spam[1]:
                        is_spam = True
                    
                    if is_spam:
                        await self.handle_automod_violation(message, mod_cog, "spam", f"lines: {content.count(chr(10))+1}, chars: {len(content)}")
                        return
                    
                    # Rate limit check
                    if spam[2] and spam[3]:
                        key = (message.guild.id, message.channel.id, message.author.id)
                        now = _time.monotonic()
                        self.ratelimit_tracker[key] = [t for t in self.ratelimit_tracker[key] if now - t < spam[3]]
                        self.ratelimit_tracker[key].append(now)
                        if len(self.ratelimit_tracker[key]) > spam[2]:
                            self.ratelimit_tracker[key].clear()
                            await self.handle_automod_violation(message, mod_cog, "rate limit", f"{spam[2]} msgs/{spam[3]}s")
                            return
        except Exception as e:
            print(f"[AUTOMOD ERROR] {e}")
        
        await self.bot.process_commands(message)
    
    async def handle_automod_violation(self, message, mod_cog, violation_type, violation_detail):
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        
        row = await mod_cog.db_fetchone("SELECT count FROM warnings WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id))
        count = (row[0] + 1) if row and row[0] else 1
        
        if row and row[0]:
            await mod_cog.db_execute("UPDATE warnings SET count = ? WHERE guild_id = ? AND user_id = ?", (count, message.guild.id, message.author.id))
        else:
            await mod_cog.db_execute("INSERT INTO warnings (guild_id, user_id, count) VALUES (?, ?, ?)", (message.guild.id, message.author.id, count))
        
        await message.channel.send(f"{message.author.mention}, your message was removed due to {violation_type}. (Strike Count: {count})", delete_after=10)
        await mod_cog.log_moderation_action(
            message.guild, f"Automod: {violation_type.title()}", message.author, self.bot.user,
            f"Triggered {violation_type}: {violation_detail}",
            [{"name": "Cumulative Strikes", "value": str(count), "inline": True}]
        )
        
        if count >= 3:
            try:
                await message.author.timeout(timedelta(hours=1), reason="Automod: 3 accumulated strikes.")
                await message.channel.send(f"{message.author.mention} has been automatically muted for 1 hour.")
                await mod_cog.log_moderation_action(message.guild, "Auto-Mute Escalation", message.author, self.bot.user, "Target reached 3 active warnings.")
            except discord.Forbidden:
                pass
    
    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def warnspam(self, ctx):
        await ctx.send(
            f"Usage:\n"
            f"`,warnspam set lines <n>` - Warn if message exceeds n lines\n"
            f"`,warnspam set chars <n>` - Warn if message exceeds n characters\n"
            f"`,warnspam ratelimit <n> <secs>` - Warn if user sends n+ msgs in a window\n"
            f"`,warnspam disable <#channel>` - Exempt a channel\n"
            f"`,warnspam enable <#channel>` - Re-enable in a channel\n"
            f"`,warnspam status` - Show current settings\n"
            f"`,warnspam reset` - Clear all spam settings"
        )
    
    @warnspam.command(name="set")
    @commands.has_permissions(manage_messages=True)
    async def warnspam_set(self, ctx, threshold_type: str, value: int):
        mod_cog = await self.get_mod_cog()
        threshold_type = threshold_type.lower()
        if threshold_type not in ("lines", "chars"):
            return await ctx.send("Type must be `lines` or `chars`.")
        
        existing = await mod_cog.db_fetchone("SELECT 1 FROM spam_settings WHERE guild_id = ?", (ctx.guild.id,))
        if threshold_type == "lines":
            if existing and existing[0]:
                await mod_cog.db_execute("UPDATE spam_settings SET max_lines = ? WHERE guild_id = ?", (value, ctx.guild.id))
            else:
                await mod_cog.db_execute("INSERT INTO spam_settings (guild_id, max_lines, max_chars, rl_max_messages, rl_window_seconds) VALUES (?, ?, NULL, NULL, NULL)", (ctx.guild.id, value))
            await ctx.send(f"Spam threshold set: messages exceeding **{value} line(s)** will trigger a warning.")
        else:
            if existing and existing[0]:
                await mod_cog.db_execute("UPDATE spam_settings SET max_chars = ? WHERE guild_id = ?", (value, ctx.guild.id))
            else:
                await mod_cog.db_execute("INSERT INTO spam_settings (guild_id, max_lines, max_chars, rl_max_messages, rl_window_seconds) VALUES (?, NULL, ?, NULL, NULL)", (ctx.guild.id, value))
            await ctx.send(f"Spam threshold set: messages exceeding **{value} character(s)** will trigger a warning.")
    
    @warnspam.command(name="ratelimit")
    @commands.has_permissions(manage_messages=True)
    async def warnspam_ratelimit(self, ctx, max_messages: int, window_seconds: int):
        mod_cog = await self.get_mod_cog()
        existing = await mod_cog.db_fetchone("SELECT 1 FROM spam_settings WHERE guild_id = ?", (ctx.guild.id,))
        if existing and existing[0]:
            await mod_cog.db_execute("UPDATE spam_settings SET rl_max_messages = ?, rl_window_seconds = ? WHERE guild_id = ?", (max_messages, window_seconds, ctx.guild.id))
        else:
            await mod_cog.db_execute("INSERT INTO spam_settings (guild_id, max_lines, max_chars, rl_max_messages, rl_window_seconds) VALUES (?, NULL, NULL, ?, ?)", (ctx.guild.id, max_messages, window_seconds))
        await ctx.send(f"Rate limit set: users sending more than **{max_messages} message(s)** within **{window_seconds}s** will be warned.")
    
    @warnspam.command(name="disable")
    @commands.has_permissions(manage_messages=True)
    async def warnspam_disable(self, ctx, channel: discord.TextChannel):
        mod_cog = await self.get_mod_cog()
        existing = await mod_cog.db_fetchone("SELECT 1 FROM spam_exempt_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
        if existing and existing[0]:
            return await ctx.send(f"{channel.mention} is already exempt.")
        await mod_cog.db_execute("INSERT INTO spam_exempt_channels (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel.id))
        await ctx.send(f"Spam warnings disabled in {channel.mention}.")
    
    @warnspam.command(name="enable")
    @commands.has_permissions(manage_messages=True)
    async def warnspam_enable(self, ctx, channel: discord.TextChannel):
        mod_cog = await self.get_mod_cog()
        existing = await mod_cog.db_fetchone("SELECT 1 FROM spam_exempt_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
        if not existing or not existing[0]:
            return await ctx.send(f"{channel.mention} is not currently exempt.")
        await mod_cog.db_execute("DELETE FROM spam_exempt_channels WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, channel.id))
        await ctx.send(f"Spam warnings re-enabled in {channel.mention}.")
    
    @warnspam.command(name="status")
    @commands.has_permissions(manage_messages=True)
    async def warnspam_status(self, ctx):
        mod_cog = await self.get_mod_cog()
        embeds_cog = self.bot.get_cog('Embeds')
        settings = await mod_cog.db_fetchone("SELECT max_lines, max_chars, rl_max_messages, rl_window_seconds FROM spam_settings WHERE guild_id = ?", (ctx.guild.id,))
        exempt_rows = await mod_cog.db_execute("SELECT channel_id FROM spam_exempt_channels WHERE guild_id = ?", (ctx.guild.id,))
        
        lines_val = str(settings[0]) if settings and settings[0] else "Not set"
        chars_val = str(settings[1]) if settings and settings[1] else "Not set"
        rl_val = f"{settings[2]} msgs / {settings[3]}s" if settings and settings[2] and settings[3] else "Not set"
        exempt_list = ", ".join(f"<#{r[0]}>" for r in exempt_rows) if exempt_rows else "None"
        
        fields = [
            {"name": "Max Lines per Message", "value": lines_val, "inline": True},
            {"name": "Max Characters per Message", "value": chars_val, "inline": True},
            {"name": "Rate Limit", "value": rl_val, "inline": True},
            {"name": "Exempt Channels", "value": exempt_list, "inline": False},
        ]
        embed = embeds_cog.create_embed(title="Spam Warning Settings", fields=fields, color=discord.Color.orange())
        await ctx.send(embed=embed)
    
    @warnspam.command(name="reset")
    @commands.has_permissions(manage_messages=True)
    async def warnspam_reset(self, ctx):
        mod_cog = await self.get_mod_cog()
        await mod_cog.db_execute("DELETE FROM spam_settings WHERE guild_id = ?", (ctx.guild.id,))
        await mod_cog.db_execute("DELETE FROM spam_exempt_channels WHERE guild_id = ?", (ctx.guild.id,))
        await ctx.send("Spam warning settings and all exempt channels have been cleared.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def barword(self, ctx, *, phrase: str):
        mod_cog = await self.get_mod_cog()
        phrase = phrase.strip().lower()
        existing = await mod_cog.db_fetchone("SELECT phrase FROM barred_phrases WHERE guild_id = ? AND phrase = ?", (ctx.guild.id, phrase))
        if existing and existing[0]:
            return await ctx.send(f"The phrase `{phrase}` is already blacklisted.")
        await mod_cog.db_execute("INSERT INTO barred_phrases (guild_id, phrase) VALUES (?, ?)", (ctx.guild.id, phrase))
        await ctx.send(f"Added `{phrase}` to the barred message list.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def unbarword(self, ctx, *, phrase: str):
        mod_cog = await self.get_mod_cog()
        phrase = phrase.strip().lower()
        existing = await mod_cog.db_fetchone("SELECT phrase FROM barred_phrases WHERE guild_id = ? AND phrase = ?", (ctx.guild.id, phrase))
        if not existing or not existing[0]:
            return await ctx.send(f"The phrase `{phrase}` was not found.")
        await mod_cog.db_execute("DELETE FROM barred_phrases WHERE guild_id = ? AND phrase = ?", (ctx.guild.id, phrase))
        await ctx.send(f"Removed `{phrase}` from the barred message list.")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def barredwords(self, ctx):
        mod_cog = await self.get_mod_cog()
        embeds_cog = self.bot.get_cog('Embeds')
        rows = await mod_cog.db_execute("SELECT phrase FROM barred_phrases WHERE guild_id = ?", (ctx.guild.id,))
        if not rows:
            return await ctx.send("No barred phrases configured.")
        phrases = [f"`{row[0]}`" for row in rows]
        embed = embeds_cog.create_embed(title="Active Blacklisted Phrases", description=", ".join(phrases), 
                                       color=discord.Color.orange(), footer_text=f"Total: {len(rows)}")
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def barchar(self, ctx, *, char: str):
        mod_cog = await self.get_mod_cog()
        char = char.strip()
        existing = await mod_cog.db_fetchone("SELECT 1 FROM barred_chars WHERE guild_id = ? AND char = ?", (ctx.guild.id, char))
        if existing and existing[0]:
            return await ctx.send("That character is already barred.")
        await mod_cog.db_execute("INSERT INTO barred_chars (guild_id, char) VALUES (?, ?)", (ctx.guild.id, char))
        await ctx.send(f"Added to barred characters: `{char}`")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def unbarchar(self, ctx, *, char: str):
        mod_cog = await self.get_mod_cog()
        char = char.strip()
        existing = await mod_cog.db_fetchone("SELECT 1 FROM barred_chars WHERE guild_id = ? AND char = ?", (ctx.guild.id, char))
        if not existing or not existing[0]:
            return await ctx.send("That character is not barred.")
        await mod_cog.db_execute("DELETE FROM barred_chars WHERE guild_id = ? AND char = ?", (ctx.guild.id, char))
        await ctx.send(f"Removed from barred characters: `{char}`")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def barchars(self, ctx):
        mod_cog = await self.get_mod_cog()
        embeds_cog = self.bot.get_cog('Embeds')
        rows = await mod_cog.db_execute("SELECT char FROM barred_chars WHERE guild_id = ?", (ctx.guild.id,))
        if not rows:
            return await ctx.send("No barred characters configured.")
        chars_list = ", ".join(f"`{r[0]}`" for r in rows)
        embed = embeds_cog.create_embed(title="Barred Characters & Emojis", description=chars_list, color=discord.Color.red())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Automod(bot))
