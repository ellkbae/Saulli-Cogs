import discord
from redbot.core import commands
from redbot.core.bot import Red
import json
import os

CONFIG_FILE = "lfg_config.json"

# Game thumbnails by name (case-insensitive)
GAME_IMAGES = {
    "valorant": "https://1000logos.net/wp-content/uploads/2022/09/Valorant-Logo.jpg",
    "val": "https://1000logos.net/wp-content/uploads/2022/09/Valorant-Logo.jpg",
    "league of legends": "https://1000logos.net/wp-content/uploads/2020/09/League-of-Legends-logo.jpg",
    "lol": "https://1000logos.net/wp-content/uploads/2020/09/League-of-Legends-logo.jpg",
    "aram": "https://1000logos.net/wp-content/uploads/2020/09/League-of-Legends-logo.jpg",
    "fortnite": "https://1000logos.net/wp-content/uploads/2020/06/Fortnite-Logo-1.jpg",
    "cs": "https://1000logos.net/wp-content/uploads/2018/01/CSGO-Logo.jpg",
    "csgo": "https://1000logos.net/wp-content/uploads/2018/01/CSGO-Logo.jpg",
    "csgo2": "https://1000logos.net/wp-content/uploads/2018/01/CSGO-Logo.jpg",
    "roblox": "https://1000logos.net/wp-content/uploads/2017/09/Roblox-Logo-1.jpg",
    "minecraft": "https://1000logos.net/wp-content/uploads/2018/10/Minecraft-Logo.jpg",
    "mc": "https://1000logos.net/wp-content/uploads/2018/10/Minecraft-Logo.jpg",
    "overwatch": "https://1000logos.net/wp-content/uploads/2018/03/Overwatch-Logo.jpg",
    "marvelrivals": "https://www.marvelrivals.com/pc/gw/20241128194803/img/logo_ad22b142.png"
}

# Fallback image if no match found
DEFAULT_IMAGE_URL = "https://media.discordapp.net/attachments/1353077747748176003/1355691101700231188/gs_logo_small-01.png?ex=67fcf6fa&is=67fba57a&hm=1ae4c0ef5e1e428f39702fe7370da5b275dc597bcc666c44060f726a78b7e76e&=&format=webp&quality=lossless"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

class TeamLFG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def get_lfg_channel_id(self, guild_id):
        return self.config.get(str(guild_id), None)

    def set_lfg_channel_id(self, guild_id, channel_id):
        self.config[str(guild_id)] = channel_id
        save_config(self.config)

    @commands.command(name='setlfgchannel')
    @commands.has_permissions(administrator=True)
    async def set_lfg_channel(self, ctx, channel: discord.TextChannel):
        self.set_lfg_channel_id(ctx.guild.id, channel.id)
        await ctx.send(f"LFG commands can now only be used in {channel.mention}.")

    @commands.command(name='lfg')
    async def lfg(self, ctx, message: str = None, game: str = None, number_of_people: int = None):
        # Restrict to set channel
        allowed_channel_id = self.get_lfg_channel_id(ctx.guild.id)
        if allowed_channel_id and ctx.channel.id != allowed_channel_id:
            await ctx.send(f"{ctx.author.mention}, you can only use this command in <#{allowed_channel_id}>.")
            return

        # Check for correct usage
        if not all([message, game, number_of_people]):
            await ctx.send(
                f"{ctx.author.mention}, invalid usage. Example:\n"
                f"`*lfg \"Message here\" \"Game Name\" 5`\n"
                f"Quotes are required for message and game name."
            )
            return

        if number_of_people < 1 or number_of_people > 10:
            await ctx.send(f"{ctx.author.mention}, please enter a number of people between 1 and 10.")
            return

        user = ctx.author

        if not user.voice or not user.voice.channel:
            await ctx.send(f"{user.mention}, you must be connected to a voice channel to use this command.")
            return

        voice_channel = user.voice.channel

        try:
            await voice_channel.edit(user_limit=number_of_people)
        except discord.Forbidden:
            await ctx.send("I do not have permission to edit this voice channel.")
            return
        except Exception as e:
            await ctx.send(f"Error updating voice channel: {e}")
            return

        try:
            invite = await voice_channel.create_invite(max_age=3600, max_uses=0, unique=True, reason="LFG Command")
        except Exception as e:
            await ctx.send(f"Failed to create an invite link: {e}")
            return

        game_key = game.lower()
        image_url = GAME_IMAGES.get(game_key, DEFAULT_IMAGE_URL)

        embed = discord.Embed(
            title=f"Playing - {game}",
            description=message,
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Voice Channel", value=voice_channel.name, inline=True)
        embed.add_field(name="Players Needed", value=str(number_of_people), inline=True)
        embed.add_field(name="Join Here", value=invite.url, inline=False)
        embed.set_thumbnail(url=image_url)
        embed.set_footer(text=f"Created by {user.display_name}", icon_url=user.avatar.url if user.avatar else None)

        await ctx.send(embed=embed)

        # Try to delete user's command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
            
async def setup(bot):
    await bot.add_cog(TeamLFG(bot))
