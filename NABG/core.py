import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from datetime import datetime, timezone
import logging

log = logging.getLogger("red.nabg")

class NABG(commands.Cog):
    """New Accounts Be Gone - Automatically kicks accounts created today"""
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        
        # Default guild settings
        default_guild = {
            "enabled": False,
            "log_channel": None,
            "kick_message": "Your account was created too recently to join this server."
        }
        
        self.config.register_guild(**default_guild)
    
    @commands.group(name="nabg", invoke_without_command=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def nabg_group(self, ctx):
        """NABG - New Accounts Be Gone configuration"""
        if ctx.invoked_subcommand is None:
            enabled = await self.config.guild(ctx.guild).enabled()
            log_channel_id = await self.config.guild(ctx.guild).log_channel()
            log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None
            
            embed = discord.Embed(
                title="NABG - New Accounts Be Gone",
                description="Configuration for automatic new account detection",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Status", 
                value="✅ Enabled" if enabled else "❌ Disabled", 
                inline=True
            )
            embed.add_field(
                name="Log Channel", 
                value=log_channel.mention if log_channel else "Not set", 
                inline=True
            )
            embed.add_field(
                name="Function", 
                value="Kicks users whose accounts were created today", 
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @nabg_group.command(name="enable")
    @checks.admin_or_permissions(manage_guild=True)
    async def enable_nabg(self, ctx):
        """Enable NABG protection"""
        await self.config.guild(ctx.guild).enabled.set(True)
        embed = discord.Embed(
            title="NABG Enabled",
            description="✅ New account protection is now active. Users with accounts created today will be kicked.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        log.info(f"NABG enabled in guild {ctx.guild.name} ({ctx.guild.id})")
    
    @nabg_group.command(name="disable")
    @checks.admin_or_permissions(manage_guild=True)
    async def disable_nabg(self, ctx):
        """Disable NABG protection"""
        await self.config.guild(ctx.guild).enabled.set(False)
        embed = discord.Embed(
            title="NABG Disabled",
            description="❌ New account protection is now inactive.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        log.info(f"NABG disabled in guild {ctx.guild.name} ({ctx.guild.id})")
    
    @nabg_group.command(name="logchannel")
    @checks.admin_or_permissions(manage_guild=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for NABG logs"""
        if channel is None:
            await self.config.guild(ctx.guild).log_channel.set(None)
            await ctx.send("Log channel cleared.")
        else:
            await self.config.guild(ctx.guild).log_channel.set(channel.id)
            await ctx.send(f"Log channel set to {channel.mention}")
    
    @nabg_group.command(name="message")
    @checks.admin_or_permissions(manage_guild=True)
    async def set_kick_message(self, ctx, *, message: str):
        """Set the DM message sent to kicked users"""
        await self.config.guild(ctx.guild).kick_message.set(message)
        await ctx.send(f"Kick message updated to: {message}")
    
    @nabg_group.command(name="test")
    @checks.admin_or_permissions(manage_guild=True)
    async def test_account_age(self, ctx, user: discord.Member = None):
        """Test account age checking on a user (defaults to yourself)"""
        if user is None:
            user = ctx.author
        
        created_today = self._is_account_created_today(user)
        account_age = datetime.now(timezone.utc) - user.created_at
        
        embed = discord.Embed(
            title="Account Age Test",
            color=discord.Color.orange()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Account Created", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
        embed.add_field(name="Account Age", value=f"{account_age.days} days", inline=True)
        embed.add_field(name="Created Today?", value="Yes" if created_today else "No", inline=True)
        embed.add_field(name="Would be kicked?", value="Yes" if created_today else "No", inline=True)
        
        await ctx.send(embed=embed)
    
    def _is_account_created_today(self, user: discord.Member) -> bool:
        """Check if user account was created today"""
        now = datetime.now(timezone.utc)
        user_created = user.created_at
        
        # Check if both dates are the same day
        return (now.date() == user_created.date())
    
    async def _send_log(self, guild: discord.Guild, message: str):
        """Send a message to the configured log channel"""
        log_channel_id = await self.config.guild(guild).log_channel()
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                try:
                    embed = discord.Embed(
                        title="NABG - Account Kicked",
                        description=message,
                        color=discord.Color.orange(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    log.warning(f"Cannot send to log channel {log_channel_id} in guild {guild.id}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Event triggered when a new member joins the server"""
        guild = member.guild
        
        # Check if NABG is enabled for this guild
        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            return
        
        # Check if the bot has permission to kick members
        if not guild.me.guild_permissions.kick_members:
            log.warning(f"Bot lacks kick permissions in guild {guild.name} ({guild.id})")
            return
        
        # Check if account was created today
        if self._is_account_created_today(member):
            try:
                # Get kick message
                kick_message = await self.config.guild(guild).kick_message()
                
                # Try to send DM first
                try:
                    await member.send(kick_message)
                except discord.Forbidden:
                    log.info(f"Could not DM user {member} ({member.id}) - DMs disabled")
                
                # Kick the member
                await member.kick(reason="Account created today - NABG protection")
                
                # Log the action
                log_message = f"**User:** {member} ({member.id})\n**Account Created:** {member.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n**Reason:** Account created today"
                await self._send_log(guild, log_message)
                
                log.info(f"Kicked user {member} ({member.id}) from guild {guild.name} ({guild.id}) - account created today")
                
            except discord.Forbidden:
                log.warning(f"Failed to kick user {member} ({member.id}) from guild {guild.name} ({guild.id}) - insufficient permissions")
            except Exception as e:
                log.error(f"Error kicking user {member} ({member.id}) from guild {guild.name} ({guild.id}): {e}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(NABG(bot))