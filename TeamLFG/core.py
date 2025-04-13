import discord
from redbot.core import commands
from redbot.core.bot import Red
from discord.ui import View, Button
import json
import os

CONFIG_FILE = "lfg_config.json"

# Game thumbnails by name (case-insensitive)
game_images = {
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

class LFGView(View):
    def __init__(self, invite_url: str):
        super().__init__(timeout=None)
        self.add_item(Button(label="Join Voice", url=invite_url, style=discord.ButtonStyle.link, emoji="🎧"))


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

    @commands.command(name="lfg")
    async def lfg(self, ctx, message: str = None, game: str = None, number_of_people: int = None):
    user = ctx.author
    voice_state = user.voice

    # Check for command format
    if not all([message, game, number_of_people]):
        await ctx.send(
            f"❗ Usage: `*lfg \"message\" \"game name\" number`\n"
            f"Example: `*lfg \"Need 2 more!\" \"Valorant\" 5`"
        )
        return

    # Check number_of_people validity
    if not (1 <= number_of_people <= 10):
        await ctx.send("Please set the number of people between 1 and 10.")
        return

    # Check if user is in a voice channel
    if not voice_state or not voice_state.channel:
        await ctx.send("You need to be connected to a voice channel to use this command.")
        return

    # Optional: Check if restricted to a specific channel
    config = getattr(self.bot, "lfg_config", {})
    allowed_channel_id = config.get(str(ctx.guild.id))
    if allowed_channel_id and ctx.channel.id != allowed_channel_id:
        await ctx.send(f"You can only use this command in <#{allowed_channel_id}>.")
        return

    voice_channel = voice_state.channel
    await voice_channel.edit(user_limit=number_of_people)
    invite = await voice_channel.create_invite(max_age=3600, max_uses=10)

    # Get image
    game_key = game.lower()
    image_url = game_images.get(game_key, DEFAULT_IMAGE_URL)

    # Create styled embed
    embed = discord.Embed(
        title=f"🎮 Playing: {game}",
        description=f"**{message}**",
        color=discord.Color.purple(),
        timestamp=ctx.message.created_at
    )
    embed.add_field(name="🗣️ Voice Channel", value=voice_channel.name, inline=True)
    embed.add_field(name="👥 Players Needed", value=f"{number_of_people}", inline=True)
    embed.add_field(name="🔗 Invite", value=f"[Click to Join]({invite.url})", inline=False)
    embed.set_thumbnail(url=image_url)
    embed.set_footer(
        text=f"Created by {user.display_name}",
        icon_url=user.avatar.url if user.avatar else None
    )

    # Send embed with button
    view = LFGView(invite.url)
    await ctx.send(embed=embed, view=view)

    # Delete user message after success
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Bot doesn't have permission to delete messages

            
async def setup(bot):
    await bot.add_cog(TeamLFG(bot))
